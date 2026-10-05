"""
Điểm khởi chạy pipeline ETL.

Cách chạy:
    python src/main.py            # chỉ Transform (sinh file CSV trong data/processed)
    python src/main.py --load     # Transform + Load (nạp vào PostgreSQL)
"""

import subprocess
import sys
from pathlib import Path

try:  # chạy như package:  python -m src.main
    from .config import SRC_DIR, ensure_dirs
except ImportError:  # chạy trực tiếp: python src/main.py
    from config import SRC_DIR, ensure_dirs

# Các bước Transform, chạy theo thứ tự
files = [
    "dim_time.py",
    "dim_location.py",
    "dim_product.py",
    "fact_delivery_sla.py",
]

# Bước Load (chạy sau, chỉ khi có --load)
load_step = "load_data.py"


def run_script(filename: str) -> int:
    """Chạy một script ETL con bằng cùng interpreter hiện tại."""
    script_path = SRC_DIR / filename
    print(f"\n========== Running {filename} ==========")

    if not script_path.is_file():
        print(f"❌ Không tìm thấy script: {script_path}")
        return 1

    result = subprocess.run([sys.executable, str(script_path)], check=False)

    if result.returncode != 0:
        print(f"\n❌ {filename} bị lỗi. Dừng chương trình.")
        return result.returncode

    print(f"✅ {filename} chạy thành công.")
    return 0


def main() -> int:
    ensure_dirs()

    steps = list(files)
    if "--load" in sys.argv:
        steps.append(load_step)

    for filename in steps:
        returncode = run_script(filename)
        if returncode != 0:
            return returncode

    print("\n🎉 Pipeline hoàn tất!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
