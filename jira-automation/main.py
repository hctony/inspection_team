import argparse
import os

from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import schedule
import time

# ==============================
# Jira 설정
# ==============================

load_dotenv()


def require_env(key):

    value = os.environ.get(key)

    if not value:
        raise RuntimeError(f"환경 변수 {key}가 설정되어야 합니다.")

    return value


EMAIL = require_env("JIRA_EMAIL")
API_TOKEN = require_env("JIRA_API_TOKEN")
SITE = require_env("JIRA_SITE")
PROJECT = os.environ.get("JIRA_PROJECT_KEY", "DMT")
REPORT_STATUS = os.environ.get("JIRA_REPORT_STATUS", "업무 일보")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
COMPLETE_STATUSES = {"완료", "Done"}
PROGRESS_STATUSES = {"진행 중", "In Progress"}
PLANNED_STATUSES = {"검사기술팀 예정업무", "타부서 요청건"}
DEFAULT_STATUS_EMOJI = "▪️"
STATUS_EMOJI_PREFIXES = [
    "🟢",
    "⚠️",
    "📅",
    "🟡",
    "🔄",
    "✅",
    "🗓️",
    DEFAULT_STATUS_EMOJI,
]
INCLUDED_STATUSES = COMPLETE_STATUSES | PROGRESS_STATUSES

auth = HTTPBasicAuth(EMAIL, API_TOKEN)

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}


def _resolve_timeout(default: int = 10) -> int:
    env_value = os.environ.get("HTTP_TIMEOUT_SECONDS")
    if not env_value:
        return default

    try:
        parsed = int(env_value)
        return parsed if parsed > 0 else default
    except ValueError:
        return default


REQUEST_TIMEOUT_SECONDS = _resolve_timeout()


