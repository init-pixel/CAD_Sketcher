import sys
from pathlib import Path
import logging

import bpy
from bpy.types import AddonPreferences, Panel, Menu, Context, UILayout
from bpy.props import (
    PointerProperty,
    BoolProperty,
    StringProperty,
    EnumProperty,
    IntProperty,
    FloatProperty,
)
from bpy.utils import register_class, unregister_class
from bl_ui.utils import PresetPanel

from . import (
    global_data,
    theme,
    units,
    install,
    addon_updater_ops,
    functions,
)


log_levels = [
    ("CRITICAL", "Critical", "", 0),
    ("ERROR", "Error", "", 1),
    ("WARNING", "Warning", "", 2),
    ("INFO", "Info", "", 3),
    ("DEBUG", "Debug", "", 4),
    ("NOTSET", "Notset", "", 5),
]

logger = logging.getLogger(__name__)


def get_log_level(self):
    prop = self.bl_rna.properties["logging_level"]
    items = prop.enum_items
    default_value = items[prop.default].value
    item = items[self.get("logging_level", default_value)]
    return item.value


def set_log_level(self, value):
    items = self.bl_rna.properties["logging_level"].enum_items
    item = items[value]

    level = item.identifier
    logger.info("setting log level: {}".format(item.name))
    self["logging_level"] = level
    logger.setLevel(level)


def get_wheel() -> str:
    """ Get platform appropriate wheel"""
    p = Path(__file__).parent.absolute()
    from sys import platform, version_info

    if platform == "linux" or platform == "linux2":
        # Linux
        platform_strig = "linux"
    elif platform == "darwin":
        # OS X
        platform_strig = "macosx"
    elif platform == "win32":
        # Windows
        platform_strig = "win"

    matches = list(
        p.glob(
            "**/*cp{}{}*{}*.whl".format(
                version_info.major, version_info.minor, platform_strig
            )
        )
    )
    if matches:
        match = matches[0]
        logger.info("Local installation file available: " + str(match))
        return match.as_posix()
    return ""


class SKETCHER_PT_theme_presets(PresetPanel, Panel):
    bl_label = "Theme Presets"
    preset_subdir = "bgs/theme"
    preset_operator = "script.execute_preset"
    preset_add_operator = "bgs.theme_preset_add"


class SKETCHER_MT_theme_presets(Menu):
    bl_label = "Theme Presets"
    preset_subdir = "bgs/theme"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


def get_prefs():
    return bpy.context.preferences.addons[__package__].preferences


def get_scale():
    return bpy.context.preferences.system.ui_scale * get_prefs().entity_scale


def is_experimental():
    return get_prefs().show_debug_settings


