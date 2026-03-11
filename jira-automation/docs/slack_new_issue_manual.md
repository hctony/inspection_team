# Jira 신규 업무 Slack 알림 매뉴얼

## 1. 목표
- **신규 업무 등록 즉시** 지정된 Slack 채널에 알림을 보내어 팀이 실시간으로 요청을 파악하도록 합니다.
- 기존 업무일보 자동화 코드와는 **별도 경로**(Jira Webhook, Slack Incoming Webhook, 선택 시 자체 수신 서버)를 사용합니다.

## 2. 사전 준비
1. Slack 워크스페이스에서 **Incoming Webhook URL** 생성
   - `https://api.slack.com/apps` → 새 앱 → *Incoming Webhooks* 활성화 → 채널 선택 후 URL 복사
2. Jira Cloud 관리자 권한 (프로젝트 설정과 Webhook/Automation 생성 권한)
3. 네트워크로 Slack에 HTTPS POST를 보낼 수 있는 환경

## 3. 방법 A – Jira Automation → Slack 직접 연동 (가장 간단)
> Jira Automation 규칙으로 “이슈 생성” 이벤트를 감지하고 Slack Webhook으로 POST 합니다.

1. **프로젝트 설정 → Automation** 진입 (또는 Global Automation)
2. **Create rule** 선택
3. Trigger: `Issue created`
4. Action: `Send web request`
   - URL: Slack Incoming Webhook URL
   - Method: `POST`
   - Headers: `Content-Type: application/json`
   - Webhook body 예시:
     ```json
     {
       "text": "*[{{issue.key}}]* {{issue.fields.summary}}\n담당자: {{issue.fields.assignee.displayName|default("미배정")}}\n상태: {{issue.fields.status.name}}"
     }
     ```
5. (선택) Condition: 특정 프로젝트/이슈타입/레이블에만 적용
6. Rule 이름 지정 후 **Turn on rule**

**장점**: 추가 서버 없이 Jira만으로 완료.  
**주의**: Slack Webhook URL이 Jira에 저장되므로 접근 권한 관리 필수.

## 4. 방법 B – Jira Webhook → 자체 수신 서비스 → Slack
> 더 복잡한 로직(예: 이슈 필터링, 첨부 처리, 멀티 채널 라우팅)이 필요하면 추천.

1. **수신 API 서비스 구성**
   - 예: 기존 Python 스크립트나 서버리스 함수(Cloud Run, Lambda 등)
   - 엔드포인트는 HTTPS여야 하며 Jira가 접근할 수 있어야 합니다.
   - 요청 본문은 Jira Webhook payload(JSON) 그대로 수신.
2. **수신 서비스 로직**
   - 이벤트 유형 검사: `issue_created`만 처리
   - 필요한 필드 추출: `issue.key`, `fields.summary`, `fields.assignee.displayName`, `fields.status.name`, `fields.labels`
   - 사전 정의된 필터(예: 특정 레이블, 프로젝트)에 맞으면 Slack Webhook으로 POST
   - Slack 메시지 예시(멀티 라인):
     ```json
     {
       "text": "새 업무 등록 : *{{key}}*\n제목: {{summary}}\n담당자: {{assignee}}\n상태: {{status}}\n레이블: {{labels}}"
     }
     ```
3. **Jira Webhook 생성**
   - Jira 관리(⚙) → *System* → *Webhooks*
   - Create Webhook → 이름
   - URL: 1단계에서 만든 수신 엔드포인트
   - Events: `Issue created`
   - JQL 필터(Optional): `project = DMT AND issuetype in (Task, "작업")`
   - 활성화

**장점**: 복잡한 비즈니스 규칙/다중 알림 채널 관리 가능.  
**주의**: 엔드포인트 인증(예: Secret Token 검증)과 모니터링 필요.

## 5. Slack 메시지 포맷 권장안
- Prefix에 프로젝트/라벨 이모지 사용 예: `:clipboard: [DMT] *DMT-123*`
- 중요 필드: 제목, 담당자, 상태, 생성자, 예상 종료일 등
- Jira 이슈 링크 포함: `https://<your-domain>.atlassian.net/browse/{{issue.key}}`
- 필요 시 `blocks` 포맷으로 레이아웃 구성 가능

## 6. 테스트 체크리스트
1. Slack Webhook URL이 올바르게 작동하는지 `curl -X POST`로 사전 테스트
2. Jira 테스트 프로젝트에서 Dummy 이슈 생성 → Slack에 즉시 도착 여부 확인
3. 조건부 필터(레이블, 이슈 타입)가 의도대로 동작하는지 각각 다른 조건으로 시도
4. 실패 시 Jira Automation/웹훅 실행 로그 확인 (Project settings → Automation audit log / System → Webhook history)

## 7. 운영 팁
- Slack 메시지를 너무 자주 보내면 노이즈가 될 수 있으므로 필요 시 레이블/상태 조건으로 제한
- 민감 정보 보호: Slack 공개채널 대신 전용 채널 사용 권장
- Webhook URL 교체 시 `.env`나 Jira Automation rule에서 즉시 업데이트
- 자체 수신 서비스에는 Health Check와 재시도 로직을 구현해 두는 것이 안전

---
문의나 추가 기능(예: 이슈 업데이트/완료 알림, 멘션 처리)이 필요하면 README에 적힌 실행 방법으로 새 스크립트를 확장하거나 Jira Automation에서 규칙을 추가하세요.
