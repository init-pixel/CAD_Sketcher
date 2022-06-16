from pathlib import Path
from contextlib import contextmanager

import bpy
import bmesh


@contextmanager
def load_mesh(filepath: Path, name: str):
    try:
        with bpy.data.libraries.load(str(filepath)) as (data_from, data_to):
            data_to.meshes = [name]
            mesh = data_to.meshes[name]
        yield mesh
    finally:
        bpy.data.meshes.remove(mesh)


def load_bmesh(filepath: Path, name: str):
    with load_mesh(filepath) as mesh:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        return bm
