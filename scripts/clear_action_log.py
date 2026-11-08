import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clear DSS action log rows from the configured database."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm deletion of all action log rows, including non-test rows.",
    )
    args = parser.parse_args()
    if not args.yes:
        parser.error("Deletion requires the explicit --yes flag.")

    sys.path.insert(0, str(ROOT / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    import django

    django.setup()

    from dss.models import ActionLog

    # This intentionally deletes all ActionLog rows, which may include non-test rows.
    _, deleted_by_model = ActionLog.objects.all().delete()
    deleted = deleted_by_model.get(ActionLog._meta.label, 0)
    print(f"Deleted {deleted} ActionLog row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
