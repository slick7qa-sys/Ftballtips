import requests
import datetime

def get_visitor_info(ip, user_agent):
    ipapi_url = f"https://ipapi.co/{ip}/json/"
    geoip_url = f"https://json.geoiplookup.io/{ip}"

    def safe_get_json(url):
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()  # raise HTTPError if status != 200
            return resp.json()
        except (requests.RequestException, ValueError):
            # If request failed or JSON parsing failed, return empty dict
            return {}

    details = safe_get_json(ipapi_url)
    vpnconn = safe_get_json(geoip_url)

    vpn = "Yes" if vpnconn.get("connection_type") == "Corporate" else "No"

    now_utc = datetime.datetime.utcnow()

    info = {
        "ip": ip,
        "user_agent": user_agent,
        "vpn": vpn,
        "country": details.get("country_name", "Unknown"),
        "countryCode": details.get("country_code", "xx").lower(),
        "region": details.get("region", ""),
        "city": details.get("city", ""),
        "zip": details.get("postal", ""),
        "lat": details.get("latitude", 0),
        "lon": details.get("longitude", 0),
        "date": now_utc.strftime("%d/%m/%Y"),
        "time": now_utc.strftime("%H:%M:%S"),
    }
    return info
