"""Fix Twilio webhook URL - clean version."""
import os, json, base64, urllib.request, urllib.parse
from dotenv import load_dotenv

load_dotenv(os.path.join(r"c:\Users\G Sai Prakash\Documents\zrai-lead-oss-main\zrai-lead-oss-main", "AI-AGENTS-NEW", ".env"))

sid = os.getenv("HEALTHCARE_TWILIO_ACCOUNT_SID", "")
token = os.getenv("HEALTHCARE_TWILIO_AUTH_TOKEN", "")
auth = base64.b64encode(f"{sid}:{token}".encode()).decode()

WEBHOOK = "https://creations-corner-color-libraries.trycloudflare.com/webhook/whatsapp"

# List all phone numbers
url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/IncomingPhoneNumbers.json"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Basic {auth}")

with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    for p in data["incoming_phone_numbers"]:
        pn_sid = p["sid"]
        phone = p["phone_number"]
        old_url = p.get("sms_url", "NONE")
        print(f"Phone SID: {pn_sid}")
        print(f"Phone: {phone}")
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
