"""In-editor verification of the Type G level. Launched through Content/Python/init_unreal.py:
    FLAT_RUN=<this file> FLAT_QUIT=1 UnrealEditor FlatTypeG.uproject

1. Character tuning on BP_FirstPersonCharacter (walk speed, capsule 25 cm, first-person arms hidden).
2. Player-capsule sweeps along walking routes from the spawn point into every room (through each doorway).
3. Navmesh build + path queries from the spawn to every room.
4. Floor-hole check: downward traces on a 25 cm grid inside each room.
5. Viewport screenshots from fixed eye-height cameras (Saved/Screenshots/...).
Writes verify/verify_report.json and quits when FLAT_QUIT=1.
"""
import unreal, json, os, math

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "verify")
os.makedirs(OUT, exist_ok=True)
MAP = "/Game/Flat/Maps/L_FlatTypeG"
R = {"routes": {}, "paths": {}, "floor": {}, "shots": [], "notes": []}
CAP_R, CAP_HH = 25.0, 88.0


def ue(x, y, z=0.0):            # plan cm (layout.py) -> UE cm
    return unreal.Vector(x, -y, z)


SPAWN = (1520, 60)
ROUTES = {  # waypoint chains in plan coordinates, all starting at the spawn point
    "Living": [SPAWN, (1500, 86), (1380, 86)],
    "Dining": [SPAWN, (1500, 86), (1380, 86), (1180, 78), (1185, 375), (1060, 375)],
    "Kitchen": [SPAWN, (1500, 86), (1380, 86), (1180, 78), (1185, 375), (1300, 360), (1330, 430)],
    "Balcony2": [SPAWN, (1500, 86), (1380, 86), (1180, 78), (1185, 375), (1050, 375), (1030, 470)],
    "Vanity": [SPAWN, (1500, 86), (1380, 86), (1180, 78), (900, 75), (819, 75), (819, 128)],
    "Bed2": [SPAWN, (1500, 86), (1380, 86), (1180, 78), (900, 75), (686, 95), (676, 270), (500, 290)],
    "Toilet2": [SPAWN, (1500, 86), (1380, 86), (1180, 78), (900, 75), (686, 95), (690, 262), (785, 262), (780, 420)],
    "Bed1": [SPAWN, (1500, 86), (1380, 86), (1180, 78), (900, 75), (600, 105), (470, 105), (282, 120), (282, 290), (200, 290)],
    "Toilet1": [SPAWN, (1500, 86), (1380, 86), (1180, 78), (900, 75), (600, 105), (470, 105), (282, 120), (282, 290), (188, 330), (188, 440)],
    "Balcony1": [SPAWN, (1500, 86), (1380, 86), (1180, 78), (900, 75), (600, 105), (470, 105), (282, 120), (282, 285), (102, 285), (102, 420)],
    "Passage": [SPAWN, (1520, -130)],
}
FLOOR_RECTS = {"Living": (1210, 1585, 5, 295), "Dining": (910, 1205, 5, 410), "Kitchen": (1232, 1585, 315, 548),
               "Bed1": (5, 385, 5, 308), "Bed2": (406, 728, 166, 548), "Foyer": (550, 900, 5, 145),
               "Toilet1": (154, 386, 406, 548), "Toilet2": (748, 890, 221, 453), "Balcony1": (0, 135, 330, 555),
               "Balcony2": (910, 1213, 430, 558)}
SHOTS = [  # (name, eye plan xyz, target plan xyz)
    ("ue_spawn_view", (1525, 40, 165), (1300, 260, 130)), ("ue_living", (880, 55, 160), (1589, 210, 120)),
    ("ue_dining", (1540, 90, 160), (930, 360, 120)), ("ue_kitchen", (1505, 398, 160), (1250, 545, 110)),
    ("ue_foyer", (560, 100, 160), (1500, 60, 120)), ("ue_bed1", (322, 300, 160), (110, 20, 95)),
    ("ue_bed2", (425, 262, 160), (732, 460, 100)), ("ue_toilet1", (175, 412, 150), (330, 552, 100)),
    ("ue_vanity", (840, 20, 150), (819, 205, 120)), ("ue_balcony2", (1060, 300, 160), (1060, 572, 110)),
]


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def tune_character():
    bp = unreal.load_asset("/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter")
    cdo = unreal.get_default_object(bp.generated_class())
    cm = cdo.get_editor_property("character_movement")
    cm.set_editor_property("max_walk_speed", 300.0)
    cm.set_editor_property("max_step_height", 30.0)
    cm.set_editor_property("jump_z_velocity", 350.0)
    cap = cdo.get_editor_property("capsule_component")
    cap.set_capsule_size(CAP_R, CAP_HH)
    hidden = []
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h)
        o = unreal.SubobjectDataBlueprintFunctionLibrary.get_associated_object(d)
        if o and o.get_name().startswith("FirstPersonMesh"):
            o.set_editor_property("hidden_in_game", True)
            o.set_editor_property("visible", False)
            hidden.append(o.get_name())
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    R["character"] = dict(walk=cm.get_editor_property("max_walk_speed"), radius=cap.get_unscaled_capsule_radius(),
                          half_height=cap.get_unscaled_capsule_half_height(), hidden=hidden)


