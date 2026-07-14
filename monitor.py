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

        page.wait_for_selector("table tbody tr", timeout=120000)

        rows = page.locator("table tbody tr")

        count = rows.count()

        print(f"Found rows: {count}")

        for i in range(count):

            row = rows.nth(i)

            text = row.inner_text().strip()

            if not text:
                continue

            columns = [
                c.strip()
                for c in text.split("\n")
                if c.strip()
            ]

            # 跳过标题行
            if len(columns) < 3:
                continue


            # -------------------------
            # 第一列:
            # EN 18274:2026 (WI=JT021019)
            # -------------------------

            project_line = columns[0]

            if "(WI=" not in project_line:
                continue

            wi = (
                project_line
                .split("(WI=")[1]
                .split(")")[0]
                .strip()
            )

            project = (
                project_line
                .split("(WI=")[0]
                .strip()
            )


            # -------------------------
            # 第二列:
            # Item Name
            # -------------------------

            item_name = columns[1]


            # -------------------------
            # 第三列:
            # Approved\tdate\tdate...
            # -------------------------

            status_line = columns[2]

            status = (
                status_line
                .split("\t")[0]
                .strip()
            )


            results[wi] = {
                "project": project,
                "name": item_name,
                "status": status,
            }


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

    for key in sorted(all_keys):

        old_item = old.get(key)
        new_item = new.get(key)

        old_status = old_item["status"] if old_item else None
        new_status = new_item["status"] if new_item else None

        if old_status != new_status:

            item = new_item if new_item else old_item

            changes.append({
                "wi": key,
                "project": item.get("project", ""),
                "name": item.get("name", ""),
                "old_status": old_status,
                "new_status": new_status,
            })

    return changes


# 发送邮件
def send_email(changes):

    resend_api_key = os.environ["RESEND_API_KEY"]

    to_emails = [
        email.strip()
        for email in os.environ["TO_EMAILS"].split(",")
        if email.strip()
    ]

    html = """
    <h2>CEN/CLC/JTC 21 Status Changes</h2>
    """

    for change in changes:

        html += f"""
        <hr>

        <table style="border-collapse:collapse;">

            <tr>
                <td style="padding:4px 10px;"><strong>WI</strong></td>
                <td>{change["wi"]}</td>
            </tr>

            <tr>
                <td style="padding:4px 10px;"><strong>Project</strong></td>
                <td>{change["project"]}</td>
            </tr>

            <tr>
                <td style="padding:4px 10px;"><strong>Name</strong></td>
                <td>{change["name"]}</td>
            </tr>

            <tr>
                <td style="padding:4px 10px;"><strong>Old Status</strong></td>
                <td>{change["old_status"]}</td>
            </tr>

            <tr>
                <td style="padding:4px 10px;"><strong>New Status</strong></td>
                <td>
                    <span style="color:red;font-weight:bold;">
                        {change["new_status"]}
                    </span>
                </td>
            </tr>

        </table>
        """

    html += f"""
    <br><br>
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

    print("Email response:", response.status_code)
    print(response.text)

    response.raise_for_status()


# 主程序
def main():

    current_statuses = get_current_statuses()

    print("\n========== Current Statuses ==========")
    print(json.dumps(current_statuses, indent=2, ensure_ascii=False))

    old_statuses = load_old_statuses()

    changes = compare_statuses(old_statuses, current_statuses)

    # 第一次运行
    if not old_statuses:

        print("\nFirst run.")
        print("Saving initial status file...")

        save_statuses(current_statuses)

        return

    # 有变化
    if changes:

        print("\n========== Changes Detected ==========")

        for change in changes:

            print(
                f"[{change['wi']}] "
                f"{change['project']}\n"
                f"Status: {change['old_status']} -> {change['new_status']}\n"
            )

        send_email(changes)

        save_statuses(current_statuses)

        print("Status file updated.")

    # 无变化
    else:

        print("\nNo changes detected.")
        

if __name__ == "__main__":
    main()
