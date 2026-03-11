import sqlite3
import datetime
import argparse
import sys

# Format: python add_test_lead.py --phone 1234567890 --clinic "Test Clinic" --owner "Sai"
def main():
    parser = argparse.ArgumentParser(description="Inject a test lead into lead_queue.db")
    parser.add_argument("--phone", required=True, help="Test phone number without any +, e.g. 919876543210")
    parser.add_argument("--clinic", default="Test Dental Clinic", help="Name of the test clinic")
    parser.add_argument("--owner", default="Dr. Tester", help="Name of the contact person")
    parser.add_argument("--weakness", default="missing 35% of patient calls on weekends", help="The weakness Lead-OS found")
    args = parser.parse_args()

    db_path = "lead_queue.db"
    
    # ensure it's digits only
    clean_phone = "".join(filter(str.isdigit, args.phone))
    
    lead_id = f"test_lead_{clean_phone}"

    try:
        with sqlite3.connect(db_path) as conn:
            # Check if this phone already exists and delete it to reset state
            conn.execute("DELETE FROM leads WHERE phone = ?", (clean_phone,))
            
            # Insert the new mock lead
            conn.execute("""
                INSERT INTO leads (
                    lead_id, clinic_name, owner_name, phone, tier, score, 
                    outreach_angle, weakness_summary,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead_id, args.clinic, args.owner, clean_phone,
                "Tier 1", 95, 
                "We built an AI to patch your patient booking leaks.",
                args.weakness,
                "NEW"
            ))
            conn.commit()
            print(f"✅ Successfully inserted Test Lead for {args.clinic} with phone {clean_phone} into DB.")
            print("You can now run: python sales_engine.py --process")
    except Exception as e:
        print(f"❌ Error inserting lead into DB: {e}")

if __name__ == "__main__":
    main()
