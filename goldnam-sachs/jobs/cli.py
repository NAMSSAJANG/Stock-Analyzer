"""CLI dispatch; run from the monorepo root containing jobs/."""

import sys


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in {"validate", "daily"}:
        raise SystemExit("goldnam validate|daily --market us|kr [options]")
    command = sys.argv.pop(1)
    if command == "validate":
        from jobs.validate import main as run
    else:
        from jobs.daily_scores import main as run
    run()
