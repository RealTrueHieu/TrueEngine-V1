import urllib.request
import re

url = "https://komodochess.com/downloads.htm"
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    matches = re.findall(r'href=[\'"]([^\'"]+)[\'"]', html)
    for m in matches:
        if any(k in m.lower() for k in ["komodo", "zip", "exe", "dragon", "pub"]):
            print("FOUND:", m)
except Exception as e:
    print("Fetch error:", e)
