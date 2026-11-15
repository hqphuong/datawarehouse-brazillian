"""Authentication logic for ``/api/auth/*``.

Stored credentials may be a werkzeug hash (preferred) or a legacy plain-text
value; a legacy row is upgraded to a hash after a successful login.
"""

from __future__ import annotations

import hmac
import re

from werkzeug.security import check_password_hash, generate_password_hash

from . import bi_repo as repo

_HASH_PATTERN = re.compile(r"^(scrypt|pbkdf2|argon2)[:$]")


def login(username: str, password: str):
    """Return the authenticated username, or ``None`` on a mismatch."""
    row = repo.get_account(username)
    if not row:
        return None

    stored = row.get("password") or ""
    if _HASH_PATTERN.match(stored):
        return username if check_password_hash(stored, password) else None

    if not hmac.compare_digest(str(stored), str(password)):
        return None

    try:
        repo.update_account_password(username, generate_password_hash(password))
    except Exception:  # pragma: no cover - best effort upgrade
        pass
    return username
