"""Check what Apify actually returned"""
from apify_client import ApifyClient
import os
import json

client = ApifyClient(os.getenv('APIFY_API_TOKEN'))

# Get the run
run_id = 'Bz8etQVAyGJ3AWk5y'
run = client.run(run_id).get()

# Get dataset
dataset = client.dataset(run['defaultDatasetId'])
items = list(dataset.iterate_items())

if items:
    item = items[0]
    
    print("=" * 80)
    print("ACTUAL APIFY OUTPUT - ALL FIELDS")
    print("=" * 80)
    print("\nFields returned:")
    for key in sorted(item.keys()):
        print(f"  - {key}")
    
    print("\n" + "=" * 80)
    print("VOLUME-RELATED FIELDS")
    print("=" * 80)
    
    volume_fields = [
        'totalScore', 'reviewsCount', 'rating', 'reviews',
        'openingHours', 'peopleAlsoSearch', 'imageCategories',
        'popularTimesHistogram', 'peopleTypicallySpendHere',
        'reviewsDistribution', 'questionsAndAnswers'
    ]
    
    for field in volume_fields:
        value = item.get(field)
        if value is not None:
            if isinstance(value, (dict, list)):
                print(f"\n✅ {field}: {type(value).__name__} with {len(value)} items")
                if isinstance(value, dict) and len(value) < 10:
                    print(f"   {json.dumps(value, indent=2)[:200]}")
                elif isinstance(value, list) and len(value) > 0:
                    print(f"   First item: {json.dumps(value[0], indent=2, default=str)[:200]}")
            else:
                print(f"\n✅ {field}: {value}")
        else:
            print(f"\n❌ {field}: NOT RETURNED")
    
    print("\n" + "=" * 80)
    print("FULL ITEM (first 3000 chars)")
    print("=" * 80)
    print(json.dumps(item, indent=2, default=str)[:3000])
