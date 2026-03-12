import requests
import time
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

BOT_TOKEN = "8444717416:AAGSTPQnuwMd1vfn_C3kyAHrGu59AgNH5Xk"
CHAT_ID = "1460560636"

EMAIL_FILE = "emails.txt"
SEEN_FILE = "seen.json"

CHECK_INTERVAL = 20
MAX_THREADS = 5


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg},
            timeout=20
        )
    except:
        pass


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()

    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except:
        return set()


def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)
    except:
        pass


def load_emails():

    accounts = []

    with open(EMAIL_FILE) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            parts = line.split("|")

            if len(parts) < 4:
                continue

            email_addr = parts[0]
            refresh_token = parts[2]
            client_id = parts[3]

            accounts.append((email_addr, refresh_token, client_id))

    return accounts


def get_messages(email_addr, refresh_token, client_id):

    url = "https://tools.dongvanfb.net/api/get_messages_oauth2"

    payload = {
        "email": email_addr,
        "refresh_token": refresh_token,
        "client_id": client_id
    }

    for _ in range(5):

        try:

            r = requests.post(url, json=payload, timeout=25)

            if r.status_code == 200:

                try:
                    return r.json()
                except:
                    return None

            time.sleep(3)

        except:
            time.sleep(3)

    return None


def check_account(account, seen):

    email_addr, refresh_token, client_id = account

    data = get_messages(email_addr, refresh_token, client_id)

    if not data:
        return

    messages = data.get("messages")

    if not messages:
        return

    for mail in messages:

        subject = mail.get("subject")
        message_id = mail.get("id")

        key = email_addr + str(message_id)

        if key in seen:
            continue

        seen.add(key)

        msg = f"""📩 NEW MAIL

Email: {email_addr}
Subject: {subject}
"""

        send(msg)

        log(f"NEW MAIL {email_addr}")


def main():

    log("MAIL BOT STARTED")

    send("MAIL BOT STARTED")

    seen = load_seen()

    while True:

        try:

            accounts = load_emails()

            if accounts:

                with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

                    for acc in accounts:
                        executor.submit(check_account, acc, seen)
                        time.sleep(0.3)

                save_seen(seen)

        except Exception as e:

            log(f"Main error {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
