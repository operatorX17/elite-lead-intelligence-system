import os, requests, time
from dotenv import load_dotenv
load_dotenv()
a = (os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

sids = [
    ("Bot 1", "MM87a8c298259f3f4eab6d610ab1fb346e"),
    ("smileathonZ", "MM9d38e33d87ecfa9aaa9c029d27a3441d"),
    ("Bot 2", "MM74f3cb951e0d2e61fd36f16812746be2"),
    ("Direct From", "SMb30ba184c5a06e8dd38b4292c3754abd"),
]

time.sleep(5)
print("Checking delivery status...\n")
for name, sid in sids:
    r = requests.get(f"https://api.twilio.com/2010-04-01/Accounts/{a[0]}/Messages/{sid}.json", auth=a)
    d = r.json()
    print(f"{name}: status={d.get('status')}, error={d.get('error_code')}, from={d.get('from')}")
