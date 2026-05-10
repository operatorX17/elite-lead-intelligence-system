"""Check Twilio Sandbox config and get the join code."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SID = os.getenv("TWILIO_ACCOUNT_SID")
TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
auth = (SID, TOKEN)

print("=" * 60)
print("TWILIO WHATSAPP SANDBOX CONFIG")
print("=" * 60)

# Get the sandbox messaging service details
# The sandbox service SID from diagnostic: MG97e29c78ccb2c195b513cbf1dcc8b1ae
SANDBOX_SID = "MG97e29c78ccb2c195b513cbf1dcc8b1ae"

# Get service details
r = requests.get(f"https://messaging.twilio.com/v1/Services/{SANDBOX_SID}", auth=auth)
if r.status_code == 200:
    svc = r.json()
    print(f"\nService: {svc.get('friendly_name')}")
    print(f"SID:     {svc.get('sid')}")
    print(f"Webhook: {svc.get('inbound_request_url', 'NOT SET')}")
    print(f"Fallback: {svc.get('fallback_url', 'NOT SET')}")
    print(f"Status callback: {svc.get('status_callback', 'NOT SET')}")
else:
    print(f"Error: {r.status_code} - {r.text[:200]}")

# List phone numbers in the messaging service
print(f"\nPhone numbers in service:")
r = requests.get(f"https://messaging.twilio.com/v1/Services/{SANDBOX_SID}/PhoneNumbers", auth=auth)
if r.status_code == 200:
    nums = r.json().get("phone_numbers", [])
    for n in nums:
        print(f"  📱 {n.get('phone_number')} - {n.get('sid')}")
    if not nums:
        print("  (none)")
else:
    print(f"  Error: {r.status_code}")

# Check sandbox config directly
print(f"\n--- Sandbox Configuration ---")
r = requests.get(
    f"https://messaging.twilio.com/v1/a]Services/{SANDBOX_SID}/AlphaSenders",
    auth=auth
)
if r.status_code == 200:
    print(f"Alpha senders: {r.json()}")

# Check the actual sandbox phone number configuration
print(f"\n--- Number +14155238886 webhook config ---")
# List all numbers to find the sandbox one
r = requests.get(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/IncomingPhoneNumbers.json",
    auth=auth,
    params={"PhoneNumber": "+14155238886"}
)
if r.status_code == 200:
    nums = r.json().get("incoming_phone_numbers", [])
    if nums:
        n = nums[0]
        print(f"  SMS URL:   {n.get('sms_url')}")
        print(f"  Voice URL: {n.get('voice_url')}")
    else:
        print("  Sandbox number not in your account (it's shared by Twilio)")
        print("  You configure the webhook via the Twilio Console sandbox page.")

print(f"\n--- Current Sandbox Webhook (via API) ---")
# Try the conversations API
r = requests.get(
    f"https://conversations.twilio.com/v1/Configuration/Webhooks",
    auth=auth
)
if r.status_code == 200:
    print(f"  Conversations webhooks: {r.json()}")
else:
    print(f"  {r.status_code}")

print("\n" + "=" * 60)
print("NEXT STEPS:")
print("=" * 60)
print("""
1. FIRST: Join the sandbox from your WhatsApp:
   - Open WhatsApp on your phone
   - Send a message to +14155238886
   - The message should be: join <your-sandbox-code>
   - Find the join code at: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn

2. THEN: Set the webhook URL in the Twilio Console sandbox page:
   - Go to: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
   - Set "WHEN A MESSAGE COMES IN" to your bot's public URL + /webhook/whatsapp
   - Method: POST

3. If running locally, you need a tunnel (ngrok/localtunnel) to expose your bot.
""")
