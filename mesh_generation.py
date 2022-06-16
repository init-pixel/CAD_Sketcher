"""
General mesh generation functions for rendering and datablock creation
"""

from __future__ import annotations
from functools import cached_property
from pathlib import Path
from collections import deque
from typing import Iterable, List, Tuple
from dataclasses import dataclass
import numpy as np

# import bpy
import bmesh
from bmesh.types import BMesh, BMVert, BMFace
from mathutils import Vector
from gpu.types import GPUIndexBuf, GPUVertBuf, GPUVertFormat

from . import io

CACHE_LOCATION = Path(__file__).parent / "cache"


@dataclass
class DrawingMesh:
    """ Mesh representation for viewport drawing """

    bm: BMesh
    double_sided: bool = True

    @classmethod
    def from_file(cls, filepath: Path, double_sided: bool = True) -> DrawingMesh:
        return cls(io.load_bmesh(filepath))

    @cached_property
    def gpu_buffers(self) -> Tuple[GPUVertBuf, GPUIndexBuf]:
        """ Convert bmesh object to GPUIndexBuf """
        bm = bm.copy()
        if self.double_sided:
            geom = bm.verts[:] + bm.faces[:]
            ret = bmesh.ops.duplicate(bm, geom=geom)
            backfaces = [elem for elem in ret["geom"] if isinstance(elem, BMFace)]
            bmesh.ops.reverse_faces(bm, faces=backfaces)

        bmesh.ops.triangulate(bm, bm.faces)
        bm.verts.ensure_lookup_table()

        vert_buffer = self.bm_verts_to_vertbuf(bm)
        index_buffer = self.bm_faces_to_indexbuf(bm.faces)

        bm.free()
        return vert_buffer, index_buffer

    @cached_property
    def vertbuf(self) -> GPUVertBuf:
        verts = self.bm.verts
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

    @staticmethod
    def face_vert_indices(face: BMFace) -> List[int]:
        """ Get vert indices from face """
        return [vert.index for vert in face.verts]

    @cached_property
    def indexbuf(self) -> GPUIndexBuf:
        faces = self.bm.faces
        index_sets = [self.face_vert_indices(face) for face in faces]
        return GPUIndexBuf(type="TRIS", seq=index_sets)
