import subprocess
import re
import time

print("Starting cloudflared...")
proc = subprocess.Popen(["cloudflared", "tunnel", "--url", "http://127.0.0.1:8000"], stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", shell=True)

found = False
for line in proc.stderr:
    print("LOG:", line.strip())
    match = re.search(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', line)
    if match:
        url = match.group(1)
        print("\n" + "="*50)
        print("BINGO! THE CLOUDFLARE URL IS:")
        print(url)
        print("="*50 + "\n")
        with open("CF_EXACT_URL.txt", "w") as f:
            f.write(url)
        found = True
        break

if not found:
    print("Could not find URL stream.")
