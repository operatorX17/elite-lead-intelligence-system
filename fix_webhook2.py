"""Check and fix Twilio WhatsApp Sandbox webhook."""
import os, json, base64, urllib.request, urllib.parse
from dotenv import load_dotenv

load_dotenv(os.path.join(r"c:\Users\G Sai Prakash\Documents\zrai-lead-oss-main\zrai-lead-oss-main", "AI-AGENTS-NEW", ".env"))

sid = os.getenv("HEALTHCARE_TWILIO_ACCOUNT_SID", "")
token = os.getenv("HEALTHCARE_TWILIO_AUTH_TOKEN", "")
auth = base64.b64encode(f"{sid}:{token}".encode()).decode()

WEBHOOK = "https://58af-157-50-177-79.ngrok-free.app/webhook/whatsapp"

# Try messaging service endpoint
print("=== Checking MessagingServices ===")
try:
    url = f"https://messaging.twilio.com/v1/Services"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        for svc in data.get("services", []):
            print(f"Service: {svc.get('friendly_name')} SID: {svc.get('sid')}")
            print(f"  Inbound URL: {svc.get('inbound_request_url')}")
except Exception as e:
    print(f"MessagingServices error: {e}")

# Try the channels endpoint for WhatsApp sandbox
print("\n=== Checking WhatsApp Senders ===")
try:
    url = f"https://messaging.twilio.com/v1/Services?PageSize=20"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        services = data.get("services", [])
        for svc in services:
            svc_sid = svc["sid"]
            print(f"\nService: {svc.get('friendly_name')} ({svc_sid})")
            print(f"  Inbound URL: {svc.get('inbound_request_url')}")
            print(f"  Fallback URL: {svc.get('fallback_url')}")
            
            # Update inbound URL
            update_url = f"https://messaging.twilio.com/v1/Services/{svc_sid}"
            update_data = urllib.parse.urlencode({
                "InboundRequestUrl": WEBHOOK,
                "InboundMethod": "POST"
            }).encode()
            update_req = urllib.request.Request(update_url, data=update_data, method="POST")
            update_req.add_header("Authorization", f"Basic {auth}")
            try:
                with urllib.request.urlopen(update_req) as uresp:
                    result = json.loads(uresp.read().decode())
                    print(f"  UPDATED Inbound URL: {result.get('inbound_request_url')}")
            except Exception as e:
                print(f"  Update failed: {e}")
except Exception as e:
    print(f"Error: {e}")
