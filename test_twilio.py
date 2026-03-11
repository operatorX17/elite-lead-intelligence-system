import os
import sys
import requests
from dotenv import load_dotenv

# Load the environment variables from the .env file in the current directory
load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

def test_twilio_whatsapp(to_number: str):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        print("❌ ERROR: Twilio credentials not found. Please check your .env file.")
        sys.exit(1)

    print(f"Sending test WhatsApp message to {to_number} from {TWILIO_PHONE_NUMBER}...")

    # Ensure the destination number is in Twilio's expected whatsapp formatting
    if not to_number.startswith("whatsapp:"):
        # Auto-add default country code if missing (assumes India based on prior context, but handles '+' as well)
        if not to_number.startswith("+"):
            if len(to_number) == 10:
                to_number = "+91" + to_number
            else:
                to_number = "+" + to_number
        to_number = f"whatsapp:{to_number}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    
    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    data = {
        "To": to_number,
        "From": TWILIO_PHONE_NUMBER if TWILIO_PHONE_NUMBER.startswith("whatsapp:") else f"whatsapp:{TWILIO_PHONE_NUMBER}",
        "Body": "Hello! This is a test message from your new Twilio integration. 🎉",
    }

    try:
        response = requests.post(url, auth=auth, data=data, timeout=15)
        if response.status_code in (200, 201):
            print("✅ SUCCESS! Message scheduled/sent successfully. Check your WhatsApp.")
            print(f"Response data: {response.json()}")
        else:
            print(f"❌ ERROR: Failed to send message. HTTP Status Code: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ EXCEPTION ERROR: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_twilio.py <your_phone_number>")
        print("Example: python test_twilio.py +919876543210")
        sys.exit(1)
        
    test_twilio_whatsapp(sys.argv[1])
