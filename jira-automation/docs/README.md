# Jira Reporter Automation

Jira 업무일보를 자동으로 생성하고 09:00/17:00 스케줄에 맞춰 내용을 업데이트하는 스크립트입니다. Docker/Compose 환경이나 Airflow 태스크에서 그대로 실행할 수 있도록 설계되어 있습니다.

## 환경 변수
`.env` 파일을 생성해 아래 값을 채워 주세요. 예시는 `.env.example` 참고.

```
JIRA_EMAIL=your_email@example.com
JIRA_API_TOKEN=your_api_token
JIRA_SITE=https://your-domain.atlassian.net
JIRA_PROJECT_KEY=DMT
JIRA_REPORT_STATUS=업무 일보
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz  # 선택 사항
TZ=Asia/Seoul
```

## 로컬 실행
수동 점검 시 `uv`로 의존성을 동기화한 뒤 필요 작업을 1회 실행할 수 있습니다.

```bash
uv run main.py --run-once create   # 오전 일보 생성만
uv run main.py --run-once update   # 칸반 데이터로 업데이트만
uv run main.py --list-statuses     # 프로젝트 상태 목록 확인
```

Slack 알림은 `SLACK_WEBHOOK_URL`을 설정했을 때만 **업데이트 완료 시** 전송됩니다. 메시지에는 "업무일보 DMT-XX 업데이트 완료" 헤더와 함께 Jira 이슈 링크만 담겨, 칸반 보드 상세로 바로 이동할 수 있습니다.
`--run-once all`은 먼저 오늘 날짜 업무일보를 검색하고, 없을 때만 새 이슈를 만든 뒤 즉시 업데이트합니다. 이미 생성된 일보를 강제로 새로 만들고 싶다면 `--run-once create`를 별도로 실행하세요 (이때는 Slack 알림이 가지 않습니다).

### Slack Webhook 설정 방법
1. Slack 관리자가 <https://api.slack.com/apps>에서 새 앱을 만들고 **Incoming Webhooks** 기능을 활성화합니다.
2. "웹훅 추가" 버튼으로 원하는 채널을 선택해 URL을 발급받습니다. (예: `https://hooks.slack.com/services/T000/B000/XXXX`)
3. 해당 URL을 `.env`의 `SLACK_WEBHOOK_URL` 값으로 넣고 컨테이너를 재시작합니다.
4. 필요 시 채널을 바꾸고 싶으면 같은 메뉴에서 새 URL을 만들거나 기존 웹훅의 채널을 수정하면 됩니다.

테스트나 사내 검증 용도로는 별도 테스트 채널을 만들어 URL을 분리해 두는 것이 안전합니다. 메시지는 Jira 이슈 링크만 포함하므로 민감한 본문이 그대로 노출되지 않습니다.

## Docker Compose

```bash
docker compose up -d --build        # 백그라운드에서 스케줄러 실행
```

로그 확인:

```bash
docker compose logs -f jira-reporter
```

컨테이너가 떠 있는 동안 `TZ=Asia/Seoul` 환경값을 사용해 **한국 시간 기준 평일 09:00에 신규 업무일보 생성**, **17:00에 업데이트** 작업이 자동으로 실행됩니다. 주중 자동화를 계속 쓰고 싶다면 `docker compose up -d` 상태를 유지하면 됩니다.

## 수동 Docker 트리거

스케줄러를 기다리지 않고 현재 `.env` 값을 그대로 사용해 1회 실행하고 싶다면 루트에 추가된 `trigger.py`를 활용하세요. 내부적으로 `docker compose run jira-reporter uv run main.py ...`를 호출하므로 이미지/환경 구성이 동일하게 재사용됩니다.

```powershell
python trigger.py --task update        # 업무일보 업데이트만 즉시 실행
python trigger.py --task create        # 신규 업무일보만 생성
python trigger.py --task all           # 생성 + 업데이트 연속 실행 (기본값)
python trigger.py --list-statuses      # Jira 프로젝트 상태 목록 출력
python trigger.py --dry-run --task all # 실행 전 compose 명령만 확인
```

