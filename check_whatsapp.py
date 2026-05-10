import os, json, base64, urllib.request
from dotenv import load_dotenv

load_dotenv(os.path.join(r"c:\Users\G Sai Prakash\Documents\zrai-lead-oss-main\zrai-lead-oss-main", "AI-AGENTS-NEW", ".env"))

sid = os.getenv("HEALTHCARE_TWILIO_ACCOUNT_SID", "")
token = os.getenv("HEALTHCARE_TWILIO_AUTH_TOKEN", "")
auth = base64.b64encode(f"{sid}:{token}".encode()).decode()

print(f"Checking WhatsApp Senders for SID {sid}")

try:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/IncomingPhoneNumbers.json"
    print("\n--- INCOMING PHONE NUMBERS ---")
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        for p in data.get("incoming_phone_numbers", []):
            print(f"Phone: {p['phone_number']} SID: {p['sid']} SMS URL: {p.get('sms_url')} StatusCallback: {p.get('status_callback')}")
except Exception as e:
    print("Error:", e)

try:
    print("\n--- MESSAGING SERVICES ---")
    url = f"https://messaging.twilio.com/v1/Services"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        for svc in data.get("services", []):
            print(f"Service: {svc.get('friendly_name')} SID: {svc.get('sid')} Inbound URL: {svc.get('inbound_request_url')}")
            
            # Check senders in this service
            try:
                s_url = f"https://messaging.twilio.com/v1/Services/{svc.get('sid')}/PhoneNumbers"
                s_req = urllib.request.Request(s_url)
                s_req.add_header("Authorization", f"Basic {auth}")
                with urllib.request.urlopen(s_req) as s_resp:
                    s_data = json.loads(s_resp.read().decode())
                    for sender in s_data.get("phone_numbers", []):
                        print(f"  -> Sender: {sender.get('phone_number')}")
            except Exception as se:
                print("  -> Error fetching senders:", se)
except Exception as e:
    print("Error:", e)
