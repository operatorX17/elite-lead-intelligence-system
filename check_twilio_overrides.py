import os, json, base64, urllib.request
from dotenv import load_dotenv

load_dotenv(os.path.join(r"c:\Users\G Sai Prakash\Documents\zrai-lead-oss-main\zrai-lead-oss-main", "AI-AGENTS-NEW", ".env"))

sid = os.getenv("HEALTHCARE_TWILIO_ACCOUNT_SID", "")
token = os.getenv("HEALTHCARE_TWILIO_AUTH_TOKEN", "")
auth = base64.b64encode(f"{sid}:{token}".encode()).decode()

try:
    # There is no direct "WhatsApp Senders" REST API exposed that behaves like IncomingPhoneNumbers.
    # However, sometimes they are mapped under phone numbers, or we can check the recent messages to get details.
    
    # As an alternative to see why webhooks are suppressed, let's look at Twilio Conversations Configuration.
    url = f"https://conversations.twilio.com/v1/Configuration"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req) as resp:
        print("CONVERSATIONS CONFIG:")
        print(json.loads(resp.read().decode()))
except Exception as e:
    print("Error getting Conversations Config:", e)

try:
    # Check Twilio Studio Flows (Active Executions)
    url = f"https://studio.twilio.com/v2/Flows"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print("\nSTUDIO FLOWS:")
        for f in data.get("flows", []):
            print(f"Flow: {f['friendly_name']} SID: {f['sid']} Status: {f['status']}")
except Exception as e:
    print("Error getting Studio Flows:", e)
