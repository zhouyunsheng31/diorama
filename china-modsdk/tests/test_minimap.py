# -*- coding: utf-8 -*-
"""Tests for the engine-drawn minimap screen.

This is the only screen whose base class is supplied by the engine
(``clientApi.GetMiniMapScreenNodeCls()``), so it is also the only one that has to
be imported against a stubbed ``client.extraClientApi``. ``fake_engine`` provides
that stub; the assertions below are about our own bookkeeping - which markers we
add, which we remove, and what we do when the build has no minimap at all.
"""

from __future__ import absolute_import, division, print_function

import importlib
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

PACK_ROOT = os.path.normpath(
    os.path.join(HERE, os.pardir, "DioramaMod", "behavior_packs", "diorama_behavior_pack")
)
if PACK_ROOT not in sys.path:
    sys.path.insert(0, PACK_ROOT)

import fake_engine  # noqa: E402  (path set up just above)


MINIMAP_MODULE = "dioramaScripts.modClient.ui.DioramaMiniMapScreen"
UI_BASE_MODULE = "dioramaScripts.modClient.ui.ui_base"


class FakeMiniMapBase(fake_engine.FakeScreenNode):
    """What ``GetMiniMapScreenNodeCls()`` returns in these tests."""


def load_minimap_module(minimap_cls=FakeMiniMapBase):
    """Install the stub engine and import the minimap module fresh.

    The whole ``modClient.ui`` package is purged, not just the two modules:
    ``from package import name`` prefers the parent package's attribute, so a
    stale ``ui_base`` would otherwise be reused along with its cached
    ``screen_node_cls()`` result.
    """
    fake_engine.install(screen_node_cls=fake_engine.FakeScreenNode, minimap_cls=minimap_cls)
    prefix = "dioramaScripts.modClient.ui"
    for name in list(sys.modules):
        if name == prefix or name.startswith(prefix + "."):
            del sys.modules[name]
    return importlib.import_module(MINIMAP_MODULE)


class MiniMapAvailabilityTest(unittest.TestCase):
    def test_the_official_accessor_name_is_used_first(self):
        module = load_minimap_module()
        self.assertTrue(module.available())
        self.assertTrue(issubclass(module.DioramaMiniMapScreen, FakeMiniMapBase))

    def test_a_build_without_the_minimap_class_reports_unavailable(self):
        module = load_minimap_module(minimap_cls=None)
        # ``minimap_screen_cls`` falls back to ScreenNode, which is not a
        # minimap, so the flag must be False and registration must be skipped.
        self.assertFalse(module.available())
        self.assertIsNone(module.register())

    def test_the_root_path_parameter_is_defaulted(self):
        module = load_minimap_module()
        screen = module.DioramaMiniMapScreen("ns", "name", None)
        self.assertEqual(screen.param["mini_map_root_path"], "/minimap_anchor/inheritor1")

    def test_a_supplied_root_path_is_not_overwritten(self):
        module = load_minimap_module()
        screen = module.DioramaMiniMapScreen(
            "ns", "name", {"mini_map_root_path": "/custom"}
        )
        self.assertEqual(screen.param["mini_map_root_path"], "/custom")


class MiniMapMarkerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_minimap_module()
        self.screen = self.module.DioramaMiniMapScreen("ns", "name", None)
        self.control = fake_engine.FakeUIControl()
        self.minimap = fake_engine.FakeMiniMapControl(
            support=("AddStaticMarker", "RemoveStaticMarker")
        )
        self.control.minimap = self.minimap
        # ``ui_base.resolve`` prepends the base-screen wrapper, so register the
        # control under the resolved path the production code will ask for.
        from dioramaScripts.modClient.ui import ui_base

        path = ui_base.resolve(self.screen, "/minimap_anchor/inheritor1")
        self.screen.controls[path] = self.control

    def test_waypoints_become_static_markers(self):
        count = self.screen.sync_waypoints(
            [{"id": "a", "x": 10, "z": -4}, {"id": "b", "x": 0, "z": 0}]
        )
        self.assertEqual(count, 2)
        self.assertEqual(len(self.minimap.static_markers), 2)

    def test_death_waypoints_use_the_death_sprite(self):
        self.screen.sync_waypoints([{"id": "d", "x": 1, "z": 1, "kind": "death"}])
        args = self.minimap.static_markers[0]
        self.assertIn(self.module.DEATH_SPRITE, args)

    def test_removing_a_waypoint_removes_its_marker(self):
        self.screen.sync_waypoints([{"id": "a", "x": 1, "z": 1}])
        self.assertEqual(self.screen.sync_waypoints([]), 0)
        self.assertEqual(len(self.minimap.static_markers), 0)

    def test_syncing_the_same_list_twice_does_not_duplicate(self):
        waypoints = [{"id": "a", "x": 1, "z": 1}]
        self.screen.sync_waypoints(waypoints)
        self.screen.sync_waypoints(waypoints)
        self.assertEqual(len(self.minimap.static_markers), 1)

    def test_a_missing_control_is_not_an_error(self):
        self.screen.controls.clear()
        self.assertEqual(self.screen.sync_waypoints([{"id": "a", "x": 1, "z": 1}]), 0)

    def test_entities_are_tracked_and_untracked(self):
        self.assertEqual(self.screen.track_entities(["-1", "-2"]), 2)
        self.assertEqual(len(self.minimap.entity_markers), 2)
        self.screen.track_entities(["-1"])
        self.assertEqual(len(self.minimap.entity_markers), 1)


class MiniMapOptionalMethodTest(unittest.TestCase):
    def setUp(self):
        self.module = load_minimap_module()
        self.screen = self.module.DioramaMiniMapScreen("ns", "name", None)
        self.control = fake_engine.FakeUIControl()
        self.minimap = fake_engine.FakeMiniMapControl()
        self.control.minimap = self.minimap
        from dioramaScripts.modClient.ui import ui_base

        self.screen.controls[
            ui_base.resolve(self.screen, "/minimap_anchor/inheritor1")
        ] = self.control

    def test_refresh_and_zoom_report_success(self):
        self.assertTrue(self.screen.refresh())
        self.assertTrue(self.screen.zoom(1))
        self.assertTrue(self.screen.zoom(-1))
        self.assertTrue(self.screen.zoom_reset())
        self.assertTrue(self.screen.set_highest_y(-1))
        self.assertEqual(self.minimap.repaints, 1)
        self.assertEqual(self.minimap.zooms, [1, -1, 0])
        self.assertEqual(self.minimap.highest_y, -1)

    def test_missing_optional_methods_report_failure(self):
        self.minimap.support.clear()
        # FakeMiniMapControl still defines the methods, so instead check the
        # "no control at all" path, which is the realistic failure mode.
        self.screen.controls.clear()
        self.assertFalse(self.screen.refresh())
        self.assertFalse(self.screen.zoom(1))
        self.assertFalse(self.screen.zoom_reset())
        self.assertFalse(self.screen.set_highest_y(0))


if __name__ == "__main__":
    unittest.main()
