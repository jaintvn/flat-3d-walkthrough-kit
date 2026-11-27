"""Furnishing categories for variants (Furnished / SemiFurnished / Unfurnished).

Every object gets a custom property 'flat_cat'. export_ue.py writes it to scene.json ('cat'); the variant scripts
(unreal/scripts/ue_variant.py, blender_variant.py) remove objects by category, using unreal/scripts/variants.json.
Builders set it explicitly with  ob["flat_cat"] = "wardrobe"  (preferred), or name objects so RULES below match.
tag_all() fills in only objects that have no category yet and returns the untagged names (should be architecture).

Categories
  arch              walls, floors, ceilings slab, doors, windows, sliders, railings, ducts, skirting
  bath_fitting      WC, basin, taps, shower, glass partition, towel rail, exhaust fan, vanity
  mirror, switch, wall_finish (mouldings, fluted panels, feature walls that are part of the builder finish)
  kitchen_fitted    cabinets, counter, splashback, sink, hob, chimney, under-cabinet LEDs
  appliance         fridge, washing machine, microwave, TV screen counts as 'tv'
  wardrobe, false_ceiling (bands, coves, cove LEDs, downlight trims), light_fitting (pendants, sconces, downlights +
  their light sources), fan
  loose_furniture   sofa, chairs, tables, side tables, consoles;  bed;  study (desk, desk chair, desk lamp);  tv (TV + unit)
  soft_furnishing   rugs, runners, cushions/throws not part of furniture, towels;  curtain (curtains, sheers, rods)
  decor             vases, books, frames, art, jars, boards;  plant;  balcony_furniture
  context           outside placeholders / environment (never removed by variants)
"""
import re
import bpy

RULES = [  # (regex on object name, category) - first match wins. Type G naming: <ROOM>_<Item>
    (r"^CTX_|^ENV_|^SM_ENV_|^TREE_", "context"),
    (r"_Mirror", "mirror"),
    (r"^SW_|_Switch", "switch"),
    (r"^FC_|_Cove|DownlightTrim", "false_ceiling"),
    (r"_CeilingFan|^LGT_Fan", "fan"),
    (r"_Pendant|_Sconce|_Downlight|^LGT_.*Pend|^LGT_.*Sconce|^LGT_Downlight|_DeskLamp", "light_fitting"),
    (r"_Wardrobe", "wardrobe"),
    (r"_Fridge|_WashingMachine|^KIT_WM_|_Microwave", "appliance"),
    (r"^KIT_(Jar|Board|Herb)", "decor"),
    (r"^KIT_", "kitchen_fitted"),
    (r"_TVWall|Moulding|_Fluted|_FeatureWall", "wall_finish"),
    (r"_TV", "tv"),
    (r"_Bed_|_Bed$", "bed"),
    (r"_StudyDesk|_DeskChair|_DeskBooks", "study"),
    (r"^BAL\d_(Chair|SideTable|Table)", "balcony_furniture"),
    (r"Plant|_Herb", "plant"),
    (r"_Curtain", "curtain"),
    (r"_Rug$|_Runner$|_Towel$|HandTowel", "soft_furnishing"),
    (r"_Vase|Books|_PhotoFrame|_Painting|_Art$|_Frame$", "decor"),
    (r"_Sofa|_Armchair|_CoffeeTable|_Table_|_Chair_|_SideTable|_Console", "loose_furniture"),
    (r"^(T\d|VAN)_|_WC|_Basin|_Tap|_Shower|_TowelRail|_Exhaust", "bath_fitting"),
    (r"_Panel", "wall_finish"),
]
_RX = [(re.compile(p), c) for p, c in RULES]


def category_for(name):
    for rx, c in _RX:
        if rx.search(name):
            return c
    return ""


def tag_all():
    untagged = []
    for ob in bpy.data.objects:
        if ob.get("flat_cat"):
            continue
        c = category_for(ob.name)
        if c:
            ob["flat_cat"] = c
        elif ob.type in ("MESH", "LIGHT"):
            ob["flat_cat"] = "arch" if ob.type == "MESH" else "light_other"
            untagged.append(ob.name)
    return untagged
