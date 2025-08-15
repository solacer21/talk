# -*- coding: utf-8 -*-
import os, time, requests, sys
from dotenv import load_dotenv
import os, time, requests, sys
from dotenv import load_dotenv

load_dotenv()
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
if not CHANNEL_ACCESS_TOKEN:
    print("ERROR: LINE_CHANNEL_ACCESS_TOKEN is missing in .env")
    sys.exit(1)

def get_ngrok_https(loop_seconds=30, retries=30):
    api = "http://127.0.0.1:4040/api/tunnels"
    for _ in range(retries):
        try:
            j = requests.get(api, timeout=5).json()
            for t in j.get("tunnels", []):
                if t.get("proto") == "https":
                    return t.get("public_url")
        except Exception:
            pass
        time.sleep(loop_seconds / max(retries, 1))
    return None

def set_webhook(url: str):
    endpoint = "https://api.line.me/v2/bot/channel/webhook/endpoint"
    headers = {"Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}", "Content-Type": "application/json"}
    body = {"endpoint": url}
    r = requests.put(endpoint, headers=headers, json=body, timeout=30)
    if r.status_code not in (200, 201):
        print("Set webhook failed:", r.status_code, r.text)
        sys.exit(2)
    print("Set webhook OK:", url)

    # 可選驗證：有些帳號會回 404，不影響實作；只做提示不報錯
    try:
        ver = requests.post("https://api.line.me/v2/bot/channel/webhook/verify",
                            headers=headers, json={"endpoint": url}, timeout=30)
        print("Verify (non-blocking):", ver.status_code, ver.text)
    except Exception as e:
        print("Verify skipped due to error:", e)

def main():
    https_url = get_ngrok_https()
    if not https_url:
        print("ERROR: Cannot find ngrok https tunnel. Is ngrok running?")
        sys.exit(1)
    full = https_url.rstrip("/") + "/callback"
    set_webhook(full)

if __name__ == "__main__":
    main()
