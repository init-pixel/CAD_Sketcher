import logging
from typing import Tuple

import bpy
from bpy.types import Context, Scene

from . import bl_info

logger = logging.getLogger(__name__)


def get_addon_version() -> Tuple[int]:
    return bl_info["version"]


def write_addon_version(context: Context):
    """ Write addon version to all scene's sketcher property group """
    version = get_addon_version()

    logger.debug("Writing addon version: " + str(version))

    # NOTE: Version is written to every scene because there's no global
    # place we can put this value
    for scene in bpy.data.scenes:
        scene.sketcher.version = version


def recalc_pointers(scene: Scene):
    """Updates type index of entities keeping local index as is"""
    from .class_defines import update_pointers, SlvsEntities

    msg = ""
    entities = list(scene.sketcher.entities.all)
    for entity in reversed(entities):
        i = entity.slvs_index
        # scene.sketcher.entities._set_index(e)
        SlvsEntities.recalc_type_index(entity)

        if i != entity.slvs_index:
            msg += "\n - {}: {} -> {}".format(entity, i, entity.slvs_index)
            update_pointers(scene, i, entity.slvs_index)

    if msg:
        logger.debug("Update entity indices:" + msg)


def do_versioning(self):
    """ Event handler """
    from . import bl_info

    logger.debug("Check versioning")

    # Current blender version
    current_version = bpy.context.preferences.version
    # blender version this file was saved with
    file_version = bpy.data.version
    # Current addon version
    current_addon_version = bl_info["version"]
    # "Blender Version: ", current_version,
    # "\nFile Blender Version: ", file_version,
    # "\nAddon Version: ", current_addon_version,
    # "\nFile Addon Version", file_addon_version,

    # NOTE: Versioning is done per scene

    msg = "\nUpdate existing file to version {}".format(current_addon_version)
    context = bpy.context

    current_version = get_addon_version()
    for scene in bpy.data.scenes:
        props = scene.sketcher

        if not props.is_property_set("version"):
            continue

        # Scene addon version
        version = props.version[:]

        if version > current_version:
            logger.warning(
                "Scene {} was saved with a newer version of the addon".format(
                    scene.name
                )
            )
            continue

        msg += "\n  - Update scene <{}> from version {}".format(scene.name, version)

        # if version <= (0, 11, 0):
        # apply some changes that were introduced in v(0, 11, 0)

        # if version <= (1, 0, 0):
        # ...
        if version < (0, 23, 0):
            entities = scene.sketcher.entities
            entities.origin_axis_X = None
            entities.origin_plane_YZ = None
            entities.ensure_origin_elements(context)

    logger.debug(msg)
