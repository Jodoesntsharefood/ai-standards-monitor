import os
import json
import requests
from playwright.sync_api import sync_playwright

URL = "https://standards.cencenelec.eu/ords/f?p=205:22::::::&cs=117B8E8682150D42818988EEE05C945D6"

TARGET_TEXT = "CEN/CLC/JTC 21 - Artificial Intelligence"

STATUS_FILE = "last_status.txt"


def get_current_status():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        page.goto(URL, wait_until="networkidle", timeout=120000)

        page.wait_for_timeout(5000)

        body_text = page.inner_text("body")

        browser.close()

    lines = body_text.splitlines()

    found_target = False

    for line in lines:
        if TARGET_TEXT in line:
            found_target = True

        if found_target and "status" in line.lower():
            return line.strip()

    return "STATUS_NOT_FOUND"


def load_old_status():
    if not os.path.exists(STATUS_FILE):
        return ""

    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_status(status):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(status)


def send_email(old_status, new_status):
    resend_api_key = os.environ["RESEND_API_KEY"]

    to_email = os.environ["TO_EMAIL"]

    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "from": "AI Standards Monitor <onboarding@resend.dev>",
        "to": [to_email],
        "subject": "[AI Standards Alert] Status Changed",
        "html": f"""
        <h2>CEN/CLC/JTC 21 - Artificial Intelligence</h2>

        <p>Status changed detected.</p>

        <p><strong>Old Status:</strong><br>{old_status}</p>

        <p><strong>New Status:</strong><br>{new_status}</p>

        <p>
        <a href="{URL}">Open Standards Page</a>
        </p>
        """
    }

    response = requests.post(
        "https://api.resend.com/emails",
        headers=headers,
        data=json.dumps(payload)
    )

    print(response.status_code)
    print(response.text)


def main():
    current_status = get_current_status()

    print("Current:", current_status)

    old_status = load_old_status()

    print("Old:", old_status)

    if current_status != old_status:
        print("Status changed")

        send_email(old_status, current_status)

        save_status(current_status)

    else:
        print("No change")


if __name__ == "__main__":
    main()
