"""Deep diagnostic: Find WhatsApp sender registration for +15574674237."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SID = os.getenv("TWILIO_ACCOUNT_SID")
TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
auth = (SID, TOKEN)

print("=" * 60)
print("DEEP WHATSAPP SENDER DIAGNOSTIC")
print("=" * 60)

# 1. Check all messaging services and their senders
print("\n1. ALL MESSAGING SERVICES + SENDERS:")
r = requests.get("https://messaging.twilio.com/v1/Services", auth=auth)
if r.status_code == 200:
    for svc in r.json().get("services", []):
        sid = svc["sid"]
        name = svc["friendly_name"]
        print(f"\n   📨 {name} ({sid})")
        print(f"      Inbound URL:    {svc.get('inbound_request_url')}")
        print(f"      Fallback URL:   {svc.get('fallback_url')}")
        print(f"      Status CB:      {svc.get('status_callback')}")
        
        # Check phone numbers in this service
        r2 = requests.get(f"https://messaging.twilio.com/v1/Services/{sid}/PhoneNumbers", auth=auth)
        if r2.status_code == 200:
            nums = r2.json().get("phone_numbers", [])
            for n in nums:
                print(f"      Phone: {n.get('phone_number')} ({n.get('sid')})")
            if not nums:
                print(f"      (no phone numbers)")

# 2. Check WhatsApp-specific endpoints
print("\n\n2. WHATSAPP SENDER REGISTRATION CHECK:")

# Try the WhatsApp Senders endpoint (different methods)
endpoints_to_try = [
    ("GET", "https://messaging.twilio.com/v1/Senders/WhatsApp"),
    ("GET", "https://messaging.twilio.com/v1/WhatsApp/Senders"),
    ("GET", f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json?From=whatsapp:+15574674237&PageSize=1"),
]

for method, url in endpoints_to_try:
    r = requests.request(method, url, auth=auth)
    print(f"\n   {method} {url}")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print(f"   Data: {r.text[:300]}")
    else:
        print(f"   Response: {r.text[:200]}")

# 3. Check if the number was EVER used for WhatsApp (check message history)
print("\n\n3. WHATSAPP MESSAGE HISTORY (looking for past messages):")
r = requests.get(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json",
    auth=auth,
    params={"From": "whatsapp:+15574674237", "PageSize": 5}
)
if r.status_code == 200:
    msgs = r.json().get("messages", [])
    if msgs:
        print(f"   Found {len(msgs)} messages sent FROM whatsapp:+15574674237:")
        for m in msgs:
            print(f"      {m['date_created']} -> {m['to']} | {m['status']} | {m['body'][:50]}")
    else:
        print("   No messages found FROM whatsapp:+15574674237")

r = requests.get(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json",
    auth=auth,
    params={"To": "whatsapp:+15574674237", "PageSize": 5}
)
if r.status_code == 200:
    msgs = r.json().get("messages", [])
    if msgs:
        print(f"   Found {len(msgs)} messages sent TO whatsapp:+15574674237:")
        for m in msgs:
            print(f"      {m['date_created']} -> from {m['from']} | {m['status']} | {m['body'][:50]}")
    else:
        print("   No messages found TO whatsapp:+15574674237")

# Also check the other number
r = requests.get(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json",
    auth=auth,
    params={"From": "whatsapp:+18457738083", "PageSize": 5}
)
if r.status_code == 200:
    msgs = r.json().get("messages", [])
    if msgs:
        print(f"\n   Found {len(msgs)} messages FROM whatsapp:+18457738083:")
        for m in msgs:
            print(f"      {m['date_created']} -> {m['to']} | {m['status']} | {m['body'][:50]}")
    else:
        print(f"\n   No messages found FROM whatsapp:+18457738083 either")

# 4. Check ALL recent WhatsApp messages in the account
print("\n\n4. ALL RECENT WHATSAPP MESSAGES IN ACCOUNT:")
r = requests.get(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json",
    auth=auth,
    params={"PageSize": 10}
)
if r.status_code == 200:
    msgs = r.json().get("messages", [])
    for m in msgs:
        print(f"   {m['date_created']} | {m['from']} -> {m['to']} | {m['status']} | {m['body'][:40]}")

# 5. Check sub-accounts (maybe the WhatsApp sender is under a sub-account)
print("\n\n5. SUB-ACCOUNTS CHECK:")
r = requests.get(f"https://api.twilio.com/2010-04-01/Accounts.json", auth=auth)
if r.status_code == 200:
    accts = r.json().get("accounts", [])
    for a in accts:
        print(f"   Account: {a['friendly_name']} | SID: {a['sid']} | Status: {a['status']}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
