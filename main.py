import requests
import time
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup

# ================= CONFIG =================

BOT_TOKEN = "8444717416:AAGSTPQnuwMd1vfn_C3kyAHrGu59AgNH5Xk"
CHAT_ID = "1460560636"

EMAIL_FILE = "emails.txt"
SEEN_FILE = "seen.json"
SUBJECT_FILE = "subjects.txt"   # file chứa danh sách keyword subject

ACCOUNT_DELAY = 0.3
CHECK_INTERVAL = 5

API_URL = "https://tools.dongvanfb.net/api/get_messages_oauth2"

# Telegram message limit
TELEGRAM_LIMIT = 4096
MAIL_CONTENT_LIMIT = 3500

# ==========================================


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ================= TELEGRAM =================

def send(msg):
    msg = msg[:TELEGRAM_LIMIT]

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    while True:
        try:
            r = requests.post(
                url,
                json={
                    "chat_id": CHAT_ID,
                    "text": msg
                },
                timeout=20
            )

            if r.status_code == 200:
                return

            if r.status_code == 429:
                data = r.json()
                wait = data["parameters"]["retry_after"]
                log(f"Telegram rate limit → wait {wait}s")
                time.sleep(wait)
            else:
                log(f"Telegram error {r.status_code}")
                return

        except Exception as e:
            log(f"Telegram exception {e}")
            time.sleep(3)


# ================= SEEN MAIL =================

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except:
        return set()


def save_seen(seen):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen), f, ensure_ascii=False)
    except:
        pass


# ================= LOAD EMAIL =================

def load_emails():
    accounts = []

    if not os.path.exists(EMAIL_FILE):
        log("emails.txt not found")
        return accounts

    with open(EMAIL_FILE, "r", encoding="utf-8") as f:
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


# ================= LOAD SUBJECT RULES =================

def load_subject_keywords():
    keywords = []

    if not os.path.exists(SUBJECT_FILE):
        log(f"{SUBJECT_FILE} not found")
        return keywords

    try:
        with open(SUBJECT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                kw = line.strip()
                if kw:
                    keywords.append(kw.lower())
    except Exception as e:
        log(f"Load {SUBJECT_FILE} error: {e}")

    return keywords


def should_send_full_content(subject, keywords):
    subject_lower = (subject or "").lower()

    for kw in keywords:
        if kw in subject_lower:
            return True

    return False


# ================= API =================

def get_messages(email_addr, refresh_token, client_id):
    payload = {
        "email": email_addr,
        "refresh_token": refresh_token,
        "client_id": client_id
    }

    for _ in range(3):
        try:
            r = requests.post(API_URL, json=payload, timeout=25)

            if r.status_code == 200:
                try:
                    return r.json()
                except:
                    return None

            time.sleep(2)

        except:
            time.sleep(2)

    return None


# ================= CLEAN TEXT =================

def clean_text(text):
    return str(text).encode("utf-8", "ignore").decode("utf-8")


# ================= PARSE MAIL =================

def parse_mail_content(mail):
    html = (
        mail.get("message")
        or mail.get("body")
        or mail.get("content")
        or mail.get("text")
        or mail.get("snippet")
        or ""
    )

    if not html:
        return "No content"

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    clean = "\n".join(lines)
    clean = clean_text(clean)

    return clean[:MAIL_CONTENT_LIMIT]


# ================= CHECK ACCOUNT =================

def check_account(account, seen, subject_keywords):
    email_addr, refresh_token, client_id = account

    data = get_messages(email_addr, refresh_token, client_id)

    if not data:
        log(f"No API response {email_addr}")
        return

    messages = data.get("messages")

    if not messages:
        return

    mail = messages[0]

    subject = clean_text(mail.get("subject") or "No subject")
    body = parse_mail_content(mail)

    message_id = mail.get("id") or (subject + body)
    key = email_addr + str(message_id)

    if key in seen:
        return

    seen.add(key)

    send_full = should_send_full_content(subject, subject_keywords)

    if send_full:
        msg = f"""
📩 NEW MAIL

📧 Email:
{email_addr}

📌 Subject:
{subject}

📄 Content:
{body}
"""
        log(f"NEW MAIL FULL → {email_addr} | {subject}")
    else:
        msg = f"""
📩 NEW MAIL

📧 Email:
{email_addr}

📌 Subject:
{subject}
"""
        log(f"NEW MAIL SUBJECT ONLY → {email_addr} | {subject}")

    send(msg)


# ================= MAIN =================

def main():
    log("MAIL BOT STARTED")
    send("MAIL BOT STARTED")

    seen = load_seen()

    while True:
        try:
            accounts = load_emails()
            subject_keywords = load_subject_keywords()

            log(f"Scanning {len(accounts)} accounts | Subject rules: {len(subject_keywords)}")

            for acc in accounts:
                check_account(acc, seen, subject_keywords)
                time.sleep(ACCOUNT_DELAY)

            save_seen(seen)
            log("Scan finished")

        except Exception as e:
            log(f"Main error {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
