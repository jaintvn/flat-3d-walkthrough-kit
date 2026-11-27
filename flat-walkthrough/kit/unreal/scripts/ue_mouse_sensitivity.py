"""Scales mouse look in the first-person template.
    FLAT_MOUSE_SCALE=0.5 UnrealEditor-Cmd FlatTypeG.uproject -run=pythonscript -script=ue_mouse_sensitivity.py
Adds (or updates) a Scalar modifier on IA_MouseLook, the action that only the mouse drives
(gamepad look uses IA_Look and is left alone). Re-running with the same value is idempotent.
"""
import unreal, os

SCALE = float(os.environ.get("FLAT_MOUSE_SCALE", "0.5"))
ACTION = "/Game/Input/Actions/IA_MouseLook"

ia = unreal.load_asset(ACTION)
mods = list(ia.get_editor_property("modifiers"))
sc = next((x for x in mods if x.get_class().get_name() == "InputModifierScalar"), None)
if sc is None:
    sc = unreal.new_object(unreal.InputModifierScalar, outer=ia)
    mods.append(sc)
sc.set_editor_property("scalar", unreal.Vector(SCALE, SCALE, 1.0))
ia.set_editor_property("modifiers", mods)
unreal.EditorAssetLibrary.save_loaded_asset(ia, only_if_is_dirty=False)
for x in unreal.load_asset(ACTION).get_editor_property("modifiers"):
    unreal.log_warning("MOUSESENS %s %s %s" % (ACTION, x.get_class().get_name(),
                                               x.get_editor_property("scalar") if x.get_class().get_name() == "InputModifierScalar" else ""))
