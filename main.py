import requests
import time

BOT_TOKEN = "8444717416:AAGSTPQnuwMd1vfn_C3kyAHrGu59AgNH5Xk"
CHAT_ID = "1460560636"

def send(msg):

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": msg
        }
    )


def get_mail(email, refresh_token, client_id):

    url = "https://tools.dongvanfb.net/api/get_messages_oauth2"

    data = {
        "email": email,
        "refresh_token": refresh_token,
        "client_id": client_id
    }

    r = requests.post(url, json=data, timeout=30)

    return r.json()


def check(email, refresh_token, client_id):

    res = get_mail(email, refresh_token, client_id)

    if not res:
        return

    if "messages" not in res:
        return

    for mail in res["messages"]:

        subject = mail.get("subject")

        send(f"""
📩 NEW MAIL

Email: {email}
Subject: {subject}
""")


def main():

    email = "yourmail@hotmail.com"
    refresh_token = "REFRESH"
    client_id = "CLIENT"

    while True:

        check(email, refresh_token, client_id)

        time.sleep(10)


if __name__ == "__main__":
    main()
