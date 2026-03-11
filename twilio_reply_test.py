"""Check if user's message was received and try to reply."""
import os, requests, json
from dotenv import load_dotenv
load_dotenv()

SID = os.getenv("TWILIO_ACCOUNT_SID")
TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
auth = (SID, TOKEN)

print("=" * 60)
print("1. CHECK: Did Twilio receive the user's message?")
print("=" * 60)

# Check recent incoming messages
r = requests.get(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json",
    auth=auth,
    params={"To": "whatsapp:+15558485374", "PageSize": 5}
)
if r.status_code == 200:
    msgs = r.json().get("messages", [])
    if msgs:
        print(f"Found {len(msgs)} recent messages TO +15558485374:")
        for m in msgs:
            print(f"  {m['date_created']} | From: {m['from']} | Body: {m['body'][:50]} | Status: {m['status']}")
    else:
        print("No messages found TO +15558485374")

# Also check all recent messages
print("\nAll recent messages in account:")
r = requests.get(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json",
    auth=auth,
    params={"PageSize": 10}
)
if r.status_code == 200:
    for m in r.json().get("messages", []):
        print(f"  {m['date_created']} | {m['from']} -> {m['to']} | {m['status']} | {m['body'][:40]}")

print("\n" + "=" * 60)
print("2. ATTEMPT: Send freeform reply (now inside 24h window)")
print("=" * 60)

url = f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json"
data = {
    "To": "whatsapp:+918310002656",
    "From": "whatsapp:+15558485374",
    "Body": "Hey! This is a test reply from the bot. The Twilio integration is working! 🎉",
}

r = requests.post(url, auth=auth, data=data, timeout=15)
resp = r.json()
print(f"\nHTTP Status: {r.status_code}")
if r.status_code in (200, 201):
    print(f"✅ Reply sent! SID: {resp.get('sid')}, Status: {resp.get('status')}")
else:
    print(f"❌ Error: {resp.get('code')} - {resp.get('message')}")

# Wait and check delivery
import time
time.sleep(5)

if r.status_code in (200, 201):
    msg_sid = resp.get("sid")
    r2 = requests.get(f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages/{msg_sid}.json", auth=auth)
    d = r2.json()
    print(f"\nDelivery check: status={d.get('status')}, error={d.get('error_code')}")