class Preferences(AddonPreferences):
    bl_idname = __package__
    theme_settings: PointerProperty(type=theme.ThemeSettings)

    def _toggle_debug_options(self, context: Context):
        """ Callback from debug toggle, reset debug props to defaults """
        debug_props = (
            context.sketcher.show_origin,
            self.hide_inactive_constraints,
            self.all_entities_selectable,
            self.force_redraw,
        )
        if not self.show_debug_settings:
            for prop in debug_props:
                prop = prop.default

    show_debug_settings: BoolProperty(
        name="Show Debug Settings", default=False,
    )
    show_theme_settings: BoolProperty(
        name="Show Theme Settings",
        description="Expand this box to show various theme settings",
        default=False,
    )
    package_path: StringProperty(
        name="Package Filepath",
        description="Filepath to the module's .whl file",
        subtype="FILE_PATH",
        default=get_wheel(),
    )
    logging_level: EnumProperty(
        name="Logging Level",
        items=log_levels,
        get=get_log_level,
        set=set_log_level,
        default=2,
    )
    hide_inactive_constraints: BoolProperty(
        name="Hide inactive Constraints",
        default=True,
        update=functions.update_cb,
        options={"SKIP_SAVE"},
    )
    all_entities_selectable: BoolProperty(
        name="Make all Entities Selectable",
        default=False,
        update=functions.update_cb,
        options={"SKIP_SAVE"},
    )
    force_redraw: BoolProperty(
        name="Force Entity Redraw", default=True, options={"SKIP_SAVE"}
    )

    decimal_precision: IntProperty(
        name="Decimal Precision",
        description="Number of digits after the comma",
        default=3,
        min=0,
        soft_max=7,
    )
    imperial_precision: units.imperial_precision_prop
    angle_precision: IntProperty(
        name="Angle Precision",
        min=0,
        max=5,
        default=0,
        description="Angle decimal precision",
    )

    entity_scale: FloatProperty(
        name="Entity Scale", default=1.0, min=0.1, soft_max=3.0, update=theme.update
    )
    gizmo_scale: FloatProperty(
        name="Icon Scale", default=15.0, min=1.0, soft_max=25.0, update=theme.update
    )
    text_size: IntProperty(name="Text Size", default=15, min=5, soft_max=25)
    arrow_scale: FloatProperty(name="Arrow Scale", default=1, min=0.2, soft_max=3)

    # Addon updater properties
    auto_check_update: BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=False,
    )

    updater_interval_months: IntProperty(
        name="Months",
        description="Number of months between checking for updates",
        default=0,
        min=0,
    )

    updater_interval_days: IntProperty(
        name="Days",
        description="Number of days between checking for updates",
        default=7,
        min=0,
        max=31,
    )

    updater_interval_hours: IntProperty(
        name="Hours",
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23,
    )

    updater_interval_minutes: IntProperty(
        name="Minutes",
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59,
    )

    def draw(self, context: Context):
        layout: UILayout = self.layout
        layout.use_property_split = True

        box = layout.box()
        box.label(text="Solver Module")
        if global_data.registered:
            box.label(text="Registered", icon="CHECKMARK")
            module = sys.modules["py_slvs"]
            box.label(text="Path: " + module.__path__[0])
        else:
            row = box.row()
            row.label(text="Module isn't Registered", icon="CANCEL")
            split = box.split(factor=0.8)
            split.prop(self, "package_path", text="")
            split.operator(
                install.View3D_OT_slvs_install_package.bl_idname,
                text="Install from File",
            ).package = self.package_path

            row = box.row()
            row.operator(
                install.View3D_OT_slvs_install_package.bl_idname,
                text="Install from PIP",
            ).package = "py-slvs"

        box = layout.box()
        box.label(text="General")
        col = box.column(align=True)
        col.prop(self, "entity_scale")
        col.prop(self, "gizmo_scale")
        col.prop(self, "text_size")
        col.prop(self, "arrow_scale")

        box = layout.box()
        box.label(text="Units")
        col = box.column(align=True)
        col.prop(self, "decimal_precision")
        col.prop(self, "imperial_precision")
        col.prop(self, "angle_precision")

        box = layout.box()
        box.label(text="Advanced")
        col = box.column(align=True)
        col.prop(self, "show_debug_settings")
        col.prop(self, "logging_level")

        box = layout.box()
        row = box.row()
        row.use_property_split = False

        subrow = row.row()
        subrow.alignment = "LEFT"
        subrow.prop(
            self,
            "show_theme_settings",
            text="Theme",
            emboss=False,
            icon="TRIA_DOWN" if self.show_theme_settings else "TRIA_RIGHT",
        )

        subrow = row.row()
        subrow.alignment = "RIGHT"
        if global_data.registered:
            SKETCHER_PT_theme_presets.draw_panel_header(subrow)

        if self.show_theme_settings:
            row = box.row()

            row = box.row()
            flow = row.grid_flow(
                row_major=False,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )

            def list_props_recursiv(base):
                for prop in base.rna_type.properties:
                    prop_name = prop.identifier
                    if prop_name in ("name", "rna_type"):
                        continue

                    row = flow.row()
                    if type(prop) == bpy.types.PointerProperty:
                        row.label(text=prop.name)
                        list_props_recursiv(getattr(base, prop_name))
                    else:
                        row.prop(base, prop_name)

            list_props_recursiv(self.theme_settings)

        # TODO: Cleanup updater prop rendering
        # addon_updater_ops.update_settings_ui(self, context)
        addon_updater_ops.update_settings_ui_condensed(self, context)


classes = (
    SKETCHER_MT_theme_presets,
    SKETCHER_PT_theme_presets,
    Preferences,
)


def register():
    for cls in classes:
        register_class(cls)


def unregister():
    for cls in reversed(classes):
        unregister_class(cls)
