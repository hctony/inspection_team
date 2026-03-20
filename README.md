# DMTSnapSync

윈도우 트레이에서 동작하는 스크린샷 캡처 유틸리티입니다. 캡처 이미지를 고정된 폴더 구조로 저장합니다.

**폴더 구조**
`{share_path}/{pc_alias}/{YYYY-MM-DD}/cap_{HHmmss}.jpg`

**구현됨**
- 트레이 앱 메뉴 (전체 캡처, 영역 캡처, 폴더 열기, 설정, About, 종료)
- 전체화면 캡처 (Ctrl+F9)
- 드래그 영역 캡처 (Ctrl+F10)
- 전역 핫키 캡처 (비블로킹 스레드)
- 자동 폴더 생성
- UNC/로컬 경로 지원
- 파일명 충돌 시 자동 suffix 추가
- 설정 UI (pc_alias, share_path, quality, hotkeys)
- About/Info (Director/Developer/Support)

**미구현 / TODO**
- `max_image_size_kb` 옵션 (현재 `quality`만 지원)
- Director 이메일 확정 (현재 `TBD`)

**설정값**
- `pc_alias`: 비어있으면 Windows 호스트명 사용
- `share_path`: 로컬 경로 또는 UNC 경로
- `quality`: JPEG 품질 1-100
- `hotkey_full`: 전체 캡처 핫키
- `hotkey_drag`: 영역 캡처 핫키

**실행 (개발)**
```bash
cd DMTSnapSync
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
pip install -e .
python -m dmtsnapsync
```

**빌드 (PyInstaller)**
```bash
pyinstaller --onefile --noconsole -n DMTSnapSync ` --add-data "src\dmtsnapsync\assets;dmtsnapsync\assets" ` -p src ` build_entry.py
```