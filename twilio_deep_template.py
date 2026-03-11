"""Check WhatsApp template approval and WABA details."""
import os, requests, json
from dotenv import load_dotenv
load_dotenv()

SID = os.getenv("TWILIO_ACCOUNT_SID")
TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
auth = (SID, TOKEN)

print("=" * 60)
print("WHATSAPP TEMPLATE + WABA STATUS CHECK")
print("=" * 60)

# 1. Check each content template's full details
print("\n1. CONTENT TEMPLATE DETAILS:")
r = requests.get("https://content.twilio.com/v1/Content", auth=auth)
if r.status_code == 200:
    for c in r.json().get("contents", []):
        sid = c["sid"]
        name = c["friendly_name"]
        print(f"\n  Template: {name} ({sid})")
        
        # Try to get approval status
        r2 = requests.get(f"https://content.twilio.com/v1/Content/{sid}/ApprovalRequests", auth=auth)
        print(f"  Approval: {r2.status_code} - {r2.text[:200]}")

# 2. Check the messaging service that has our number
print("\n\n2. MESSAGING SERVICE WITH OUR NUMBER:")
# Check smileathonZ service since it had +15574674237
# But we need to find which service has +15558485374
r = requests.get("https://messaging.twilio.com/v1/Services", auth=auth)
if r.status_code == 200:
    for svc in r.json().get("services", []):
        sid = svc["sid"]
        r2 = requests.get(f"https://messaging.twilio.com/v1/Services/{sid}/PhoneNumbers", auth=auth)
        if r2.status_code == 200:
            for n in r2.json().get("phone_numbers", []):
                if "5558485374" in n.get("phone_number", ""):
                    print(f"  Found! Number +15558485374 is in service: {svc['friendly_name']} ({sid})")
                    print(f"  Inbound URL: {svc.get('inbound_request_url')}")

# 3. Check what happens when we try to send with MessagingServiceSid instead
print("\n\n3. TRYING WITH MESSAGING SERVICE SID:")
# Try each messaging service
for ms_sid, ms_name in [
    ("MG97e29c78ccb2c195b513cbf1dcc8b1ae", "Ssmileathon WhatsApp Bot 1"),
    ("MGa5e1908946698744dae2a95c90ec5088", "smileathonZ"),
    ("MGf885abe10feb46868631f5fbfe0294a1", "Ssmileathon WhatsApp Bot 2"),
]:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json"
    data = {
        "To": "whatsapp:+918310002656",
        "MessagingServiceSid": ms_sid,
        "ContentSid": "HX37bac5e4fc62e4184bd5e610c1deab52",
        "ContentVariables": json.dumps({"date": "tomorrow", "time": "10 AM"}),
    }
    r = requests.post(url, auth=auth, data=data, timeout=15)
    resp = r.json()
    if r.status_code in (200, 201):
        print(f"  ✅ {ms_name}: Queued! SID={resp.get('sid')}, Status={resp.get('status')}")
    else:
        print(f"  ❌ {ms_name}: {resp.get('code')} - {resp.get('message', '')[:100]}")

# 4. Try the hello_world template which is always pre-approved
print("\n\n4. TRYING SIMPLEST POSSIBLE TEMPLATE (hello_world via body):")
url = f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json"

# Try using the simple body format with the From number
data = {
    "To": "whatsapp:+918310002656",
    "From": "whatsapp:+15558485374",
    "Body": "Your appointment is coming up on {{1}} at {{2}}",
}
r = requests.post(url, auth=auth, data=data, timeout=15)
resp = r.json()
print(f"  Status: {r.status_code}")
print(f"  Response: {json.dumps(resp, indent=2)[:300]}")
