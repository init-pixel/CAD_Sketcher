from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Union

import bpy
from bpy.types import Mesh
import bmesh
from bmesh.types import BMesh


def load_mesh(filepath: Path, name: str):
    with bpy.data.libraries.load(str(filepath)) as (data_from, data_to):
        data_to.meshes = [name]
    return data_to.meshes[0]


@contextmanager
def read_external_mesh(filepath: Path, name: str) -> Generator[Mesh, None, None]:
    """ Context manager for loading a mesh without retaining its datablock """
    try:
        with bpy.data.libraries.load(str(filepath)) as (data_from, data_to):
            data_to.meshes = [name]
        yield data_to.meshes[0]
    finally:
        bpy.data.meshes.remove(data_to.meshes[0])


@contextmanager
def temp_bmesh(mesh: Union[None, Mesh]) -> Generator[BMesh, None, None]:
    """ Context manger for temporary creation of bmesh object """
    try:
        bm = bmesh.new()
        if mesh is not None:
            bm.from_mesh(mesh)
        yield bm
    finally:
        bm.free()


def load_as_bmesh(filepath: Path, name: str):
    with read_external_mesh(filepath, name) as mesh:
        bm = bmesh.new()
        mesh = load_mesh(filepath, name)
        bm.from_mesh(mesh)
    return bm
