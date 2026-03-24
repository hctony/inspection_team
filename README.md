# DMTSnapSync

DMTSnapSync는 Windows 트레이/툴바 기반 스크린샷 유틸리티입니다.  
각 PC에서 캡처한 이미지를 지정된 공유 경로에 PC별/날짜별로 자동 정리해 저장합니다.

## 최근 반영 사항 (요약)

- `max_image_size_kb` 옵션 구현
- About 메타데이터 하드코딩 제거 (`config.json` 기반 표시)
- About 메타데이터 입력/검증 경로 추가 (Settings에서 관리)
- 네트워크 저장 실패 시 로컬 스풀 + 자동 재시도 큐 구현

## 저장 규칙

- 폴더 구조: `{share_path}/{pc_alias}/{YYYY-MM-DD}/`
- 파일명 규칙: `cap_{HHMMSS}.jpg`
- 동일 파일명 충돌 시: `cap_{HHMMSS}_1.jpg`, `..._2.jpg` 형태로 자동 접미사 부여
- 상위 폴더 자동 생성
- UNC 경로(`\\server\share`) 및 로컬 경로 모두 지원

## 현재 구현 기능

- 시스템 트레이 앱 동작
- 트레이 메뉴
- `Capture Fullscreen`
- `Capture Region (Drag)`
- `Show Toolbar`
- `Open Folder`
- `Settings`
- `About`
- `Quit`
- 플로팅 툴바(기본 Windows 제목표시줄 사용)
- 버튼: `Full`, `Region`, `Settings`, `문의(About)`
- 전체화면 캡처 (`Ctrl+F9`)
- 영역 드래그 캡처 (`Ctrl+F10`)
- 전역 핫키 콜백 비동기 처리(응답성 유지)
- 캡처 직전 툴바 숨김, 캡처 후 복원
- 설정 창 경로 찾아보기(Browse) 지원
- About/Settings 창 로고 아이콘 적용
- 설정값 `config.json` 저장/재로드
- `max_image_size_kb` 적용 저장(품질 조정 + 필요 시 해상도 축소)
- About 정보 `config.json` 기반 표시 (Owner/Developer/Support)
- About 실행 전 메타데이터 검증(누락/이메일 형식)
- 네트워크 실패 시 `_retry_spool` 큐잉 후 백그라운드 자동 재동기화

## 설정 항목

- `pc_alias`: 비어 있으면 Windows 호스트명 자동 사용
- `share_path`: 저장 루트 경로(기본값 `C:\DMTSnapSync`)
- `quality`: JPEG 품질(`1~100`)
- `max_image_size_kb`: 최대 이미지 용량(KB, 비우면 미적용)
- `owner_name`: About의 Owner/Director 이름
- `owner_email`: About의 Owner/Director 이메일
- `developer_name`: About의 Developer/Bug Contact 이름
- `developer_email`: About의 Developer/Bug Contact 이메일
- `support_contact`: About의 지원/문의 정보
- `hotkey_full`: 전체 캡처 핫키
- `hotkey_drag`: 영역 캡처 핫키

## 실행 방법 (개발 환경)

```powershell
cd DMTSnapSync
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
python -m dmtsnapsync
```

실행 후 화면에 큰 창이 뜨지 않는 것이 정상입니다.  
트레이 아이콘/툴바에서 기능을 사용하면 됩니다.

## 빌드 방법 (PyInstaller, 단일 EXE)

권장:

```powershell
.\build_exe.ps1
```

직접 실행:

```powershell
.\.venv\Scripts\pyinstaller --noconfirm --clean --onefile --noconsole -n DMTSnapSync --additional-hooks-dir hooks -p src build_entry.py
```

출력 파일:

- `dist\DMTSnapSync.exe`

## 배포/운영 메모

- EXE 단독 실행 가능(대상 PC에 Python 설치 불필요)
- 설정 파일은 실행 위치 기준 `config.json` 사용
- 네트워크 경로 저장 실패 시 로컬 스풀(`_retry_spool`)에 임시 저장 후 자동 재시도
- 재시도 큐 상태 파일: `retry_queue.json`
- 재시도 큐는 앱 재시작 후에도 이어서 처리됨(큐 파일 기반)

## 미구현 / TODO

- 재시도 정책 고도화(최대 보관 기간/수동 재시도 버튼)
