"""Send a template WhatsApp message using Content SID to open the conversation window."""
import os, requests, json
from dotenv import load_dotenv
load_dotenv()

SID = os.getenv("TWILIO_ACCOUNT_SID")
TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
auth = (SID, TOKEN)

TO = "whatsapp:+918310002656"
FROM = "whatsapp:+15558485374"

# Use the appointment reminder template (most relevant)
CONTENT_SID = "HX37bac5e4fc62e4184bd5e610c1deab52"

print(f"Sending template message from {FROM} to {TO}...")
print(f"Using Content SID: {CONTENT_SID}")

url = f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json"

data = {
    "To": TO,
    "From": FROM,
    "ContentSid": CONTENT_SID,
    "ContentVariables": json.dumps({
        "date": "tomorrow",
        "time": "10:00 AM"
    }),
}

r = requests.post(url, auth=auth, data=data, timeout=15)
resp = r.json()

if r.status_code in (200, 201):
    print(f"\n✅ Message queued! SID: {resp.get('sid')}")
    print(f"Status: {resp.get('status')}")
else:
    print(f"\n❌ Error {r.status_code}")
    print(f"Code: {resp.get('code')}")
    print(f"Message: {resp.get('message')}")
    
    # If that template doesn't work, try others
    print("\n\nTrying other templates...")
    for name, content_sid in [
        ("Order Update", "HX097e61f7dae00a610fe056c4f2b23b02"),
        ("Message Opt-in", "HXc662326f0208c54682da2e7dcd2554da"),
    ]:
        data2 = {
            "To": TO,
            "From": FROM,
            "ContentSid": content_sid,
            "ContentVariables": json.dumps({
                "date": "March 10, 2026",
                "time": "10:00 AM"
            }),
        }
        r2 = requests.post(url, auth=auth, data=data2, timeout=15)
        resp2 = r2.json()
        status = "✅ Queued" if r2.status_code in (200, 201) else f"❌ {resp2.get('code')}: {resp2.get('message', '')[:80]}"
        print(f"  {name}: {status}")
        if r2.status_code in (200, 201):
            print(f"    SID: {resp2.get('sid')}")
            break
