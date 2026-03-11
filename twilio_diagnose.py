"""Twilio Account Diagnostic - Check WhatsApp setup."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SID = os.getenv("TWILIO_ACCOUNT_SID")
TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
auth = (SID, TOKEN)

print("=" * 60)
print("TWILIO ACCOUNT DIAGNOSTIC")
print("=" * 60)

# 1. Check account info
print("\n1. ACCOUNT INFO:")
r = requests.get(f"https://api.twilio.com/2010-04-01/Accounts/{SID}.json", auth=auth)
if r.status_code == 200:
    acct = r.json()
    print(f"   Name:   {acct.get('friendly_name')}")
    print(f"   Status: {acct.get('status')}")
    print(f"   Type:   {acct.get('type')}")
else:
    print(f"   ❌ Could not fetch account: {r.status_code} - {r.text}")

# 2. List all phone numbers
print("\n2. PHONE NUMBERS IN ACCOUNT:")
r = requests.get(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/IncomingPhoneNumbers.json",
    auth=auth
)
if r.status_code == 200:
    numbers = r.json().get("incoming_phone_numbers", [])
    if not numbers:
        print("   No phone numbers found.")
    for n in numbers:
        print(f"   📱 {n['phone_number']} ({n['friendly_name']})")
        caps = n.get("capabilities", {})
        print(f"      SMS: {caps.get('sms')}, Voice: {caps.get('voice')}, MMS: {caps.get('mms')}")
        print(f"      SID: {n['sid']}")
else:
    print(f"   ❌ Error: {r.status_code}")

# 3. Check Messaging Services
print("\n3. MESSAGING SERVICES:")
r = requests.get(
    f"https://messaging.twilio.com/v1/Services",
    auth=auth
)
if r.status_code == 200:
    services = r.json().get("services", [])
    if not services:
        print("   No messaging services found.")
    for s in services:
        print(f"   📨 {s['friendly_name']} (SID: {s['sid']})")
        print(f"      Use case: {s.get('use_case')}")
else:
    print(f"   ❌ Error: {r.status_code}")

# 4. Check WhatsApp Senders (Channels API)
print("\n4. WHATSAPP SENDERS (Channels):")
r = requests.get(
    f"https://messaging.twilio.com/v1/Channels/WhatsApp/Senders",
    auth=auth
)
if r.status_code == 200:
    senders = r.json().get("senders", [])
    if not senders:
        print("   ⚠️  No WhatsApp senders found!")
        print("   This is why error 63007 happens.")
        print("   Your number needs to be registered as a WhatsApp sender in Twilio.")
    for s in senders:
        print(f"   ✅ {s}")
else:
    print(f"   Response: {r.status_code} - {r.text[:200]}")

# 5. Check WhatsApp Sandbox
print("\n5. WHATSAPP SANDBOX:")
r = requests.get(
    f"https://messaging.twilio.com/v1/Services?FriendlyName=Twilio+Sandbox+for+WhatsApp",
    auth=auth
)
if r.status_code == 200:
    services = r.json().get("services", [])
    if services:
        print(f"   ✅ Sandbox service exists: {services[0]['sid']}")
    else:
        print("   ⚠️  No WhatsApp sandbox service found.")
else:
    print(f"   Response: {r.status_code}")

# 6. Try sending via sandbox number
print("\n6. TRYING SANDBOX NUMBER (+14155238886):")
sandbox_data = {
    "To": "whatsapp:+918310002656",
    "From": "whatsapp:+14155238886",
    "Body": "Test from Twilio WhatsApp Sandbox"
}
r = requests.post(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json",
    auth=auth,
    data=sandbox_data
)
if r.status_code in (200, 201):
    print(f"   ✅ Sandbox message sent! SID: {r.json().get('sid')}")
else:
    resp = r.json()
    print(f"   Status: {r.status_code}")
    print(f"   Code:   {resp.get('code')}")
    print(f"   Msg:    {resp.get('message')}")

print("\n" + "=" * 60)
print("DIAGNOSIS COMPLETE")
print("=" * 60)
