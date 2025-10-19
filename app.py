def send_to_discord(info):
    """Send the information to Discord webhook"""
    embed = {
        "username": "🌍 Visitor Bot",
        "embeds": [{
            "title": f"🚶‍♂️ New Visitor from {info['country']}",
            "description": "Here’s a breakdown of the visitor's details:",
            "color": 7506394,  # Light teal color
            "fields": [
                {
                    "name": "🖥️ IP & Location",
                    "value": f"**IP:** `{info['ip']}`\n**City:** {info['city']} ({info['region']}, {info['country']})\n**Postal Code:** {info['zip']}",
                    "inline": False
                },
                {
                    "name": "📱 User Agent",
                    "value": f"**Browser/Device:** `{info['user_agent']}`",
                    "inline": False
                },
                {
                    "name": "🌍 Google Maps Location",
                    "value": f"[Click to view on Google Maps](https://www.google.com/maps?q={info['lat']},{info['lon']})",
                    "inline": False
                }
            ],
            "footer": {
                "text": f"🔗 Visit logged at: {info['date']} {info['time']} (GMT)",
                "icon_url": "https://example.com/alarm-clock-icon.png"
            },
            "thumbnail": {
                "url": "https://example.com/thumbnail-image.png"  # Optional: Custom thumbnail
            }
        }]
    }  # Make sure this curly brace is here to close the dictionary.

    headers = {"Content-Type": "application/json"}
    response = requests.post(DISCORD_WEBHOOK_URL, json=embed, headers=headers)
    print(f"Discord webhook response: {response.status_code}")
