"""Regenerate reports/dss_eval_raw.txt while keeping stdout out of the console."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports" / "dss_eval_raw.txt"
sys.path.insert(0, str(ROOT))


def main() -> None:
    from etl import dss_eval

    output = StringIO()
    with redirect_stdout(output):
        dss_eval.main()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", encoding="utf-8", newline="\n") as report:
        report.write(output.getvalue())


if __name__ == "__main__":
    main()
