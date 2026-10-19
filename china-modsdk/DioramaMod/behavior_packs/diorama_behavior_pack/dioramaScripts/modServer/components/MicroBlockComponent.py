# -*- coding: utf-8 -*-
"""Server-side adapter for official CreateMicroBlockResStr snapshots."""
from __future__ import absolute_import, division, print_function, unicode_literals

import json


class MicroBlockComponent(object):
    """Create bounded, pre-baked Diorama snapshots for later client display."""

    MAX_EDGE = 64

    def __init__(self, server):
        self.server = server
        self._last = {}

    def create_snapshot(self, identifier, start, end, color_map=None, merge=True, icon=""):
        start = tuple(int(v) for v in start)
        end = tuple(int(v) for v in end)
        if any(abs(end[i] - start[i]) + 1 > self.MAX_EDGE for i in range(3)):
            return {"ok": False, "reason": "edge_limit"}
        try:
            factory = self.server.api.GetEngineCompFactory()
            block = factory.CreateBlock(self.server.level_id)
            raw = block.CreateMicroBlockResStr(identifier, start, end, color_map or {}, bool(merge), icon)
            if not raw:
                return {"ok": False, "reason": "engine_refused"}
            payload = raw if isinstance(raw, dict) else json.loads(raw)
            self._last[identifier] = payload
            return {"ok": True, "identifier": identifier, "resource": payload}
        except Exception as exc:
            return {"ok": False, "reason": "api_unavailable", "error": str(exc)}

    def last_snapshot(self, identifier):
        return self._last.get(identifier)