`docker compose` 대신 `docker-compose` 바이너리를 써야 한다면 `DOCKER_COMPOSE_BIN=docker-compose python trigger.py --task update`처럼 환경 변수로 오버라이드할 수 있습니다.

> 컨테이너가 이미 떠 있는 상태여도 문제 없습니다. `trigger.py`는 동일한 이미지를 기반으로 일회성 컨테이너를 띄운 뒤 작업 완료 후 즉시 제거하므로, 운영 중인 서비스와 충돌하지 않습니다.

## 업데이트 로직 & 포맷

- **담당자/상태 표기**: Jira 이슈의 `Assignee`와 `Status`를 그대로 사용해 `⚠️ 작업명 ( 담당자 - 홍길동 , 진행 상황 - 진행 중 )` 형식으로 출력합니다. 완료=🟢, 진행=⚠️(노란 삼각형), 계획=📅, 기타=▪️ 이모티콘으로 통일했습니다. 담당자가 비어 있으면 `미배정`이 자동으로 들어갑니다.
- **상태 필터링**: 실무 보고에 필요한 `완료/진행 중` 상태만 집계합니다. Jira에서 다른 상태(예: 예정/보류 등)는 업무일보에 표시되지 않습니다.
- **어제 일보와 비교한 중복 제거**: 리포트를 업데이트하기 전에 전날(오늘 날짜 - 1일)의 업무일보를 찾아 ADF 본문을 평문으로 변환하고, `(요약, 상태)` 쌍이 동일한 항목은 오늘 목록에서 제외합니다. 덕분에 상태·내용에 변화가 있는 작업만 새로 표기됩니다.
- **로그 확인**: 중복으로 제외된 항목이 있으면 `어제와 동일한 항목 N건 제외`라는 메시지가 로그에 남습니다. Jira API 호출 실패 시에도 스케줄러가 종료되지 않고 계속 재시도합니다.

필요에 따라 `get_previous_report_entries(days_back=n)` 호출로 비교 기준 일수를 조정할 수 있으며, 포맷을 바꾸고 싶으면 `build_report_body`를 수정하세요.

## 테스트
헬퍼 함수와 리포트 포맷을 검증하는 Pytest 스위트가 포함돼 있습니다.

```bash
uv run -m pytest
```

### Pytest 매뉴얼 및 활용 팁

#### 사용 목적
- 리포트 포맷, 레이블 분류, ADF 변환 등 **핵심 로직의 회귀 테스트**를 자동화해 배포 전에 안전하게 검증합니다.
- 향후 기능 추가 시 새 테스트를 더해도 기존 스위트와 함께 실행되므로 **신기능이 기존 흐름을 깨지 않도록** 확인할 수 있습니다.

#### 실행 방법 (PowerShell 기준)
```powershell
$env:UV_PROJECT_ENVIRONMENT = ".uv-env"
uv run -m pytest
# 실행 후 해제하려면: Remove-Item Env:UV_PROJECT_ENVIRONMENT
```
또는 한 번만 실행할 경우:
```powershell
cmd /c "set UV_PROJECT_ENVIRONMENT=.uv-env && uv run -m pytest"
```

#### 유용한 Pytest 기능
- `-k "keyword"`: 특정 키워드가 들어간 테스트만 실행
- `-x`: 첫 실패에서 즉시 중단 (빠른 피드백)
- `-vv`: 각 테스트 이름과 상세 로그 출력
- `--maxfail=2`: 연속 실패 허용 개수 제한
- `pytest --durations=5`: 가장 오래 걸린 테스트 5개 표시

#### 커스텀 테스트 작성 팁
- `tests/` 폴더에 `test_*.py` 파일을 추가하면 자동으로 발견됩니다.
- 공통 픽스처는 `tests/conftest.py`에 정의해서 재사용하세요.
- Jira API 호출이 필요한 테스트는 `requests` 모듈을 `responses`/`requests-mock`으로 목킹해 오프라인에서도 돌릴 수 있습니다.
