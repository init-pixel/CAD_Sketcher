"""
General mesh generation functions for rendering and datablock creation
"""

from __future__ import annotations
from functools import cached_property
from itertools import chain
from pathlib import Path
from typing import Iterable, Tuple, Union, NamedTuple
from dataclasses import dataclass

import bmesh
from bmesh.types import BMesh, BMFace
from bpy.types import Operator, Context, Event
from bpy_extras import view3d_utils
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import gpu
from gpu_extras.batch import batch_for_shader

from . import io
from .geo import (
    face_map_lookup,
    faces_by_map_id,
    points_and_faces,
)


CACHE_LOCATION = Path(__file__).parent / "cache"


class RaycastResult(NamedTuple):
    """ Return from raycast """

    location: Union[None, Vector]
    normal: Union[None, Vector]
    index: Union[None, int]
    distance: Union[None, float]

    @property
    def failed(self):
        return self.location is None


class MouseHoverResult(NamedTuple):
    """ Return from mouse hover test """

    # TODO: Distance?
    face_id: Union[None, int] = None
    face_map: Union[None, int] = None
    vert_id: Union[None, int] = None
    edge_id: Union[None, int] = None

    @property
    def failed(self):
        results = (self.face_id, self.face_map, self.vert_id, self.edge_id)
        return all((val is None for val in results))


@dataclass
class DrawnMesh:
    """ Mesh representation for viewport drawing """

    bm: BMesh
    double_sided: bool = True
    passive_color: Tuple[float] = (1, 1, 0, 1)
    active_color: Tuple[float] = (1, 1, 1, 1)
    scaler: float = 1.0
    view_distance: float = 0

    def __post_init__(self):
        bmesh.ops.triangulate(self.bm, faces=self.bm.faces)
        if self.double_sided:
            geom = self.bm.verts[:] + self.bm.faces[:]
            ret = bmesh.ops.duplicate(self.bm, geom=geom)
            backfaces = [elem for elem in ret["geom"] if isinstance(elem, BMFace)]
            bmesh.ops.reverse_faces(self.bm, faces=backfaces)
        self.bm.verts.ensure_lookup_table()
        self.bm.faces.ensure_lookup_table()

    @cached_property
    def _xformed_bm(self) -> BMesh:
        copy = self.bm.copy()
        scaler = Vector.Fill(3, self.scaler / 2)
        bmesh.ops.scale(copy, vec=scaler, verts=copy.verts[:])
        copy.verts.ensure_lookup_table()
        copy.faces.ensure_lookup_table()
        return copy

    @cached_property
    def _bvh(self) -> BVHTree:
        return BVHTree.FromBMesh(self._xformed_bm)

    @classmethod
    def from_file(
        cls,
        filepath: Path,
        name: str,
        double_sided: bool = False,
        passive_color: Tuple[float] = (1, 1, 0, 1),
        active_color: Tuple[float] = (1, 1, 1, 1),
    ) -> DrawnMesh:
        """ Instantiate from a filepath """
        return cls(
            io.load_as_bmesh(filepath, name),
            double_sided=double_sided,
            passive_color=passive_color,
            active_color=active_color,
        )

    def ray_from_mouse(
        self,
        context: Context,
        event: Event,
        face_id: bool = True,
        face_map: bool = False,
        # vert_id: bool = False,
        # edge_id: bool = False,
    ) -> MouseHoverResult:
        """ Check for geometry under mouse in region context """
        # TODO: Support for vert and edge detection
        mouse_xy = (event.mouse_region_x, event.mouse_region_y)
        ray_result = self._ray_from_screen(context, mouse_xy)
        if ray_result.failed:
            return MouseHoverResult()
        return MouseHoverResult(
            face_id=ray_result.index if face_id else None,
            face_map=face_map_lookup(self._xformed_bm, ray_result.index)
            if face_map
            else None,
        )

    def _clear_cache(self):
        try:
            self._xformed_bm.free()
            del self._xformed_bm
            del self._passive_batch
            del self._bvh
        except AttributeError:
            pass

    def draw(self, operator: Operator, context: Context):
        """" TODO: Investigate odd behaviour around perspective zooming """
        view_distance_changed = self.view_distance != context.region_data.view_distance
        if view_distance_changed:
            self.view_distance = context.region_data.view_distance
            self._clear_cache()
            self.scaler = self.view_distance / 2
            # NOTE: Hacky scaling fix
            self.scaler = max(3, self.scaler)

        shader = self._passive_shader
        shader.bind()
        shader.uniform_float("color", self.passive_color)
        self._passive_batch.draw(shader)

        active_face_maps = getattr(operator, "active_face_maps")
        if active_face_maps is not None:
            faces = chain.from_iterable(
                (faces_by_map_id(self._xformed_bm, id) for id in active_face_maps)
            )
            shader.uniform_float("color", self.active_color)
            highlight_batch = self._active_batch(faces)
            highlight_batch.draw(shader)

    @cached_property
    def _passive_shader(self):
        """ Base shader, for use with everything not highlighted/active """
        return gpu.shader.from_builtin("3D_UNIFORM_COLOR")

    @cached_property
    def _passive_batch(self):
        """ Base drawing, all geometry drawn on every frame """
        points, indices = points_and_faces(self._xformed_bm)
        content = {"pos": points}
        return batch_for_shader(self._passive_shader, "TRIS", content, indices=indices)

    def _active_batch(self, faces: Iterable[BMFace]):
        points, indices = points_and_faces(self._xformed_bm, face_filter=faces)
        content = {"pos": points}
        return batch_for_shader(self._passive_shader, "TRIS", content, indices=indices)

    def _ray_from_screen(self, context: Context, xy: Vector) -> RaycastResult:
        region = context.region
        rv3d = context.region_data
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
        result = self._bvh.ray_cast(ray_origin, view_vector)
        return RaycastResult(*result)
