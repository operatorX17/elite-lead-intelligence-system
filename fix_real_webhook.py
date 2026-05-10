"""Fix Twilio webhook URL for actual phone number."""
import os, json, base64, urllib.request, urllib.parse
from dotenv import load_dotenv

load_dotenv(os.path.join(r"c:\Users\G Sai Prakash\Documents\zrai-lead-oss-main\zrai-lead-oss-main", "AI-AGENTS-NEW", ".env"))

sid = os.getenv("HEALTHCARE_TWILIO_ACCOUNT_SID", "")
token = os.getenv("HEALTHCARE_TWILIO_AUTH_TOKEN", "")
target_phone = "+15558485374"
auth = base64.b64encode(f"{sid}:{token}".encode()).decode()

WEBHOOK = "https://58af-157-50-177-79.ngrok-free.app/webhook/whatsapp"

# List all phone numbers
url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/IncomingPhoneNumbers.json"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Basic {auth}")

found = False
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    for p in data["incoming_phone_numbers"]:
        if p["phone_number"] == target_phone:
            found = True
            pn_sid = p["sid"]
            old_url = p.get("sms_url", "NONE")
            print(f"Target Phone SID: {pn_sid}")
            print(f"Old SMS URL: {old_url}")
            
            # Update
            update_url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/IncomingPhoneNumbers/{pn_sid}.json"
            update_data = urllib.parse.urlencode({"SmsUrl": WEBHOOK, "SmsMethod": "POST"}).encode()
            update_req = urllib.request.Request(update_url, data=update_data, method="POST")
            update_req.add_header("Authorization", f"Basic {auth}")
            with urllib.request.urlopen(update_req) as uresp:
                result = json.loads(uresp.read().decode())
                print(f"NEW SMS URL: {result.get('sms_url')}")
                print("SUCCESS!")
            break

if not found:
    print(f"Could not find phone number {target_phone} in Twilio account.")
