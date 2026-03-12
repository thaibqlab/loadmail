import imaplib
import email
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

CHECK_INTERVAL = 10
MAX_THREADS = 20


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# TELEGRAM
def send(msg):

    try:

        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": msg
            },
            timeout=20
        )

        if r.status_code != 200:
            log(f"Telegram error {r.text}")

    except Exception as e:
        log(f"Telegram exception {e}")


# LOAD SEEN
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

    except Exception as e:
        log(f"Save seen error {e}")


# TOKEN
def get_access_token(refresh, client_id):

    url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

    data = {
        "client_id": client_id,
        "refresh_token": refresh,
        "grant_type": "refresh_token",
        "scope": "https://outlook.office365.com/.default"
    }

    try:

        r = requests.post(url, data=data, timeout=20)

        j = r.json()

        token = j.get("access_token")

        if not token:
            log(f"Token error {j}")

        return token

    except Exception as e:

        log(f"Token error {e}")
        return None


# IMAP LOGIN
def imap_login(email_addr, access_token):

    try:

        auth_string = f"user={email_addr}\1auth=Bearer {access_token}\1\1"

        imap = imaplib.IMAP4_SSL("imap-mail.outlook.com")

        imap.authenticate("XOAUTH2", lambda x: auth_string.encode())

        return imap

    except Exception as e:

        log(f"IMAP login error {email_addr} {e}")
        return None


# GET MAIL
def get_unseen_email(imap):

    try:

        imap.select("inbox")

        status, messages = imap.search(None, "UNSEEN")

        ids = messages[0].split()

        if not ids:
            return None, None

        latest = ids[-1]

        status, data = imap.fetch(latest, "(RFC822)")

        raw = data[0][1]

        msg = email.message_from_bytes(raw)

        subject = msg["Subject"] or "(No Subject)"

        message_id = msg["Message-ID"]

        return subject, message_id

    except Exception as e:

        log(f"Read mail error {e}")
        return None, None


# LOAD EMAIL LIST
def load_emails():

    accounts = []

    try:

        with open(EMAIL_FILE) as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                parts = line.split("|")

                if len(parts) < 4:
                    log(f"Bad format {line}")
                    continue

                email_addr = parts[0]
                refresh = parts[2]
                client_id = parts[3]

                accounts.append((email_addr, refresh, client_id))

    except Exception as e:

        log(f"Load email error {e}")

    return accounts


# CHECK ACCOUNT
def check_account(account, seen):

    email_addr, refresh, client_id = account

    try:

        log(f"Checking {email_addr}")

        token = get_access_token(refresh, client_id)

        if not token:
            return

        imap = imap_login(email_addr, token)

        if not imap:
            return

        subject, message_id = get_unseen_email(imap)

        imap.logout()

        if not subject:
            return

        key = email_addr + str(message_id)

        if key in seen:
            return

        seen.add(key)

        msg = f"""📩 NEW MAIL

Email: {email_addr}
Subject: {subject}
"""

        send(msg)

        log(f"NEW MAIL {email_addr}")

    except Exception as e:

        log(f"Account error {email_addr} {e}")


# MAIN LOOP
def main():

    log("MAIL BOT STARTED")

    send("MAIL BOT STARTED")

    seen = load_seen()

    while True:

        try:

            accounts = load_emails()

            if not accounts:

                log("No accounts")

            else:

                with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

                    for acc in accounts:
                        executor.submit(check_account, acc, seen)

                save_seen(seen)

        except Exception as e:

            log(f"Main error {e}")

        log(f"Sleep {CHECK_INTERVAL}s")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
