import os
import json
import requests
from playwright.sync_api import sync_playwright

URL = "https://standards.cencenelec.eu/ords/f?p=205:22:::::FSP_ORG_ID,FSP_LANG_ID:2916257,25&cs=114251C6C0B684FBBC069923513BF6348"

STATUS_FILE = "last_status.json"


# 提取表格中的 status
def get_current_statuses():
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        page.goto(URL, wait_until="networkidle", timeout=120000)

        page.wait_for_timeout(8000)

        # 获取所有表格行
        rows = page.locator("table tr")

        count = rows.count()

        print(f"Found rows: {count}")

        status_candidates = [
            "Preliminary",
            "Under Drafting",
            "Under Approval",
            "Under Enquiry",
            "Published",
            "Withdrawn",
        ]

        for i in range(count):
            row = rows.nth(i)

            text = row.inner_text().strip()

            if not text:
                continue

            columns = [c.strip() for c in text.split("\n") if c.strip()]

            if len(columns) < 2:
                continue

            work_item = columns[0]

            detected_status = None

            for col in columns:
                for status in status_candidates:
                    if status.lower() in col.lower():
                        detected_status = status
                        break

                if detected_status:
                    break

            if detected_status:
                results[work_item] = detected_status

        browser.close()

    return results


# 读取历史状态
def load_old_statuses():
    if not os.path.exists(STATUS_FILE):
        return {}

    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# 保存状态
def save_statuses(statuses):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(statuses, f, indent=2, ensure_ascii=False)


# 对比变化
def compare_statuses(old, new):
    changes = []

    all_keys = set(old.keys()) | set(new.keys())

    for key in all_keys:
        old_status = old.get(key)
        new_status = new.get(key)

        if old_status != new_status:
            changes.append((key, old_status, new_status))

    return changes


# 发送邮件
def send_email(changes):
    resend_api_key = os.environ["RESEND_API_KEY"]

    to_emails = os.environ["TO_EMAILS"].split(",")
    
    html = "<h2>CEN/CLC/JTC 21 Status Changes</h2>"

    for item, old_status, new_status in changes:
        html += f"""
        <hr>
        <p><strong>Item:</strong> {item}</p>
        <p><strong>Old:</strong> {old_status}</p>
        <p><strong>New:</strong> {new_status}</p>
        """

    html += f"""
    <br>
    <a href="{URL}">Open Standards Page</a>
    """

    payload = {
        "from": "AI Standards Monitor <onboarding@resend.dev>",
        "to": to_emails,
        "subject": "[AI Standards Alert] Status Changed",
        "html": html,
    }

    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        "https://api.resend.com/emails",
        headers=headers,
        json=payload,
    )

    print(response.status_code)
    print(response.text)


# 主程序
def main():
    current_statuses = get_current_statuses()

    print("Current statuses:")
    print(json.dumps(current_statuses, indent=2, ensure_ascii=False))

    old_statuses = load_old_statuses()

    changes = compare_statuses(old_statuses, current_statuses)

#    if changes:
#        print("Changes detected:")
#
#        for c in changes:
#            print(c)
#
#        send_email(changes)
#
#        save_statuses(current_statuses)
#
#    else:
#        print("No changes")
    if old_statuses and changes:
        print("Changes detected:")

        for c in changes:
            print(c)

        send_email(changes)

        save_statuses(current_statuses)

    elif not old_statuses:
        print("First run, saving initial statuses only")

        save_statuses(current_statuses)

else:
    print("No changes")

if __name__ == "__main__":
    main()