def sweep(a, b):
    z = CAP_HH + 3
    hit = unreal.SystemLibrary.capsule_trace_single(world(), ue(a[0], a[1], z), ue(b[0], b[1], z), CAP_R, CAP_HH - 2,
                                                    unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [],
                                                    unreal.DrawDebugTrace.NONE, True)
    t = hit.to_tuple() if hit else (False,)
    if not t[0]:
        return None
    actor = t[9] if len(t) > 9 else None
    return {"by": actor.get_actor_label() if actor else None, "at": [round(t[4].x), round(-t[4].y)]}


def check_routes():
    for room, pts in ROUTES.items():
        blocks = []
        for a, b in zip(pts[:-1], pts[1:]):
            h = sweep(a, b)
            if h:
                blocks.append({"segment": [a, b], **h})
        R["routes"][room] = {"clear": not blocks, "blocks": blocks}


def floor_check():
    for room, (x0, x1, y0, y1) in FLOOR_RECTS.items():
        holes, n = [], 0
        x = x0
        while x <= x1:
            y = y0
            while y <= y1:
                h = unreal.SystemLibrary.line_trace_single(world(), ue(x, y, 120), ue(x, y, -50), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                           True, [], unreal.DrawDebugTrace.NONE, True)
                t = h.to_tuple() if h else (False,)
                n += 1
                if not t[0]:
                    holes.append((x, y))
                y += 25
            x += 25
        R["floor"][room] = {"samples": n, "no_hit": len(holes), "examples": holes[:5]}


def nav_paths():
    nav = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
           if a.get_class().get_name() == "RecastNavMesh"]
    R["navmesh_actors"] = len(nav)
    for room, pts in ROUTES.items():
        x, y = pts[-1]
        p = unreal.NavigationSystemV1.find_path_to_location_synchronously(world(), ue(SPAWN[0], SPAWN[1], 90), ue(x, y, 90))
        pp = p.get_editor_property("path_points") if p else []
        R["paths"][room] = {"ok": bool(p is not None and len(pp) > 1 and not p.is_partial()), "points": len(pp),
                            "length_m": round(p.get_path_length() / 100, 1) if p else None}


def look_rot(eye, tgt):
    return unreal.MathLibrary.make_rot_from_x(unreal.Vector(tgt[0] - eye[0], -(tgt[1] - eye[1]), tgt[2] - eye[2]))


S = {"phase": "warmup", "t": 0, "shots": list(SHOTS)}


def tick(dt):
    s = S
    s["t"] += 1
    try:
        if s["phase"] == "warmup" and s["t"] > 600:          # shaders / streaming settle
            unreal.SystemLibrary.execute_console_command(world(), "RebuildNavigation")
            check_routes()
            floor_check()
            s["phase"], s["t"] = "nav_wait", 0
        elif s["phase"] == "nav_wait" and s["t"] > 400:
            nav_paths()
            s["phase"], s["t"] = "shots", 0
        elif s["phase"] == "shots":
            if s["t"] % 120 == 1:
                if not s["shots"]:
                    s["phase"], s["t"] = "finish", 0
                    return
                name, eye, tgt = s["shots"].pop(0)
                ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
                ues.set_level_viewport_camera_info(ue(*eye), look_rot(eye, tgt))
                s["pending"] = name
            elif s["t"] % 120 == 90 and s.get("pending"):
                unreal.SystemLibrary.execute_console_command(world(), "HighResShot 1600x900")
                R["shots"].append(s.pop("pending"))
        elif s["phase"] == "finish" and s["t"] > 150:
            json.dump(R, open(os.path.join(OUT, "verify_report.json"), "w"), indent=1)
            unreal.log_warning("FLATVERIFY done")
            s["phase"] = "done"
            unreal.unregister_slate_post_tick_callback(HANDLE)
            if os.environ.get("FLAT_QUIT") == "1":
                unreal.SystemLibrary.quit_editor()
    except Exception as e:
        R["notes"].append("phase %s error: %s" % (s["phase"], e))
        unreal.log_error("FLATVERIFY error %s" % e)
        s["phase"], s["t"] = "finish", 0


unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(MAP)
try:
    tune_character()
except Exception as e:
    R["notes"].append("character tuning failed: %s" % e)
HANDLE = unreal.register_slate_post_tick_callback(tick)
