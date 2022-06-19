"""
General mesh generation functions for rendering and datablock creation
"""

from __future__ import annotations
from functools import cached_property
from pathlib import Path
from collections import deque
from itertools import count
from typing import Iterable, List, Union, Generator
from dataclasses import dataclass

import bmesh
from bmesh.types import BMesh, BMVert, BMFace, BMEdge
from bpy.types import Operator, Context
from bpy_extras import view3d_utils
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import gpu
from gpu_extras.batch import batch_for_shader

from . import io

CACHE_LOCATION = Path(__file__).parent / "cache"


@dataclass
class RayReturn:
    location: Union[None, Vector]
    normal: Union[None, Vector]
    index: Union[None, Vector]
    distance: Union[None, Vector]

    @property
    def failed(self):
        return self.location is None


@dataclass
class DrawingMesh:
    """ Mesh representation for viewport drawing """

    bm: BMesh
    double_sided: bool = True
    bvh_tree: Union[None, BVHTree] = None
    use_bvh: bool = True

    def __post_init__(self):
        bmesh.ops.triangulate(self.bm, faces=self.bm.faces)
        if self.use_bvh:
            self.bvh_tree = BVHTree.FromBMesh(self.bm)
        if self.double_sided:
            geom = self.bm.verts[:] + self.bm.faces[:]
            ret = bmesh.ops.duplicate(self.bm, geom=geom)
            backfaces = [elem for elem in ret["geom"] if isinstance(elem, BMFace)]
            bmesh.ops.reverse_faces(self.bm, faces=backfaces)
        self.bm.verts.ensure_lookup_table()
        self.bm.faces.ensure_lookup_table()

    @classmethod
    def from_file(
        cls, filepath: Path, name: str, double_sided: bool = False, bvh: bool = True
    ) -> DrawingMesh:
        return cls(
            io.load_as_bmesh(filepath, name), double_sided=double_sided, use_bvh=bvh
        )

    @cached_property
    def _shader(self):
        return gpu.shader.from_builtin("3D_UNIFORM_COLOR")

    @cached_property
    def _base_batch(self):
        points, indices = self._points_and_faces()
        content = {"pos": points}
        return batch_for_shader(self._shader, "TRIS", content, indices=indices)

    def _highlight_batch(self, faces: Iterable[BMFace]):
        points, indices = self._points_and_faces(face_filter=faces)
        content = {"pos": points}
        return batch_for_shader(self._shader, "TRIS", content, indices=indices)

    def draw(self, operator: Operator, context: Context):
        shader = self._shader
        shader.bind()
        shader.uniform_float("color", (1, 1, 0, 1))
        self._base_batch.draw(shader)

        if operator.highlight_faces is not None:
            shader.uniform_float("color", (1, 1, 1, 1))
            highlight_batch = self._highlight_batch(operator.highlight_faces)
            highlight_batch.draw(shader)

    def ray_from_screen(self, context: Context, mouse_xy: Vector) -> RayReturn:
        region = context.region
        rv3d = context.region_data
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse_xy)
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse_xy)
        result = self.bvh_tree.ray_cast(ray_origin, view_vector)
        return RayReturn(*result)

    def face_map_lookup(self, face_id: int) -> int:
        """ Return face_map index """
        face_maps = self.bm.faces.layers.face_map.verify()
        return self.bm.faces[face_id][face_maps]

    def faces_by_map_id(self, face_map_id: int) -> Generator[BMFace]:
        """ Return faces with matching face_layer value """
        face_maps = self.bm.faces.layers.face_map.verify()
        for face in self.bm.faces:
            if face[face_maps] == face_map_id:
                yield face

    def _points_and_faces(self, face_filter: Union[None, Iterable[BMFace]] = None):
        """ Convert bmesh object to coords and tri indices """
        if face_filter is None:
            coords = [tuple(vert.co) for vert in self.bm.verts]
            indices = [self._face_vert_indices(face) for face in self.bm.faces]
        else:
            coords = deque()
            indices = deque()
            for face, tri in zip(face_filter, count(step=3)):
                coords.extend(vert.co for vert in face.verts)
                indices.append((tri, tri + 1, tri + 2))
        return coords, indices

    @cached_property
    def _bounding_points_and_edges(self):
        edges = [edge for edge in self.bm.edges if edge.is_boundary]
        coords = deque()
        indices = deque()
        for co_index, edge in zip(edges, count(step=2)):
            coords.extend([vert.co for vert in edge.verts])
            indices.append((co_index, co_index + 1))
        return coords, indices

    @staticmethod
    def _face_vert_indices(face: BMFace) -> List[int]:
        """ Get vert indices from face """
        return [vert.index for vert in face.verts]
