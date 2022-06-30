"""
Bpy helper functions whose purpose is to reinterpret geometry for
the purposes of viewport drawing.
"""

from collections import deque
from itertools import count
from typing import Deque, Generator, Tuple, List, Union, Iterable

from bmesh.types import BMesh, BMFace
from mathutils import Vector


def bounding_points_and_edges(bm: BMesh) -> Tuple[Deque[Vector], Deque[int]]:
    """
    Return bounding edge vert locations and indexes to recreate the edges from those positions
    """
    edges = [edge for edge in bm.edges if edge.is_boundary]
    coords = deque()
    indices = deque()
    for co_index, edge in zip(edges, count(step=2)):
        coords.extend([vert.co for vert in edge.verts])
        indices.append((co_index, co_index + 1))
    return coords, indices


def points_and_faces(
    bm: BMesh, face_filter: Union[None, Iterable[BMFace]] = None,
) -> Tuple[Deque[Vector], Deque[int]]:
    """
    Convert bmesh object to coords and tri indices
    Providing a face_filter limits results to the faces of the argument
    """
    if face_filter is None:
        coords = [vert.co for vert in bm.verts]
        indices = [face_vert_indices(face) for face in bm.faces]
    else:
        coords = deque()
        indices = deque()
        for face, tri in zip(face_filter, count(step=3)):
            coords.extend(vert.co for vert in face.verts)
            indices.append((tri, tri + 1, tri + 2))
    return coords, indices


def face_vert_indices(face: BMFace) -> List[int]:
    return [vert.index for vert in face.verts]


def face_map_lookup(bm: BMesh, face_id: int) -> int:
    """ Return face_map index """
    face_maps = bm.faces.layers.face_map.verify()
    return bm.faces[face_id][face_maps]


def faces_by_map_id(bm: BMesh, face_map_id: int) -> Generator[BMFace, None, None]:
    """ Return faces with matching face_layer value """
    face_maps = bm.faces.layers.face_map.verify()
    for face in bm.faces:
        if face[face_maps] == face_map_id:
            yield face
