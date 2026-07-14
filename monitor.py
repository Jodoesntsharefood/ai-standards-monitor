import os
import json
import requests
from bs4 import BeautifulSoup


URL = "https://standards.cencenelec.eu/ords/f?p=205:22:::::FSP_ORG_ID,FSP_LANG_ID:2916257,25&cs=114251C6C0B684FBBC069923513BF6348"

STATUS_FILE = "last_status.json"


# =====================================================
# 使用 requests 获取网页并解析状态
# =====================================================

def get_current_statuses():

    results = {}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120 Safari/537.36"
        )
    }


    try:
        response = requests.get(
            URL,
            headers=headers,
            timeout=60
        )

        response.raise_for_status()

    except Exception as e:
        print("Failed to download page:")
        print(e)
        return results


    html = response.text

    print("HTML length:", len(html))


    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    status_candidates = [
        "Preliminary",
        "Under Drafting",
        "Under Approval",
        "Under Enquiry",
        "Published",
        "Withdrawn",
        "Approved",
    ]


    # -------------------------------------------------
    # 找数据表
    # -------------------------------------------------

    tables = soup.find_all("table")

    print("Tables found:", len(tables))


    target_table = None


    for table in tables:

        text = table.get_text(
            " ",
            strip=True
        )

        # 数据表通常包含 WI 和 Status
        if "(WI=" in text and "Status" in text:
            target_table = table
            break


    if target_table is None:

        print(
            "Cannot find target table"
        )

        return results



    rows = target_table.find_all("tr")


    print(
        "Rows found:",
        len(rows)
    )


    # -------------------------------------------------
    # 解析每一行
    # -------------------------------------------------

    for row in rows:

        cells = row.find_all("td")


        if len(cells) < 2:
            continue


        first_text = cells[0].get_text(
            "\n",
            strip=True
        )


        lines = [
            x.strip()
            for x in first_text.split("\n")
            if x.strip()
        ]


        if len(lines) < 3:
            continue



        project = lines[0]


        wi = lines[1]

        wi = (
            wi
            .replace("(WI=", "")
            .replace(")", "")
            .strip()
        )


        name = " ".join(
            lines[2:]
        )



        status = cells[1].get_text(
            " ",
            strip=True
        )


        normalized_status = status


        for s in status_candidates:

            if s.lower() in status.lower():

                normalized_status = s
                break



        results[wi] = {

            "project": project,

            "wi": wi,

            "name": name,

            "status": normalized_status,

        }



    print(
        "Collected records:",
        len(results)
    )


    return results




# =====================================================
# 读取历史状态
# =====================================================

def load_old_statuses():

    if not os.path.exists(
        STATUS_FILE
    ):
        return {}


    try:

        with open(
            STATUS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)


    except Exception:

        return {}




# =====================================================
# 保存状态
# =====================================================

def save_statuses(statuses):

    with open(
        STATUS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            statuses,
            f,
            indent=2,
            ensure_ascii=False
        )


    print(
        "Status saved:",
        len(statuses)
    )
# =====================================================
# 比较状态变化
# =====================================================

def compare_statuses(old, new):

    changes = []


    all_keys = set(old.keys()) | set(new.keys())


    for key in sorted(all_keys):

        old_item = old.get(key)

        new_item = new.get(key)


        old_status = (
            old_item.get("status")
            if old_item
            else None
        )


        new_status = (
            new_item.get("status")
            if new_item
            else None
        )


        if old_status != new_status:

            item = (
                new_item
                if new_item
                else old_item
            )


            changes.append({

                "wi": item.get("wi", ""),

                "project": item.get(
                    "project",
                    ""
                ),

                "name": item.get(
                    "name",
                    ""
                ),

                "old_status": old_status,

                "new_status": new_status,

            })


    return changes




# =====================================================
# 发送邮件
# =====================================================

def send_email(changes):

    resend_api_key = os.environ.get(
        "RESEND_API_KEY"
    )


    to_emails = [

        email.strip()

        for email in os.environ.get(
            "TO_EMAILS",
            ""
        ).split(",")

        if email.strip()

    ]


    if not resend_api_key:

        print(
            "Missing RESEND_API_KEY"
        )

        return



    html = """
    <h2>
    CEN/CLC/JTC 21 Status Changes
    </h2>
    """



    for change in changes:


        html += f"""

        <hr>

        <table 
        style="border-collapse:collapse;">

        <tr>
        <td style="padding:4px 12px;">
        <strong>Project</strong>
        </td>
        <td>
        {change["project"]}
        </td>
        </tr>


        <tr>
        <td style="padding:4px 12px;">
        <strong>WI</strong>
        </td>
        <td>
        {change["wi"]}
        </td>
        </tr>


        <tr>
        <td style="padding:4px 12px;">
        <strong>Name</strong>
        </td>
        <td>
        {change["name"]}
        </td>
        </tr>


        <tr>
        <td style="padding:4px 12px;">
        <strong>Old Status</strong>
        </td>
        <td>
        {change["old_status"]}
        </td>
        </tr>


        <tr>
        <td style="padding:4px 12px;">
        <strong>New Status</strong>
        </td>

        <td>
        <span style="
        color:red;
        font-weight:bold;
        ">
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

        "from":
        "AI Standards Monitor <onboarding@resend.dev>",


        "to":
        to_emails,


        "subject":
        "[AI Standards Alert] Status Changed",


        "html":
        html,

    }



    headers = {

        "Authorization":
        f"Bearer {resend_api_key}",


        "Content-Type":
        "application/json",

    }



    try:

        response = requests.post(

            "https://api.resend.com/emails",

            headers=headers,

            json=payload,

            timeout=30

        )


        print(
            "Email status:",
            response.status_code
        )


        print(
            response.text
        )


    except Exception as e:

        print(
            "Email failed:"
        )

        print(e)





# =====================================================
# 主程序
# =====================================================

def main():


    print(
        "Starting monitor..."
    )


    current_statuses = get_current_statuses()


    print(
        "Current records:",
        len(current_statuses)
    )



    old_statuses = load_old_statuses()



    changes = compare_statuses(
        old_statuses,
        current_statuses
    )



    print(
        "Changes:",
        len(changes)
    )



    # 第一次运行
    if not old_statuses:


        print(
            "First run, saving baseline"
        )


        save_statuses(
            current_statuses
        )


        return




    # 有变化

    if changes:


        print(
            "Changes detected:"
        )


        for c in changes:

            print(
                f"{c['wi']} "
                f"{c['old_status']} "
                f"-> "
                f"{c['new_status']}"
            )



        send_email(
            changes
        )



        save_statuses(
            current_statuses
        )


    else:


        print(
            "No changes"
        )





if __name__ == "__main__":

    main()
