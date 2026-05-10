from src.tools.steel import SteelClient
import json

client = SteelClient()
print("Testing Steel scrape...")

result = client.scrape("https://example.com", screenshot=True, extract_html=True)
print(f"HTML length: {len(result.get('html', ''))}")
print(f"Has screenshot: {bool(result.get('screenshot'))}")
print("✅ Steel is working!")
