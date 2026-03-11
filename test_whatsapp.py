import requests
import sys

# Credentials from AI-AGENTS-NEW/.env
META_PHONE_ID = "826516377219932"
META_WHATSAPP_TOKEN = "EAALZBYsZByha4BQHMi5kQqQwo1k4a4z9uDBsvW1ZA1HdSIVCsdylBJJwZB8GZAhq41HZCbojiXq7PTbLIqWnhduFiftq6siUIo9lG91xSx4JJWX7zSqoZCvRrQV3NAGyP2zkLZAFj64B40XhOX8bW5Ha7ybj4Q4FOAkkeLU7sAaH623oV0OezYG1Xz6xycZBGCs4TTgZDZD"

def test_whatsapp(to_number: str):
    print(f"Sending test message to {to_number}...")
    
    # Ensure number has country code (e.g., 91 for India)
    if not to_number.startswith("91") and len(to_number) == 10:
        to_number = "91" + to_number
        print(f"Auto-added country code: {to_number}")

    url = f"https://graph.facebook.com/v21.0/{META_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": "hello_world",
            "language": {
                "code": "en_US"
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        import json
        with open("error.log", "w") as f:
            f.write(json.dumps(response.json(), indent=2))
        print("Logged response to error.log")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    test_whatsapp(sys.argv[1])
