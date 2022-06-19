from pathlib import Path

import bpy
import bmesh
from bpy.props import IntProperty
from bpy.utils import register_class, unregister_class
from bpy.types import Operator, Context, Event

from .mesh_generation import DrawingMesh
from . import io

SCRIPTS_DIR = Path(__file__).parent
MESHES_DIR = SCRIPTS_DIR / "meshes"


class VIEW3D_OT_test_geometry_drawing(Operator):
    bl_idname = "view3d.test_geometry_drawing"
    bl_label = "Test Geometry Drawing"
    bl_options = {"UNDO"}

    workplane_face_maps = {
        0: "xz",
        1: "xy",
        2: "yz",
    }

    def __init__(self):
        print("STARTING")
        mesh_name = "workplanes"
        blend_file = MESHES_DIR / "workplanes.blend"
        self.workplanes_mesh = DrawingMesh.from_file(blend_file, mesh_name)
        self.handle = None
        self.mouse_xy = None
        self.highlight_faces = None
        self.active_face_map = None

    def invoke(self, context: Context, event: Event):
        args = (self, context)
        self.handle = bpy.types.SpaceView3D.draw_handler_add(
            self.workplanes_mesh.draw, args, "WINDOW", "POST_VIEW"
        )
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _rollover_detect(self, context: Context):
        ray_result = self.workplanes_mesh.ray_from_screen(context, self.mouse_xy)
        if not ray_result.failed:
            face_map_id = self.workplanes_mesh.face_map_lookup(ray_result.index)
            self.active_face_map = face_map_id
            face_map_members = self.workplanes_mesh.faces_by_map_id(face_map_id)
            self.highlight_faces = face_map_members
        else:
            self.highlight_faces = None
            self.active_face_map = None

    def modal(self, context: Context, event: Event):
        context.area.tag_redraw()
        if event.type == "MOUSEMOVE":
            self.mouse_xy = (event.mouse_region_x, event.mouse_region_y)
            self._rollover_detect(context)
        elif event.type == "LEFTMOUSE" and self.active_face_map is not None:  # Confirm
            self.mouse_xy = (event.mouse_region_x, event.mouse_region_y)
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
            return self.execute(context)
        elif event.type in {"RIGHTMOUSE", "ESC"}:  # Cancel
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
            return {"CANCELLED"}
        else:
            return {"PASS_THROUGH"}
        return {"RUNNING_MODAL"}

    def execute(self, context: Context):
        print(self.active_face_map, self.workplane_face_maps[self.active_face_map])
        return {"FINISHED"}


ops = (VIEW3D_OT_test_geometry_drawing,)


def register():
    for op in ops:
        register_class(op)


def unregister():
    for op in ops:
        unregister_class(op)
