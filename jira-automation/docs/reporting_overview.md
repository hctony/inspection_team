# Jira Daily Report Logic

## 담당자 & 상태 표시
- Jira 이슈의 `fields.assignee.displayName`과 `fields.status.name`을 읽어 `⚠️ 작업명 ( 담당자 - 이름 , 진행 상황 - 상태 )` 형식으로 렌더링합니다. 완료=🟢, 진행=⚠️(노란 삼각형), 계획=📅, 기타=▪️로 고정돼 있으며, 실제 보고에서는 완료/진행 중 상태만 남습니다.
- 담당자가 지정되지 않은 경우 `미배정`으로 대체되며, 상태도 없으면 `상태 미정`이 들어갑니다.

## 어제 일보 기반 중복 제거
1. `get_previous_report_entries()`가 어제 날짜(`today - 1`)의 업무일보를 JQL로 찾습니다.
2. Jira Description(ADF)을 `adf_to_text()`로 평문으로 바꾼 뒤 `extract_summary_status_entries()`가 `(요약, 상태)` 튜플 집합을 만듭니다.
3. `deduplicate_categories()`가 오늘 수집한 카테고리 데이터에서 동일한 튜플을 가진 항목을 제거합니다.
4. 제외된 개수는 로그에 `어제와 동일한 항목 N건 제외`로 기록됩니다.

필요하면 `days_back` 파라미터로 비교 기준 일수를 늘려 더 오래된 일보까지 확인할 수 있습니다.

## 수동 트리거
- `trigger.py`는 `docker compose run --rm --no-deps jira-reporter uv run main.py ...` 명령을 래핑해 현재 `.env` 설정 그대로 1회 실행합니다.
- `--task {create|update|all}`로 원하는 작업을 지정하고, `--list-statuses`로 Jira 상태 목록만 확인할 수 있습니다.
- 기본 `docker compose` 대신 다른 바이너리를 쓰려면 `DOCKER_COMPOSE_BIN` 환경 변수를 설정하세요.

## Slack Preview
- `.env`에 `SLACK_WEBHOOK_URL`을 채우면 **업데이트 완료 시** 자동으로 Slack 알림이 전송됩니다. 메시지는 `업무일보 DMT-XX 업데이트 완료` 텍스트와 `https://<SITE>/browse/DMT-XX` 링크만 포함돼, Jira 보드 상세로 바로 이동할 수 있습니다.
- 별도로 본문을 공유하고 싶으면 `send_report_body_to_slack(..., include_body=True)`를 호출하세요. 기본값은 본문까지 포함하고, `include_body=False`와 `issue_key`를 함께 주면 링크만 보낼 수 있습니다. 테스트에서는 `notify_slack`을 목킹해 메시지가 예상대로 구성되는지 확인할 수 있습니다.

이 문서는 운영 중 동작을 빠르게 참고하기 위한 요약본이며, 세부 구현은 `main.py`와 `trigger.py`를 참고하세요.
