# -*- coding: utf-8 -*-
"""The engine's own minimap, dressed with Diorama markers.

This is the one presentation layer that draws *live terrain* inside the HUD
without a render-to-texture API: the China Edition UI library ships a minimap
control (``mini_map.mini_map_wrapper``) whose renderer is implemented by the
engine, and the client exposes ``GetMiniMapScreenNodeCls()`` so a mod can inherit
it and add markers.

That pattern is taken from the official MCStudio sample
``demo/GodChef/.../modClient/ui/pop_minimapUI.py``, which does exactly::

    MiniMapBaseScreen = clientApi.GetMiniMapScreenNodeCls()
    class UIMiniMap(MiniMapBaseScreen): ...
    param = {"mini_map_root_path": "/inheritor1"}

Everything here is optional: if the class or the control is missing on a build,
the screen degrades to an empty HUD and :meth:`available` reports ``False`` so
the caller can fall back to the JSON atlas minimap.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import client.extraClientApi as clientApi

from dioramaScripts.modCommon import modConfig
from dioramaScripts.modCommon.log import warn
from dioramaScripts.modClient.ui import ui_base

MiniMapBase = ui_base.minimap_screen_cls()

#: True when the client actually exposed a minimap base class.
HAS_ENGINE_MINIMAP = MiniMapBase is not ui_base.screen_node_cls() and MiniMapBase is not object

#: Marker sprites, resource-pack relative and without the extension.
WAYPOINT_SPRITE = "textures/ui/diorama_marker_waypoint"
DEATH_SPRITE = "textures/ui/diorama_marker_death"


def make_screen_cls(base):
    """Build the minimap screen class against ``base``.

    Done in a function because the base class is discovered at import time and
    the result is cached by the caller; a subclass of ``object`` would be wrong
    for the engine, so the caller checks :data:`HAS_ENGINE_MINIMAP` first.
    """

    class DioramaMiniMapScreen(base):
        """HUD screen whose map layer is rendered by the engine."""

        CONTENT_ROOT = "/minimap_root"
        USES_BASE_SCREEN = True

        def __init__(self, namespace, name, param):
            params = dict(param or {})
            params.setdefault("mini_map_root_path", "/minimap_anchor/inheritor1")
            base.__init__(self, namespace, name, params)
            self._static_markers = []
            self._entity_markers = []
            self._waypoint_ids = {}

        # -- lifecycle ------------------------------------------------

        def Create(self):
            try:
                base.Create(self)
            except Exception as exc:  # noqa: BLE001
                warn("minimap base Create failed: %r", exc)
            return True

        def init_screen(self):
            """The engine calls this once the minimap renderer is ready."""
            return True

        def destroy(self):
            self._static_markers = []
            self._entity_markers = []
            self._waypoint_ids = {}

        # -- controls -------------------------------------------------

        def _map_control(self):
            control = ui_base.control(self, "/minimap_anchor/inheritor1")
            if control is None:
                return None
            for accessor in ("asMiniMap", "asNeteaseMiniMap"):
                fn = getattr(control, accessor, None)
                if fn is None:
                    continue
                try:
                    return fn()
                except Exception:  # noqa: BLE001
                    continue
            return None

        # -- markers --------------------------------------------------

        def sync_waypoints(self, waypoints):
            """Replace the static markers with ``waypoints``.

            Each item needs ``id``, ``x``, ``z`` and optionally ``kind``; the
            engine places the marker from the world coordinate itself, so the
            mod does not have to project anything.
            """
            control = self._map_control()
            if control is None:
                return 0
            wanted = {}
            for waypoint in waypoints or []:
                key = str(waypoint.get("id"))
                wanted[key] = waypoint
            for key in list(self._waypoint_ids):
                if key not in wanted:
                    self._remove_static(self._waypoint_ids.pop(key))
            for key, waypoint in wanted.items():
                sprite = DEATH_SPRITE if waypoint.get("kind") == "death" else WAYPOINT_SPRITE
                if key in self._waypoint_ids:
                    continue
                handle = self._add_static(control, waypoint, sprite)
                if handle is not None:
                    self._waypoint_ids[key] = handle
            return len(self._waypoint_ids)

        def _add_static(self, control, waypoint, sprite):
            fn = getattr(control, "AddStaticMarker", None)
            if fn is None:
                return None
            try:
                return fn(
                    float(waypoint.get("x", 0)),
                    float(waypoint.get("z", 0)),
                    sprite,
                )
            except TypeError:
                try:
                    return fn(
                        (float(waypoint.get("x", 0)), float(waypoint.get("z", 0))),
                        sprite,
                    )
                except Exception as exc:  # noqa: BLE001
                    warn("AddStaticMarker failed: %r", exc)
                    return None
            except Exception as exc:  # noqa: BLE001
                warn("AddStaticMarker failed: %r", exc)
                return None

        def _remove_static(self, handle):
            control = self._map_control()
            if control is None or handle is None:
                return False
            fn = getattr(control, "RemoveStaticMarker", None)
            if fn is None:
                return False
            try:
                fn(handle)
                return True
            except Exception:  # noqa: BLE001
                return False

        def track_entities(self, entity_ids):
            """Mark live entities; the engine follows them as they move."""
            control = self._map_control()
            if control is None:
                return 0
            wanted = [str(e) for e in (entity_ids or [])]
            for tracked in list(self._entity_markers):
                if tracked not in wanted:
                    self._remove_entity(tracked)
            for entity_id in wanted:
                if entity_id in self._entity_markers:
                    continue
                fn = getattr(control, "AddEntityMarker", None)
                if fn is None:
                    break
                try:
                    fn(entity_id, WAYPOINT_SPRITE)
                    self._entity_markers.append(entity_id)
                except Exception as exc:  # noqa: BLE001
                    warn("AddEntityMarker failed: %r", exc)
                    break
            return len(self._entity_markers)

        def _remove_entity(self, entity_id):
            control = self._map_control()
            if control is None:
                return False
            fn = getattr(control, "RemoveEntityMarker", None)
            if fn is None:
                return False
            try:
                fn(entity_id)
            except Exception:  # noqa: BLE001
                return False
            if entity_id in self._entity_markers:
                self._entity_markers.remove(entity_id)
            return True

        # -- view -----------------------------------------------------

        def refresh(self):
            """Force the engine to repaint the map after a big move."""
            control = self._map_control()
            fn = getattr(control, "RepaintMiniMap", None) if control is not None else None
            if fn is None:
                return False
            try:
                fn()
                return True
            except Exception:  # noqa: BLE001
                return False

        def zoom(self, direction):
            control = self._map_control()
            if control is None:
                return False
            name = "ZoomIn" if direction > 0 else "ZoomOut"
            fn = getattr(control, name, None)
            if fn is None:
                return False
            try:
                fn()
                return True
            except Exception:  # noqa: BLE001
                return False

        def set_zoom(self, value):
            control = self._map_control()
            if control is None:
                return False
            fn = getattr(control, "SetZoom", None)
            if fn is None:
                return False
            try:
                fn(float(value))
                return True
            except Exception:  # noqa: BLE001
                return False

    return DioramaMiniMapScreen


DioramaMiniMapScreen = make_screen_cls(MiniMapBase)


def available():
    """Whether the engine minimap class was found on this client build."""
    return bool(HAS_ENGINE_MINIMAP)


def register(namespace=None):
    """``RegisterUI`` the minimap screen; returns the class or ``None``."""
    if not HAS_ENGINE_MINIMAP:
        return None
    ns = namespace or modConfig.MOD_NAMESPACE
    try:
        clientApi.RegisterUI(ns, modConfig.UI_MINIMAP, DioramaMiniMapScreen, modConfig.UI_DEF_MINIMAP)
        return DioramaMiniMapScreen
    except Exception as exc:  # noqa: BLE001
        warn("RegisterUI(minimap) failed: %r", exc)
        return None