def safe_request(method: str, url: str, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT_SECONDS)

    try:
        return requests.request(method=method.lower(), url=url, timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        print(f"HTTP 요청 실패: {method.upper()} {url} - {exc}")
        return None


def notify_slack(message):

    if not SLACK_WEBHOOK_URL or not message:
        return

    payload = {"text": message}

    resp = safe_request("post", SLACK_WEBHOOK_URL, json=payload)

    if resp is None:
        return

    if not resp.ok:
        print("Slack 알림 실패", resp.status_code, resp.text)


def text_to_adf(text):

    lines = text.splitlines()

    content = []

    for line in lines:

        paragraph = {"type": "paragraph", "content": []}

        if line:
            paragraph["content"].append({"type": "text", "text": line})

        content.append(paragraph)

    if not content:
        content = [{"type": "paragraph", "content": []}]

    return {
        "type": "doc",
        "version": 1,
        "content": content
    }


def adf_to_text(doc):

    if not isinstance(doc, dict) or doc.get("type") != "doc":
        return ""

    lines = []

    for node in doc.get("content", []):

        if node.get("type") != "paragraph":
            continue

        text_fragments = []

        for child in node.get("content", []):
            if child.get("type") == "text":
                text_fragments.append(child.get("text", ""))

        lines.append("".join(text_fragments))

    return "\n".join(lines)


def get_status_emoji(status):

    if status in COMPLETE_STATUSES:
        return "🟢"

    if status in PROGRESS_STATUSES:
        return "⚠️"

    if status in PLANNED_STATUSES:
        return "📅"

    return DEFAULT_STATUS_EMOJI


def log_jira_error(response, prefix):
    print(prefix, response.status_code)
    try:
        print(response.json())
    except ValueError:
        print(response.text)


def run_jql_search(jql, fields=None, max_results=100):

    url = f"{SITE}/rest/api/3/search/jql"

    issues = []
    next_page_token = None

    while True:

        payload = {
            "jql": jql,
            "maxResults": max_results
        }

        if fields:
            payload["fields"] = fields

        if next_page_token:
            payload["nextPageToken"] = next_page_token

        r = safe_request("post", url, json=payload, headers=headers, auth=auth)

        if r is None:
            print("Jira API ERROR: 요청 자체가 실패했습니다.")
            break

        if not r.ok:
            log_jira_error(r, "Jira API ERROR")
            break

        data = r.json()

        issues.extend(data.get("issues", []))

        next_page_token = data.get("nextPageToken")

        if not next_page_token:
            break

    return issues


def list_project_statuses():

    url = f"{SITE}/rest/api/3/project/{PROJECT}/statuses"

    r = safe_request("get", url, headers=headers, auth=auth)

    if r is None:
        print("프로젝트 상태 조회 실패: 네트워크 오류")
        return

    if not r.ok:
        log_jira_error(r, "프로젝트 상태 조회 실패")
        return

    data = r.json()

    print(f"프로젝트 {PROJECT} 상태 목록:")

    for issuetype in data:
        issue_type_name = issuetype.get("name", "이슈 유형 미정")
        print(f"- 이슈 유형: {issue_type_name}")

        for status in issuetype.get("statuses", []):
            print(f"  - {status.get('name', '이름 없음')}")


def transition_issue(issue_key, target_status):

    if not target_status:
        return

    url = f"{SITE}/rest/api/3/issue/{issue_key}/transitions"

    r = safe_request("get", url, headers=headers, auth=auth)

    if r is None:
        print("전이 대상 조회 실패: 네트워크 오류")
        return

    if not r.ok:
        log_jira_error(r, "전이 대상 조회 실패")
        return

    transitions = r.json().get("transitions", [])

    target = next((t for t in transitions if t["to"]["name"] == target_status), None)

    if not target:
        print(f"전이 실패: '{target_status}' 상태를 찾을 수 없음")
        return

    payload = {"transition": {"id": target["id"]}}

    r = safe_request("post", url, json=payload, headers=headers, auth=auth)

    if r is None:
        print("전이 실행 실패: 네트워크 오류")
        return

    if not r.ok:
        log_jira_error(r, "전이 실행 실패")
    else:
        print(f"{issue_key} -> {target_status}")

# ==============================
# 레이블 구조
# ==============================

CATEGORIES = {
    "AI": [],
    "검사기술": [],
    "개발": [],
    "설비이슈": [],
    "기타": []
}

STATUS_LIST = []  # 특정 상태만 집계하려면 상태 이름 문자열을 여기에 추가

ISSUETYPE_LIST = ["Task", "작업"]


# ==============================
# 업무일보 생성 (09:00)
# ==============================

def create_daily_report():

    today = datetime.now().strftime("%y-%m-%d")

    empty_categories = {key: [] for key in CATEGORIES.keys()}
    description_body = build_report_body(empty_categories, date_str=today)

    payload = {
        "fields": {
            "project": {"key": PROJECT},
            "summary": f"{today} 업무일보",
            "issuetype": {"name": "Task"},
            "description": text_to_adf(description_body)
        }
    }

    url = f"{SITE}/rest/api/3/issue"

    r = safe_request("post", url, json=payload, headers=headers, auth=auth)

    if r is None:
        print("업무일보 생성 실패: 네트워크 오류")
        return None

    if r.status_code != 201:

        log_jira_error(r, "업무일보 생성 실패")

        return None

    issue_key = r.json().get("key")

    print(f"업무일보 생성: {issue_key}")

    transition_issue(issue_key, REPORT_STATUS)

    return issue_key


# ==============================
# 칸반 업무 조회
# ==============================

def get_tasks():

    issuetype_clause = ",".join(f'"{issuetype}"' for issuetype in ISSUETYPE_LIST)
    jql_parts = [
        f"project = {PROJECT}",
        f"issuetype in ({issuetype_clause})",
        'summary !~ "업무일보"'
    ]

    if STATUS_LIST:
        status_clause = ",".join(f'"{status}"' for status in STATUS_LIST)
        jql_parts.append(f"status in ({status_clause})")

    jql = "\n    AND ".join(jql_parts)

    issues = run_jql_search(
        jql=jql,
        fields=["summary", "labels", "status", "assignee"]
    )

    if not issues:
        print("칸반 이슈 없음: 아래 JQL 결과 0건")
        print(jql)

    return issues


# ==============================
# 레이블 기준 분류
# ==============================

def categorize_tasks(issues):

    data = {key: [] for key in CATEGORIES.keys()}

    for issue in issues:

        fields = issue.get("fields", {})
        summary = fields.get("summary", "제목 없음")
        labels = fields.get("labels", []) or []
        status_name = fields.get("status", {}).get("name", "상태 미정")
        assignee_field = fields.get("assignee") or {}
        assignee_name = assignee_field.get("displayName") if isinstance(assignee_field, dict) else None
        assignee_name = assignee_name or "미배정"

        if status_name not in INCLUDED_STATUSES:
            continue

        matched = False

        for label in labels:

            if label in data:
                data[label].append({
                    "summary": summary,
                    "status": status_name,
                    "assignee": assignee_name,
                })
                matched = True

        if not matched:
            data["기타"].append({
                "summary": summary,
                "status": status_name,
                "assignee": assignee_name,
            })

    return data


# ==============================
# 업무일보 검색 및 중복 방지
# ==============================

def get_report_issue_by_date(target_date, fields=None):

    date_str = target_date.strftime("%y-%m-%d")

    jql = f'summary ~ "{date_str} 업무일보"'

    issues = run_jql_search(
        jql=jql,
        fields=fields,
        max_results=1
    )

    if issues:
        return issues[0]

    return None


def find_today_report():

    issue = get_report_issue_by_date(datetime.now())

    if issue:
        return issue.get("key")

    return None


def get_previous_report_entries(days_back=1):

    if days_back < 1:
        return set()

    target_date = datetime.now() - timedelta(days=days_back)

    issue = get_report_issue_by_date(target_date, fields=["description"])

    if not issue:
        return set()

    description_doc = issue.get("fields", {}).get("description")

    body_text = adf_to_text(description_doc)

    return extract_summary_status_entries(body_text)


# ==============================
# 업무일보 업데이트
# ==============================

def build_report_body(categories, date_str=None):

    date_str = date_str or datetime.now().strftime('%y-%m-%d')

    body_lines = [date_str, "[리포트]", ""]

    for category in CATEGORIES.keys():

        tasks = categories.get(category, [])

        body_lines.append(f"[{category}]")

        if not tasks:
            body_lines.append("")
        else:
            for task in tasks:
                status = task.get("status", "상태 미정")
                summary = task.get("summary", "제목 없음")
                assignee = task.get("assignee", "미배정")
                emoji = get_status_emoji(status)

                line = f"{emoji} {summary} ( 담당자 - {assignee} , 진행 상황 - {status} )"

                body_lines.append(line)

    return "\n".join(body_lines)


def send_report_body_to_slack(
    categories,
    date_str=None,
    title=None,
    body_text=None,
    include_body=True,
    issue_key=None,
):

    body = body_text or build_report_body(categories, date_str=date_str)

    sections = []

    if title:
        sections.append(title)

    if issue_key:
        sections.append(f"{SITE}/browse/{issue_key}")

    if include_body:
        sections.append(body)

    message = "\n\n".join(sections) if sections else body

    notify_slack(message)

    return body


def _strip_status_emoji(line):

    stripped = line.strip()

    for emoji in STATUS_EMOJI_PREFIXES:
        if stripped.startswith(emoji):
            return stripped[len(emoji):].strip()

    return stripped


def _extract_status_from_meta(meta_text):

    marker = "진행 상황"

    idx = meta_text.find(marker)

    if idx == -1:
        return ""

    fragment = meta_text[idx:]

    fragment = fragment.split(")", 1)[0]

    for separator in ("-", ":"):
        if separator in fragment:
            return fragment.split(separator, 1)[1].strip()

    return fragment.replace(marker, "").strip()


def extract_summary_status_entries(body_text):

    entries = set()

    if not body_text:
        return entries

    for line in body_text.splitlines():

        trimmed = line.strip()

        if not trimmed or trimmed.startswith("["):
            continue

        core = _strip_status_emoji(trimmed)

        if not core:
            continue

        if "(" in core:
            summary = core.split("(", 1)[0].strip()
            status = _extract_status_from_meta(core[core.find("("):])
        else:
            summary = core
            status = ""

        if summary:
            entries.add((summary, status))

    return entries


def deduplicate_categories(categories, previous_entries):

    cleaned = {key: [] for key in categories.keys()}

    for category, tasks in categories.items():

        for task in tasks:
            summary = (task.get("summary") or "").strip()
            status = (task.get("status") or "").strip()

            if (summary, status) in previous_entries:
                continue

            cleaned[category].append(task)

    return cleaned


def update_report(issue_key, categories):

    body = build_report_body(categories)

    url = f"{SITE}/rest/api/3/issue/{issue_key}"

    payload = {
        "fields": {
            "description": text_to_adf(body)
        }
    }

    r = safe_request("put", url, json=payload, headers=headers, auth=auth)

    if r is None:
        print("업무일보 업데이트 실패: 네트워크 오류")
        return

    if not r.ok:

        log_jira_error(r, "업무일보 업데이트 실패")

    else:

        print("업무일보 업데이트 완료")
        send_report_body_to_slack(
            categories,
            title=f"업무일보 {issue_key} 업데이트 완료",
            body_text=body,
            include_body=False,
            issue_key=issue_key,
        )


# ==============================
# 17시 실행
# ==============================

def evening_update(existing_report_key=None):

    issues = get_tasks()

    print(f"조회된 칸반 이슈 수: {len(issues)}")

    categories = categorize_tasks(issues)

    previous_entries = get_previous_report_entries()

    if previous_entries:
        before_count = sum(len(tasks) for tasks in categories.values())
        categories = deduplicate_categories(categories, previous_entries)
        after_count = sum(len(tasks) for tasks in categories.values())

        if after_count < before_count:
            print(f"어제와 동일한 항목 {before_count - after_count}건 제외")

    report_key = existing_report_key or find_today_report()

    if report_key:

        update_report(report_key, categories)

    else:

        print("오늘 업무일보 없음 - 새로 생성")

        report_key = create_daily_report()

        if report_key:
            update_report(report_key, categories)
        else:
            print("업무일보 생성 실패로 업데이트 중단")


# ==============================
# 스케줄러
# ==============================

def start_scheduler():

    schedule.every().monday.at("09:00").do(create_daily_report)
    schedule.every().tuesday.at("09:00").do(create_daily_report)
    schedule.every().wednesday.at("09:00").do(create_daily_report)
    schedule.every().thursday.at("09:00").do(create_daily_report)
    schedule.every().friday.at("09:00").do(create_daily_report)

    schedule.every().monday.at("17:00").do(evening_update)
    schedule.every().tuesday.at("17:00").do(evening_update)
    schedule.every().wednesday.at("17:00").do(evening_update)
    schedule.every().thursday.at("17:00").do(evening_update)
    schedule.every().friday.at("17:00").do(evening_update)

    print("Scheduler started...")

    while True:

        schedule.run_pending()

        time.sleep(60)


# ==============================
# 실행
# ==============================

def parse_args():
    parser = argparse.ArgumentParser(description="Jira 업무일보 자동화 스크립트")
    parser.add_argument(
        "--run-once",
        choices=["create", "update", "all"],
        help="스케줄러 대신 지정된 작업을 즉시 1회 실행"
    )
    parser.add_argument(
        "--list-statuses",
        action="store_true",
        help="프로젝트에서 사용 중인 상태 이름을 출력하고 종료"
    )
    return parser.parse_args()


if __name__ == "__main__":

    args = parse_args()

    if args.list_statuses:
        list_project_statuses()
        exit(0)

    if args.run_once:
        if args.run_once == "create":
            create_daily_report()
        elif args.run_once == "update":
            evening_update()
        elif args.run_once == "all":
            report_key = find_today_report()

            if not report_key:
                report_key = create_daily_report()

            if report_key:
                evening_update(existing_report_key=report_key)

        exit(0)

    start_scheduler()
