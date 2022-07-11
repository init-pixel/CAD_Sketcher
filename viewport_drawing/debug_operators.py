from pathlib import Path

import bpy
import bmesh
from bpy.utils import register_class, unregister_class
from bpy.types import Operator, Context, Event

from .drawing import DrawnMesh

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
        mesh_name = "workplanes"
        blend_file = MESHES_DIR / "workplanes.blend"
        self.workplanes_mesh = DrawnMesh.from_file(blend_file, mesh_name)
        self.draw_handle = None
        self.mouse_xy = None
        self.active_face_maps = None

    def invoke(self, context: Context, event: Event):
        args = (self, context)
        self.draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self.workplanes_mesh.draw, args, "WINDOW", "POST_VIEW"
        )
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _rollover_detect(self, context: Context, event: Event):
        hover_result = self.workplanes_mesh.ray_from_mouse(
            context, event, face_map=True
        )
        if not hover_result.failed:
            self.active_face_maps = [hover_result.face_map]
        else:
            self.active_face_maps = None

    def modal(self, context: Context, event: Event):
        context.area.tag_redraw()
        if event.type == "MOUSEMOVE":
            self.mouse_xy = (event.mouse_region_x, event.mouse_region_y)
            self._rollover_detect(context, event)
        elif event.type == "LEFTMOUSE" and self.active_face_maps is not None:  # Confirm
            bpy.types.SpaceView3D.draw_handler_remove(self.draw_handle, "WINDOW")
            return self.execute(context)
        elif event.type in {"RIGHTMOUSE", "ESC"}:  # Cancel
            bpy.types.SpaceView3D.draw_handler_remove(self.draw_handle, "WINDOW")
            return {"CANCELLED"}
        else:
            return {"PASS_THROUGH"}
        return {"RUNNING_MODAL"}

    def execute(self, context: Context):
        print(self.workplane_face_maps[self.active_face_maps[0]])
        return {"FINISHED"}


ops = (VIEW3D_OT_test_geometry_drawing,)


def register():
    for op in ops:
        register_class(op)


def unregister():
    for op in ops:
        unregister_class(op)
