# -*- coding: utf-8 -*-
"""Official ModSDK rendering adapters for the Diorama fullscreen mode.

The adapters are deliberately defensive because VirtualWorld, block geometry and
PaperDoll support vary by client build. They never replace the tested pure core:
they only turn a palette/geometry produced by the server into an optional client
presentation. Missing APIs fall back to the ordinary JSON atlas screen.
"""
from __future__ import absolute_import, division, print_function, unicode_literals


class WorldDioramaComponent(object):
    """Own one VirtualWorld and one block-geometry presentation per client."""

    def __init__(self, client):
        self.client = client
        self.api = getattr(client, "api", None)
        self.level_id = getattr(client, "level_id", None)
        self.virtual = None
        self.virtual_objects = []
        self.geometry_names = {}

    def _factory_component(self, creator):
        try:
            factory = self.api.GetEngineCompFactory()
            return getattr(factory, creator)(self.level_id)
        except Exception:
            return None

    def ensure_virtual_world(self):
        if self.virtual is None:
            self.virtual = self._factory_component("CreateVirtualWorld")
            if self.virtual is None:
                return False
            try:
                self.virtual.VirtualWorldCreate()
            except Exception:
                return False
        return True

    def show_virtual(self, visible=True):
        if not self.ensure_virtual_world():
            return False
        try:
            return bool(self.virtual.VirtualWorldToggleVisibility(bool(visible)))
        except Exception:
            return False

    def destroy_virtual(self):
        if self.virtual is None:
            return True
        try:
            self.virtual.VirtualWorldDestroy()
        except Exception:
            return False
        self.virtual = None
        self.virtual_objects = []
        return True

    def set_camera(self, pos, target, fov=45.0, zoom=1.0):
        if not self.ensure_virtual_world():
            return False
        try:
            self.virtual.CameraSetPos(tuple(pos))
            self.virtual.CameraLookAt(tuple(target), (0, 1, 0))
            self.virtual.CameraSetFov(float(fov))
            self.virtual.CameraSetZoom(float(zoom))
            return True
        except Exception:
            return False

    def add_minecraft_model(self, identifier, pos, scale=(1, 1, 1)):
        if not self.ensure_virtual_world():
            return -1
        try:
            object_id = self.virtual.ModelCreateMinecraftObject(identifier)
            if int(object_id) < 0:
                return -1
            self.virtual.ModelSetPos(object_id, tuple(pos))
            self.virtual.ModelSetScale(object_id, tuple(scale))
            self.virtual.MoveToVirtualWorld(3, object_id)  # VirtualWorldObjectType.Model
            self.virtual_objects.append(object_id)
            return object_id
        except Exception:
            return -1

    def render_block_geometry(self, screen, control_path, palette, geometry_name="diorama_map"):
        """Render a palette inside a PaperDoll control when supported.

        ``palette`` may be either a live BlockPalette object or the plain dict
        that ``SerializeBlockPalette`` produced on the server; the dict is
        deserialized here because the serialized form is what crosses the
        client/server event boundary. ``geometry_name`` is reused on purpose:
        the docs say reusing a name for an identical model saves model memory.
        The JSON atlas screen remains the fallback.
        """
        if screen is None or palette is None:
            return False
        try:
            geometry_api = self._factory_component("CreateBlockGeometry")
            if geometry_api is None:
                return False
            live = palette
            if isinstance(palette, dict):
                live = geometry_api.DeserializeBlockPalette(palette)
                if live is None:
                    return False
            geometry = geometry_api.CombineBlockPaletteToGeometry(live, geometry_name, 0)
            if not geometry:
                return False
            control = screen.GetBaseUIControl(control_path)
            doll = control.asNeteasePaperDoll()
            doll.RenderBlockGeometryModel({"geometry_name": geometry})
            self.geometry_names[geometry_name] = geometry
            return True
        except Exception:
            return False
