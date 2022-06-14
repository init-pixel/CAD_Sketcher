"""
General mesh generation functions for rendering and datablock creation

TODO: Caching mechansm for mesh data?

"""

from pathlib import Path
from collections import deque
from typing import Iterable, List, Tuple
from dataclasses import dataclass
import numpy as np

import bpy
import bmesh
from bmesh.types import BMesh, BMVert, BMFace
from mathutils import Vector
from gpu.types import GPUIndexBuf, GPUVertBuf, GPUVertFormat

CACHE_LOCATION = Path(__file__).parent / "cache"


@dataclass
class np_mesh:
    """ numpy representation of mesh for caching """

    verts: np.ndarray
    normals: np.ndarray
    faces: np.ndarray

    @classmethod
    def from_file(cls, filename: str):
        ...

    def write(self, filename: str):
        ...


def face_vert_indices(face: BMFace) -> List[int]:
    """ Get vert indices from face """
    return [vert.index for vert in face.verts]


def bm_verts_to_vertbuf(verts: Iterable[BMVert]) -> GPUVertBuf:
    fmt = GPUVertFormat()
    fmt.attr_add(id="pos", comp_type="F32", len=3, fetch_mode="FLOAT")
    fmt.attr_add(id="normal", comp_type="F32", len=3, fetch_mode="FLOAT")

    locs = deque()
    normals = deque()
    for index, vert in enumerate(verts):
        locs.append(vert.co)
        normals.append(vert.normal)

    n_verts = index + 1
    vert_buf = GPUVertBuf(len=n_verts, format=fmt)
    vert_buf.attr_fill(id="pos", data=locs)
    vert_buf.attr_fill(id="normal", data=normals)
    return vert_buf


def bm_faces_to_indexbuf(faces: Iterable[BMVert]) -> GPUIndexBuf:
    index_sets = [face_vert_indices(face) for face in faces]
    return GPUIndexBuf(type="TRIS", seq=index_sets)


def bmesh_to_gpu_buffers(
    bm: BMesh, double_sided: bool = False
) -> Tuple[GPUVertBuf, GPUIndexBuf]:
    """ Convert bmesh object to GPUIndexBuf """
    bm = bm.copy()
    if double_sided:
        geom = bm.verts[:] + bm.faces[:]
        ret = bmesh.ops.duplicate(bm, geom=geom)
        backfaces = [elem for elem in ret["geom"] if isinstance(elem, BMFace)]
        bmesh.ops.reverse_faces(bm, faces=backfaces)

    bmesh.ops.triangulate(bm, bm.faces)
    bm.verts.ensure_lookup_table()

    vert_buffer = bm_verts_to_vertbuf(bm)
    index_buffer = bm_faces_to_indexbuf(bm.faces)

    bm.free()
    return vert_buffer, index_buffer


# Testing
