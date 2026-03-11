"""Utility script to trigger the dockerized Jira reporter with the current .env."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
ENV_FILE = REPO_ROOT / ".env"
SERVICE_NAME = "jira-reporter"


def _ensure_required_files() -> None:
    missing = [str(path) for path in (ENV_FILE, COMPOSE_FILE) if not path.exists()]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"필수 파일을 찾을 수 없습니다: {joined}")


def _compose_bin() -> list[str]:
    override = os.environ.get("DOCKER_COMPOSE_BIN")
    if override:
        return shlex.split(override)
    return ["docker", "compose"]


def build_compose_command(list_statuses: bool, task: str) -> list[str]:
    base_cmd = [
        *_compose_bin(),
        "-f",
        str(COMPOSE_FILE),
        "run",
        "--rm",
        "--no-deps",
        SERVICE_NAME,
        "uv",
        "run",
        "main.py",
    ]

    if list_statuses:
        return [*base_cmd, "--list-statuses"]

    return [*base_cmd, "--run-once", task]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="현재 .env 설정을 그대로 사용해 docker compose로 Jira 리포트 작업을 1회 실행합니다."
    )
    parser.add_argument(
        "--task",
        choices=["create", "update", "all"],
        default="all",
        help="즉시 실행할 작업 종류 (default: all)",
    )
    parser.add_argument(
        "--list-statuses",
        action="store_true",
        help="프로젝트 상태 목록만 조회",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실행하지 않고 compose 명령만 출력",
    )

    args = parser.parse_args()

    if args.list_statuses and args.task != "all":
        print("--list-statuses 옵션을 사용하면 --task 값은 무시됩니다.")

    _ensure_required_files()

    compose_cmd = build_compose_command(args.list_statuses, args.task)

    print("실행 명령:", " ".join(compose_cmd))

    if args.dry_run:
        return 0

    try:
        completed = subprocess.run(compose_cmd, cwd=REPO_ROOT, check=False)
        return completed.returncode
    except FileNotFoundError:
        print("docker CLI를 찾을 수 없습니다. Docker Desktop 또는 docker compose가 설치되어 있는지 확인하세요.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
