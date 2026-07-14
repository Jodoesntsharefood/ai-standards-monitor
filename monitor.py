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

        page.goto(
            URL,
            wait_until="networkidle",
            timeout=120000
        )

        page.wait_for_timeout(5000)

        # 等待表格数据真正出现
        page.wait_for_selector(
            "table tbody tr",
            timeout=120000
        )
        tables = page.locator("table")

        print("Total tables:", tables.count())

        for i in range(tables.count()):
            print("======== TABLE", i, "========")
            print(tables.nth(i).inner_text()[:300])
            
        # 找到真正的数据表
        table = page.locator("table").filter(
            has=page.locator("th:text('Status')")
        ).first

        rows = table.locator("tbody tr")

        print(f"Found rows: {rows.count()}")

        status_candidates = [
            "Preliminary",
            "Under Drafting",
            "Under Approval",
            "Under Enquiry",
            "Published",
            "Withdrawn",
            "Approved",
        ]

        for i in range(rows.count()):

            row = rows.nth(i)

            tds = row.locator("td")

            if tds.count() < 2:
                continue

            # -----------------------------
            # 第一列(Project)
            # -----------------------------
            first_text = first_cell = tds.nth(0).inner_text()

            lines = [
                x.strip()
                for x in first_text.split("\n")
                if x.strip()
            ]

            if len(lines) < 3:
                continue

            project = lines[0]

            wi = lines[1]
            wi = wi.replace("(WI=", "").replace(")", "").strip()

            name = " ".join(lines[2:])

            # -----------------------------
            # Status
            # -----------------------------
            status = tds.nth(1).inner_text().strip()

            for s in status_candidates:
                if s.lower() in status.lower():
                    status = s
                    break

            results[wi] = {
                "project": project,
                "wi": wi,
                "name": name,
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
                "wi": item.get("wi", ""),
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
                <td style="padding:4px 12px;"><strong>Project</strong></td>
                <td>{change["project"]}</td>
            </tr>

            <tr>
                <td style="padding:4px 12px;"><strong>WI</strong></td>
                <td>{change["wi"]}</td>
            </tr>

            <tr>
                <td style="padding:4px 12px;"><strong>Name</strong></td>
                <td>{change["name"]}</td>
            </tr>

            <tr>
                <td style="padding:4px 12px;"><strong>Old Status</strong></td>
                <td>{change["old_status"]}</td>
            </tr>

            <tr>
                <td style="padding:4px 12px;"><strong>New Status</strong></td>
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

    <a href="{URL}">
        Open CEN Work Programme
    </a>
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
            print(
                f"[{c['wi']}] "
                f"{c['project']} | "
                f"{c['old_status']} -> {c['new_status']}"
            )

        send_email(changes)

        save_statuses(current_statuses)

    elif not old_statuses:
        print("First run, saving initial statuses only")

        save_statuses(current_statuses)

    else:
        print("No changes")

        

if __name__ == "__main__":
    main()
