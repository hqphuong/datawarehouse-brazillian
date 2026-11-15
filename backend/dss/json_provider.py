"""JSON rendering compatible with the former Django ``JsonResponse``."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

import numpy as np
from flask.json.provider import DefaultJSONProvider


class DssJSONProvider(DefaultJSONProvider):
    """Preserve key order, accept numpy scalars, keep Django's escaping."""

    ensure_ascii = True
    sort_keys = False

    def dumps(self, obj, **kwargs):
        kwargs.setdefault("ensure_ascii", self.ensure_ascii)
        kwargs.setdefault("sort_keys", self.sort_keys)
        kwargs.setdefault("default", self.default)
        return json.dumps(obj, **kwargs)

    def default(self, o):
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, (datetime, date, time)):
            return o.isoformat()
        if isinstance(o, timedelta):
            return o.total_seconds()
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, UUID):
            return str(o)
        return super().default(o)
