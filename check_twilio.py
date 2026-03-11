import os, json, base64, urllib.request
from dotenv import load_dotenv

load_dotenv(os.path.join(r"c:\Users\G Sai Prakash\Documents\zrai-lead-oss-main\zrai-lead-oss-main", "AI-AGENTS-NEW", ".env"))

sid = os.getenv("HEALTHCARE_TWILIO_ACCOUNT_SID", "")
token = os.getenv("HEALTHCARE_TWILIO_AUTH_TOKEN", "")
auth = base64.b64encode(f"{sid}:{token}".encode()).decode()

print(f"Checking Twilio logs for SID {sid}")

# Check recent Messages
try:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json?PageSize=5"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print("\n--- RECENT MESSAGES ---")
        for m in data.get("messages", []):
            print(f"[{m['direction']}] From: {m['from']} To: {m['to']} Status: {m['status']} Error: {m.get('error_message')}")
except Exception as e:
    print("Error fetching messages:", e)

# Check recent Alerts/Errors
try:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Notifications.json?PageSize=5"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print("\n--- RECENT ERRORS ---")
        for m in data.get("notifications", []):
            print(f"[{m['log']}] Code: {m.get('error_code')} Msg: {m['message_text']}")
except Exception as e:
    print("Error fetching alerts:", e)
