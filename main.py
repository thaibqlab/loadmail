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
    # đảm bảo message không vượt giới hạn Telegram
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
    """
    Hỗ trợ cả format cũ:
    - list: lưu danh sách key mail đã thấy
    Và format mới:
    - dict: {"message_keys": [...], "subjects": [...]}
    """
    if not os.path.exists(SEEN_FILE):
        return {"message_keys": set(), "subjects": set()}

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return {
                "message_keys": set(data.get("message_keys", [])),
                "subjects": set(data.get("subjects", [])),
            }

        if isinstance(data, list):
            return {
                "message_keys": set(data),
                "subjects": set(),
            }

    except Exception:
        pass

    return {"message_keys": set(), "subjects": set()}


def save_seen(seen):
    try:
        payload = {
            "message_keys": sorted(seen["message_keys"]),
            "subjects": sorted(seen["subjects"]),
        }
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def normalize_subject(subject):
    return " ".join((subject or "").strip().lower().split())


# ================= LOAD EMAIL =================

def load_emails():
    accounts = []

    if not os.path.exists(EMAIL_FILE):
        log("emails.txt not found")
        return accounts

    with open(EMAIL_FILE, encoding="utf-8") as f:
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
                except Exception:
                    return None

            time.sleep(2)

        except Exception:
            time.sleep(2)

    return None


def extract_messages(data):
    """
    Cố gắng lấy toàn bộ mail có trong response API.
    Nếu API thực sự chỉ trả tối đa 10 mail từ server thì script không thể vượt quá giới hạn đó
    nếu không có cơ chế phân trang/token từ API.
    """
    if not data:
        return []

    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]

    if not isinstance(data, dict):
        return []

    candidates = []

    direct_messages = data.get("messages")
    if isinstance(direct_messages, list):
        candidates.extend(x for x in direct_messages if isinstance(x, dict))

    # hỗ trợ một số format response phổ biến khác
    for key in ("data", "items", "results"):
        value = data.get(key)
        if isinstance(value, list):
            candidates.extend(x for x in value if isinstance(x, dict))
        elif isinstance(value, dict):
            inner_messages = value.get("messages")
            if isinstance(inner_messages, list):
                candidates.extend(x for x in inner_messages if isinstance(x, dict))

    # loại trùng theo id nếu có
    unique = []
    seen_ids = set()

    for mail in candidates:
        mail_id = mail.get("id") or mail.get("message_id")
        if mail_id:
            if mail_id in seen_ids:
                continue
            seen_ids.add(mail_id)
        unique.append(mail)

    return unique


# ================= CLEAN TEXT =================

def clean_text(text):
    return text.encode("utf-8", "ignore").decode("utf-8")


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

    # giới hạn nội dung mail
    return clean[:MAIL_CONTENT_LIMIT]


# ================= CHECK ACCOUNT =================

def check_account(account, seen):
    email_addr, refresh_token, client_id = account

    data = get_messages(email_addr, refresh_token, client_id)

    if not data:
        log(f"No API response {email_addr}")
        return

    messages = extract_messages(data)

    if not messages:
        return

    log(f"{email_addr} → API returned {len(messages)} messages")

    new_count = 0
    skipped_duplicate_subject = 0

    for mail in messages:
        subject = clean_text(mail.get("subject") or "No subject")
        body = parse_mail_content(mail)

        message_id = mail.get("id") or mail.get("message_id") or (subject + body)
        message_key = email_addr + str(message_id)
        subject_key = normalize_subject(subject)

        # đã xử lý mail này rồi
        if message_key in seen["message_keys"]:
            continue

        # đánh dấu mail đã quét để lần sau không xử lý lại
        seen["message_keys"].add(message_key)

        # nếu tiêu đề đã từng lưu thì bỏ qua gửi thông báo
        if subject_key in seen["subjects"]:
            skipped_duplicate_subject += 1
            continue

        # lưu tiêu đề ngay khi phát hiện mail mới để lần quét sau không gửi lại
        seen["subjects"].add(subject_key)

        msg = f"""
📩 NEW MAIL

📧 Email:
{email_addr}

📌 Subject:
{subject}

📄 Content:
{body}
"""

        log(f"NEW MAIL → {email_addr} | {subject}")
        send(msg)
        new_count += 1

    if skipped_duplicate_subject:
        log(f"{email_addr} → skipped {skipped_duplicate_subject} duplicate subject(s)")
    if new_count:
        log(f"{email_addr} → sent {new_count} notification(s)")


# ================= MAIN =================

def main():
    log("MAIL BOT STARTED")
    send("MAIL BOT STARTED")

    seen = load_seen()

    while True:
        try:
            accounts = load_emails()

            log(f"Scanning {len(accounts)} accounts")

            for acc in accounts:
                check_account(acc, seen)
                time.sleep(ACCOUNT_DELAY)

            save_seen(seen)
            log("Scan finished")

        except Exception as e:
            log(f"Main error {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
