"""Đảm bảo thư mục gốc repo nằm trong sys.path khi chạy pytest."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
