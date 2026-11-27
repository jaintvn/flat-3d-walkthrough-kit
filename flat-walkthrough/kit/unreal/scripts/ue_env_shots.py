"""Balcony / window screenshots of the Mac (Lumen) level from fixed eye positions (editor viewport + HighResShot),
so no mouse drift as in -game mode.

FLAT_RUN=<abs path>/ue_env_shots.py FLAT_QUIT=1 UnrealEditor FlatTypeG.uproject
Output: unreal/FlatTypeG/Saved/Screenshots/MacEditor/ (copied to previews/environment/unreal_<name>.png)
"""
import unreal, os, time, glob, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", "FlatTypeG"))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "previews", "environment"))
MAP = "/Game/Flat/Maps/L_FlatTypeG"
# name: (UE location cm, pitch, yaw)   (flat (x, y, z) m -> UE (x, -y, z) * 100; balconies face yaw -90)
SHOTS = [
    ("unreal_bal2_from_dining", (1055, -260, 160), -3, -90),
    ("unreal_bal2_rail", (1055, -525, 162), -10, -90),
    
    ("unreal_bal2_rail_right", (1055, -525, 162), -12, -60),
    
    ("unreal_bed1_window", (260, -195, 150), -5, 180),
]
S = {"phase": "warm", "t0": time.time(), "i": 0}
LOG = []
UES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)


def world():
    return UES.get_editor_world()


def shot_dir():
    return os.path.join(PROJ, "Saved", "Screenshots")


def tick(dt):
    try:
        t = time.time() - S["t0"]
        if S["phase"] == "warm" and t > 60:
            S["phase"], S["t0"] = "place", time.time()
        elif S["phase"] == "place":
            if S["i"] >= len(SHOTS):
                return finish()
            name, loc, pitch, yaw = SHOTS[S["i"]]
            UES.set_level_viewport_camera_info(unreal.Vector(*loc), unreal.Rotator(0, pitch, yaw))
            S["before"] = set(glob.glob(os.path.join(shot_dir(), "**", "*.png"), recursive=True))
            S["phase"], S["t0"] = "settle", time.time()
        elif S["phase"] == "settle" and t > 14:
            ok = unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, SHOTS[S["i"]][0] + ".png", None, False, False)
            LOG.append("request %s %s" % (SHOTS[S["i"]][0], ok))
            S["phase"], S["t0"] = "save", time.time()
        elif S["phase"] == "save" and t > 8:
            new = set(glob.glob(os.path.join(shot_dir(), "**", "*.png"), recursive=True)) - S["before"]
            new |= {f for f in glob.glob(os.path.join(PROJ, "**", SHOTS[S["i"]][0] + "*.png"), recursive=True) if "previews" not in f}
            name = SHOTS[S["i"]][0]
            if new:
                src = max(new, key=os.path.getmtime)
                shutil.copy(src, os.path.join(OUT, name + ".png"))
                LOG.append("shot " + name)
            else:
                LOG.append("no file for " + name)
            S["i"] += 1
            S["phase"] = "place"
    except Exception as e:
        LOG.append("error %s" % e)
        finish()


def finish():
    S["phase"] = "done"
    unreal.unregister_slate_post_tick_callback(H)
    open(os.path.join(HERE, "ue_env_shots_report.txt"), "w").write("\n".join(LOG))
    if os.environ.get("FLAT_QUIT") == "1":
        unreal.SystemLibrary.quit_editor()


os.makedirs(OUT, exist_ok=True)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
les.load_level(MAP)
try:
    les.editor_set_game_view(True)
except Exception:
    pass
unreal.SystemLibrary.execute_console_command(world(), "DisableAllScreenMessages")
H = unreal.register_slate_post_tick_callback(tick)
