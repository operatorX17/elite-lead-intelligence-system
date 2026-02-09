from src.tools.steel import SteelClient
print("Testing Steel...")
client = SteelClient()
print("Client created")
result = client.scrape("https://example.com", screenshot=False, extract_html=True)
print(f"Success! HTML: {len(result.get('html', ''))} chars")
