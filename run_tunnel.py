import subprocess
import re
import time

print('Starting Cloudflared Tunnel...')
p = subprocess.Popen(['cloudflared', 'tunnel', '--url', 'http://localhost:8000'], stderr=subprocess.PIPE, stdout=subprocess.PIPE)

url = None
start = time.time()
while time.time() - start < 15:
    line = p.stderr.readline().decode('utf-8', errors='ignore')
    print("DEBUG:", line.strip())
    if 'trycloudflare.com' in line:
        matches = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
        if matches:
            url = matches[-1]
            break

if url:
    print('==============================')
    print('WEBHOOK URL: ' + url + '/webhook/whatsapp')
    print('==============================')
    # Loop to keep tunnel alive
    while True:
        time.sleep(10)
else:
    print('Failed to get URL within 15s.')
    p.terminate()
