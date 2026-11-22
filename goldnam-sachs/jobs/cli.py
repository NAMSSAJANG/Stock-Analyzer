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
    run()
