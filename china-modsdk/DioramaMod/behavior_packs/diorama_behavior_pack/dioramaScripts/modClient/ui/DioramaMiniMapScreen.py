# -*- coding: utf-8 -*-
"""The engine's own minimap, dressed with Diorama markers.

This is the only presentation layer that draws *live terrain* inside the HUD
without a render-to-texture API. The China Edition UI library ships a minimap
control (``mini_map.mini_map_wrapper``) whose renderer is implemented by the
engine, and the client exposes ``GetMiniMapScreenNodeCls()`` so a mod can inherit
``MiniMapBaseScreen`` and add markers on top.

Verified against two official sources:

* the MCStudio sample ``demo/GodChef/.../modClient/ui/pop_minimapUI.py`` and
  ``clickbuttonUI.py``, which create a *persistent HUD* minimap with
  ``CreateUI(..., {"inputMode": 0, "mini_map_root_path": "/inheritor0"})``;
* the ``MiniMapUIControl`` method table in the official UI控件 docs.

The control exposes 13 methods and nothing else: markers, text markers,
``SetHighestY``, relative zoom, and a full repaint. There is **no** way to
recolour the terrain, filter blocks, or rotate the map - the engine draws it, so
rotation has to be done with a separate compass overlay.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import client.extraClientApi as clientApi

from dioramaScripts.modCommon import modConfig
from dioramaScripts.modCommon.log import warn
from dioramaScripts.modClient.ui import ui_base

MiniMapBase = ui_base.minimap_screen_cls()

#: True when the client actually exposed the minimap base class.
HAS_ENGINE_MINIMAP = (
    MiniMapBase is not ui_base.screen_node_cls() and MiniMapBase is not object
)

#: Marker sprites, resource-pack relative and without the extension.
WAYPOINT_SPRITE = "textures/ui/diorama_marker_waypoint"
DEATH_SPRITE = "textures/ui/diorama_marker_death"
PLAYER_SPRITE = "textures/ui/diorama_marker_player"

#: Marker size in UI pixels, as the engine documents it (default is 4x4).
MARKER_SIZE = (6, 6)


def make_screen_cls(base):
    """Build the minimap screen class against ``base``.

    Done in a function because the base class is discovered at import time; a
    subclass of ``object`` would be wrong for the engine, so callers check
    :data:`HAS_ENGINE_MINIMAP` before registering.
    """

    class DioramaMiniMapScreen(base):
        """HUD screen whose map layer is rendered by the engine."""

        CONTENT_ROOT = "/minimap_root"
        USES_BASE_SCREEN = True

        def __init__(self, namespace, name, param):
            params = dict(param or {})
            params.setdefault(
                "mini_map_root_path", modConfig.MINIMAP_CONTROL_PATH
            )
            base.__init__(self, namespace, name, params)
            self._static_keys = {}
            self._text_keys = {}
            self._entity_markers = []
            self._map = None

        # -- lifecycle ------------------------------------------------

        def Create(self):
            # MiniMapBaseScreen.Create() is what hands the engine its renderer;
            # skipping it yields a blank control.
            try:
                base.Create(self)
            except Exception as exc:  # noqa: BLE001
                warn("minimap base Create failed: %r", exc)
            return True

        def init_screen(self):
            """Called by the engine once the minimap renderer is ready."""
            return True

        def Destroy(self):
            self._static_keys = {}
            self._text_keys = {}
            self._entity_markers = []
            self._map = None
            try:
                base.Destroy(self)
            except Exception as exc:  # noqa: BLE001
                warn("minimap base Destroy failed: %r", exc)

        # -- control --------------------------------------------------

        def map_control(self):
            """The ``MiniMapUIControl``, or ``None`` on a build without one."""
            if self._map is not None:
                return self._map
            control = ui_base.control(self, modConfig.MINIMAP_CONTROL_SUFFIX)
            if control is None:
                return None
            for accessor in ("asMiniMap", "asNeteaseMiniMap"):
                fn = getattr(control, accessor, None)
                if fn is None:
                    continue
                try:
                    found = fn()
                except Exception:  # noqa: BLE001
                    continue
                if found is not None:
                    self._map = found
                    return found
            return None

        # -- markers --------------------------------------------------

        def sync_waypoints(self, waypoints):
            """Make the engine's markers match ``waypoints``.

            ``AddStaticMarker(key, vec2, texturePath)`` keys the marker itself,
            so keeping our own ``key -> key`` map is just bookkeeping for
            removals; the engine owns the actual marker once added.
            """
            control = self.map_control()
            if control is None:
                return 0
            wanted = {}
            for waypoint in waypoints or []:
                key = "%s" % (waypoint.get("id"),)
                wanted[key] = waypoint
            for key in list(self._static_keys):
                if key not in wanted:
                    self._remove_static(control, key)
            for key, waypoint in wanted.items():
                if key in self._static_keys:
                    continue
                sprite = (
                    DEATH_SPRITE
                    if waypoint.get("kind") == "death"
                    else WAYPOINT_SPRITE
                )
                if self._add_static(control, key, waypoint, sprite):
                    self._static_keys[key] = True
            return len(self._static_keys)

        def _add_static(self, control, key, waypoint, sprite):
            fn = getattr(control, "AddStaticMarker", None)
            if fn is None:
                return False
            vec = (float(waypoint.get("x", 0.0)), float(waypoint.get("z", 0.0)))
            try:
                return bool(fn(key, vec, sprite, MARKER_SIZE))
            except TypeError:
                pass
            try:
                return bool(fn(key, vec, sprite))
            except Exception as exc:  # noqa: BLE001
                warn("AddStaticMarker failed: %r", exc)
                return False

        def _remove_static(self, control, key):
            fn = getattr(control, "RemoveStaticMarker", None)
            self._static_keys.pop(key, None)
            if fn is None:
                return False
            try:
                return bool(fn(key))
            except Exception:  # noqa: BLE001
                return False

        def sync_labels(self, waypoints):
            """Optional text markers under each waypoint."""
            control = self.map_control()
            if control is None:
                return 0
            wanted = {}
            for waypoint in waypoints or []:
                text = waypoint.get("name")
                if not text:
                    continue
                wanted["%s" % (waypoint.get("id"),)] = (waypoint, text)
            for key in list(self._text_keys):
                if key not in wanted:
                    self._remove_text(control, key)
            for key, (waypoint, text) in wanted.items():
                if key in self._text_keys:
                    continue
                fn = getattr(control, "AddStaticTextMarker", None)
                if fn is None:
                    break
                vec = (
                    float(waypoint.get("x", 0.0)),
                    float(waypoint.get("z", 0.0)),
                )
                try:
                    fn(key, vec, text)
                    self._text_keys[key] = True
                except Exception as exc:  # noqa: BLE001
                    warn("AddStaticTextMarker failed: %r", exc)
                    break
            return len(self._text_keys)

        def _remove_text(self, control, key):
            fn = getattr(control, "RemoveStaticTextMarker", None)
            self._text_keys.pop(key, None)
            if fn is None:
                return False
            try:
                return bool(fn(key))
            except Exception:  # noqa: BLE001
                return False

        def track_entities(self, entity_ids, rotate=False):
            """Mark live entities; the engine follows them as they move."""
            control = self.map_control()
            if control is None:
                return 0
            wanted = ["%s" % (e,) for e in (entity_ids or [])]
            for tracked in list(self._entity_markers):
                if tracked not in wanted:
                    self._remove_entity(control, tracked)
            for entity_id in wanted:
                if entity_id in self._entity_markers:
                    continue
                fn = getattr(control, "AddEntityMarker", None)
                if fn is None:
                    break
                try:
                    fn(entity_id, PLAYER_SPRITE, MARKER_SIZE, bool(rotate))
                    self._entity_markers.append(entity_id)
                except TypeError:
                    try:
                        fn(entity_id, PLAYER_SPRITE)
                        self._entity_markers.append(entity_id)
                    except Exception as exc:  # noqa: BLE001
                        warn("AddEntityMarker failed: %r", exc)
                        break
                except Exception as exc:  # noqa: BLE001
                    warn("AddEntityMarker failed: %r", exc)
                    break
            return len(self._entity_markers)

        def _remove_entity(self, control, entity_id):
            fn = getattr(control, "RemoveEntityMarker", None)
            if entity_id in self._entity_markers:
                self._entity_markers.remove(entity_id)
            if fn is None:
                return False
            try:
                return bool(fn(entity_id))
            except Exception:  # noqa: BLE001
                return False

        # -- view -----------------------------------------------------

        def set_highest_y(self, value):
            """Only affects chunks the engine has not drawn yet."""
            control = self.map_control()
            fn = getattr(control, "SetHighestY", None) if control is not None else None
            if fn is None:
                return False
            try:
                return bool(fn(int(value)))
            except Exception:  # noqa: BLE001
                return False

        def refresh(self):
            """Force a full repaint, e.g. after a teleport or a dimension change."""
            control = self.map_control()
            fn = getattr(control, "RepaintMiniMap", None) if control is not None else None
            if fn is None:
                return False
            try:
                fn()
                return True
            except Exception:  # noqa: BLE001
                return False

        def zoom(self, direction, step=0.05):
            """Relative zoom: there is no absolute zoom setter in the API."""
            control = self.map_control()
            if control is None:
                return False
            name = "ZoomIn" if direction > 0 else "ZoomOut"
            fn = getattr(control, name, None)
            if fn is None:
                return False
            try:
                fn(float(step))
                return True
            except TypeError:
                try:
                    fn()
                    return True
                except Exception:  # noqa: BLE001
                    return False
            except Exception:  # noqa: BLE001
                return False

        def zoom_reset(self):
            control = self.map_control()
            fn = getattr(control, "ZoomReset", None) if control is not None else None
            if fn is None:
                return False
            try:
                fn()
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
        clientApi.RegisterUI(
            ns, modConfig.UI_MINIMAP, DioramaMiniMapScreen, modConfig.UI_DEF_MINIMAP
        )
        return DioramaMiniMapScreen
    except Exception as exc:  # noqa: BLE001
        warn("RegisterUI(minimap) failed: %r", exc)
        return None
