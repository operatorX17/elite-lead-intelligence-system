"""List approved WhatsApp Content Templates in Twilio."""
import os, requests
from dotenv import load_dotenv
load_dotenv()

SID = os.getenv("TWILIO_ACCOUNT_SID")
TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
auth = (SID, TOKEN)

print("=" * 60)
print("TWILIO CONTENT TEMPLATES")
print("=" * 60)

# List all Content Templates
r = requests.get("https://content.twilio.com/v1/Content", auth=auth)
if r.status_code == 200:
    contents = r.json().get("contents", [])
    if not contents:
        print("\n  No Content Templates found.")
        print("  You need to create one in Twilio Console:")
        print("  https://console.twilio.com/us1/develop/sms/content-template-builder")
    else:
        print(f"\n  Found {len(contents)} template(s):\n")
        for c in contents:
            print(f"  - Name: {c.get('friendly_name')}")
            print(f"     SID:  {c.get('sid')}")
            print(f"     Types: {list(c.get('types', {}).keys())}")
            
            # Show approval status
            approval = c.get("approval_requests", {})
            print(f"     Status: {approval.get('status', 'unknown')}")
            
            # Show the body content
            types = c.get("types", {})
            for tname, tdata in types.items():
                if "body" in tdata:
                    print(f"     Body: {tdata['body'][:100]}")
            print()
else:
    print(f"\n  Error {r.status_code}: {r.text[:300]}")

# Also check Content Template approval statuses
print("\n--- Template Approval Statuses ---")
r = requests.get("https://content.twilio.com/v1/Content", auth=auth, params={"PageSize": 50})
if r.status_code == 200:
    for c in r.json().get("contents", []):
        sid = c.get("sid")
        # Check approval status
        r2 = requests.get(f"https://content.twilio.com/v1/Content/{sid}/ApprovalRequests/whatsapp", auth=auth)
        if r2.status_code == 200:
            approval = r2.json()
            print(f"  {c.get('friendly_name')}: {approval.get('status', 'N/A')} (category: {approval.get('category', 'N/A')})")
        else:
            print(f"  {c.get('friendly_name')}: Could not fetch approval ({r2.status_code})")
