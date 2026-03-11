import urllib.request, json
try:
    with urllib.request.urlopen("http://127.0.0.1:4040/api/requests/http") as response:
        data = json.loads(response.read().decode())
        reqs = data.get("requests", [])
        print(f"Total requests caught by ngrok: {len(reqs)}")
        for r in reqs[:5]:
            req = r.get("request", {})
            resp = r.get("response", {})
            print(f"- {req.get('method')} {req.get('uri')} -> Status: {resp.get('status_code')}")
except Exception as e:
    print("Error:", e)
