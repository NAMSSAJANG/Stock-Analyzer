"""CLI dispatch; run from the monorepo root containing jobs/."""

import sys


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in {"validate", "daily", "import-v6"}:
        raise SystemExit("goldnam validate|daily|import-v6 [options]")
    command = sys.argv.pop(1)
    if command == "validate":
        from jobs.validate import main as run
    elif command == "import-v6":
        from jobs.import_v6_history import main as run
    else:
        from jobs.daily_scores import main as run
    try:
        run()
    except Exception as exc:
        raise SystemExit(
            f"실행 실패: {type(exc).__name__}. 시크릿을 출력하지 않았습니다. 공급자 상태·설정·보고서를 확인하세요."
        ) from None
