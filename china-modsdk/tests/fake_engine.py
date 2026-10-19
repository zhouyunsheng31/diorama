# -*- coding: utf-8 -*-
"""Minimal fake ModSDK engine, so client UI code can be imported and tested.

The real runtime is Python 2 inside the game, and its modules are named
``client.extraClientApi`` / ``server.extraServerApi``. Those do not exist on a
PC, so anything that touches them at import time is untestable unless they are
stubbed. This module installs just enough of them for the UI layer.

Design rules:

* nothing here simulates Minecraft behaviour - it only records calls;
* every attribute the production code might ask for is present, and the fakes
  are deliberately permissive (``*args, **kwargs``) so a signature guess in the
  production code cannot make the test fail for the wrong reason;
* installing twice is a no-op, so tests can call :func:`install` freely.
"""

from __future__ import absolute_import, division, print_function

import sys
import types


class FakeUIControl(object):
    """A UI control that records what was done to it."""

    def __init__(self, name="control"):
        self.name = name
        self.calls = []
        self.visible = True
        self.text = None
        self.sprite = None
        self.position = None
        self.minimap = None

    def _record(self, method, *args):
        self.calls.append((method, args))

    def SetVisible(self, value):
        self.visible = bool(value)
        self._record("SetVisible", value)
        return True

    def SetText(self, value):
        self.text = value
        self._record("SetText", value)
        return True

    def SetSprite(self, value):
        self.sprite = value
        self._record("SetSprite", value)
        return True

    def SetPosition(self, value):
        self.position = value
        self._record("SetPosition", value)
        return True

    def asMiniMap(self):
        return self.minimap

    def asLabel(self):
        return self


class FakeMiniMapControl(object):
    """Stands in for the engine's minimap control object."""

    def __init__(self, support=None):
        #: Names of the optional methods this instance should expose.
        self.support = set(support or ())
        self.static_markers = []
        self.entity_markers = []
        self.repaints = 0
        self.zooms = []
        self.zoom_value = None

    def AddStaticMarker(self, *args):
        if "AddStaticMarker" not in self.support:
            raise AttributeError("AddStaticMarker")
        self.static_markers.append(args)
        return len(self.static_markers)

    def RemoveStaticMarker(self, *args):
        if "RemoveStaticMarker" not in self.support:
            raise AttributeError("RemoveStaticMarker")
        marker = args[0] if args else None
        if marker in self.static_markers:
            self.static_markers.remove(marker)
            return True
        # Tolerate the index form the production code may pass.
        index = int(marker) - 1 if isinstance(marker, int) else -1
        if 0 <= index < len(self.static_markers):
            self.static_markers.pop(index)
            return True
        return False

    def AddEntityMarker(self, *args):
        self.entity_markers.append(args)
        return len(self.entity_markers)

    def RemoveEntityMarker(self, *args):
        entity_id = args[0] if args else None
        self.entity_markers = [e for e in self.entity_markers if e[0] != entity_id]
        return True

    def RepaintMiniMap(self):
        self.repaints += 1
        return True

    def ZoomIn(self):
        self.zooms.append(1)
        return True

    def ZoomOut(self):
        self.zooms.append(-1)
        return True

    def SetZoom(self, value):
        self.zoom_value = value
        return True


def _module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def install(screen_node_cls=None, minimap_cls=None, extra=None):
    """Install ``client.extraClientApi`` (and a server stub) into ``sys.modules``.

    ``screen_node_cls`` is what ``GetScreenNodeCls`` returns; ``minimap_cls`` is
    what ``GetMiniMapScreenNodeCls`` returns (pass ``None`` to simulate a build
    that does not expose the engine minimap).
    """
    base = screen_node_cls or FakeScreenNode

    recorded = {"registered": [], "created": []}

    def RegisterUI(namespace, key, cls, def_name):
        recorded["registered"].append((namespace, key, cls, def_name))
        return True

    def CreateUI(namespace, key, params=None):
        recorded["created"].append((namespace, key, params))
        return None

    attrs = {
        "GetScreenNodeCls": lambda: base,
        "GetUIScreenCls": lambda: base,
        "RegisterUI": RegisterUI,
        "CreateUI": CreateUI,
        "PushScreen": lambda *a, **k: True,
        "PopScreen": lambda *a, **k: True,
        "PopTopUI": lambda *a, **k: True,
        "GetUI": lambda *a, **k: None,
        "GetLevelId": lambda: "0",
        "GetLocalPlayerId": lambda: "-1",
        "GetEngineNamespace": lambda: "engine",
        "GetEngineSystemName": lambda: "engineSystem",
        "GetEngineCompFactory": lambda: FakeFactory(),
        "GetViewBinderCls": lambda: FakeViewBinder,
        "GetViewViewRequestCls": lambda: FakeViewRequest,
        "Recorded": recorded,
    }
    if minimap_cls is not None:
        attrs["GetMiniMapScreenNodeCls"] = lambda: minimap_cls
    if extra:
        attrs.update(extra)

    client_module = _module("client", extraClientApi=None)
    api_module = _module("client.extraClientApi", **attrs)
    client_module.extraClientApi = api_module

    server_api = _module(
        "server.extraServerApi",
        GetServerSystemCls=lambda: FakeServerSystem,
        GetEngineNamespace=lambda: "engine",
        GetEngineSystemName=lambda: "engineSystem",
        GetLevelId=lambda: "0",
        GetEngineCompFactory=lambda: FakeFactory(),
    )
    server_pkg = _module("server", extraServerApi=server_api)

    sys.modules["client"] = client_module
    sys.modules["client.extraClientApi"] = api_module
    sys.modules["server"] = server_pkg
    sys.modules["server.extraServerApi"] = server_api
    return api_module


class FakeViewBinder(object):
    BF_BindBool = 5
    BF_BindInt = 6
    BF_BindFloat = 7
    BF_BindString = 8
    BF_BindGridSize = 9
    BF_BindColor = 10
    BF_ButtonClick = 2
    BF_ToggleChanged = 13

    @staticmethod
    def binding(flag, name=None):
        def decorator(fn):
            fn.binding_flag = flag
            fn.binding_name = name
            return fn

        return decorator

    @staticmethod
    def binding_collection(flag, collection, name=None):
        def decorator(fn):
            fn.binding_flag = flag
            fn.binding_collection = collection
            fn.binding_name = name
            return fn

        return decorator


class FakeViewRequest(object):
    Nothing = 0
    Refresh = 1
    Exit = 8


class FakeScreenNode(object):
    """Base class the fake ``GetScreenNodeCls`` returns."""

    def __init__(self, namespace=None, name=None, param=None):
        self.namespace = namespace
        self.name = name
        self.param = param or {}
        self.controls = {}
        self.created = False
        self.initialised = False

    def GetBaseUIControl(self, path):
        return self.controls.get(path)

    def Create(self):
        self.created = True
        return True

    def init_screen(self):
        self.initialised = True
        return True

    def Update(self):
        return True


class FakeServerSystem(object):
    def __init__(self, namespace=None, name=None):
        self.namespace = namespace
        self.name = name

    def ListenForEvent(self, *args, **kwargs):
        return True

    def NotifyToClient(self, *args, **kwargs):
        return True


class FakeFactory(object):
    def __call__(self):
        return self

    def CreateGame(self, *args, **kwargs):
        return FakeGame()

    def CreateConfigClient(self, *args, **kwargs):
        return None


class FakeGame(object):
    def AddRepeatedTimer(self, interval, callback):
        return 1

    def CancelTimer(self, timer):
        return True
