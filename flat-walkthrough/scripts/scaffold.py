#!/usr/bin/env python3
"""Creates a new flat-walkthrough project from the kit (the pipeline that produced the Type G 2BHK walkthrough).

python3 scaffold.py <dest dir> --name FlatLotus3B --title "Lotus 3BHK" [--package com.flatwalkthrough.lotus3b]
                    [--plan path/to/plan.jpg ...] [--no-keystore] [--dry-run]

--name     Unreal project / app name: letters and digits only, starts with a letter (becomes <name>.app, <name>.apk)
--title    human title used in window titles, app labels and docs ("Lotus 3BHK" -> "Lotus 3BHK Flat")
--package  Android application id (default com.flatwalkthrough.<lower name without 'flat'>)

Result:
  <dest>/blender/scripts        kit scripts (renamed identifiers). layout.py / furnish.py etc. still hold Type G
                                data: they are templates to rewrite for the new plan (see FLAT_SPECIFIC.md)
  <dest>/blender/assets|textures Poly Haven CC0 library (APFS clones, no extra disk space)
  <dest>/unreal/<name>/          UE 5.8 content-only project: First Person template content, kit Config,
                                Content/Python/init_unreal.py hook (FLAT_RUN automation)
  <dest>/unreal/scripts         kit Unreal scripts, variants.json
  <dest>/reference/             the plan images given with --plan
  <dest>/project.json           intake answers (fill in during intake), <dest>/site.json (environment)
  <dest>/FLAT_SPECIFIC.md       checklist of the files that carry per-flat data
Secrets: a fresh Android keystore + random password are generated into unreal/<name>/Build/Android and
DefaultEngine.ini (never print the password back to the user in chat).
"""
import argparse, json, os, re, secrets, shutil, subprocess, sys, uuid

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(SKILL, "kit")
BASE = os.path.join(SKILL, "base")
TEXT_EXT = {".py", ".sh", ".ini", ".json", ".md", ".txt", ".uproject"}

FLAT_SPECIFIC = """# Per-flat files to rewrite (they start as the Type G 2BHK versions)

| File | What is flat-specific |
|---|---|
| blender/scripts/layout.py | every room, wall, opening, door, window, duct, balcony (cm, plan frame) |
| blender/scripts/build_flat.py | room-specific builders (false ceiling bands, toilets, kitchen shell), markers (PlayerStart) |
| blender/scripts/furnish.py | furniture placement per room, builder style, `flat_cat` category on every object |
| blender/scripts/compare_plan.py, annotate_plan.py | plan pixel registration (KX, OX, KY, OY), room labels |
| blender/scripts/render_previews.py, make_review_page.py | camera views per room |
| blender/scripts/env_render.py, env_floorplate.py | balcony/window eye points, tower plan registration |
| site.json | pin lat/lon, storey height, bearings, plan registration (flat-environment skill) |
| blender/env_data/towers.json | known tall buildings around the site (researched per site) |
| unreal/scripts/ue_verify.py | walking routes and room rectangles for the capsule sweeps |
| unreal/scripts/ue_mobile.py | ROOMS (reflection captures) and ROOM_EV (per-room exposure) |
| unreal/scripts/ue_env_shots.py | balcony screenshot cameras |
| unreal/scripts/variants.json | remove lists for SemiFurnished / Unfurnished (confirm the builder's hand-over list) |
"""


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def clone_tree(src, dst):
    """APFS clone (cp -c) when possible, so the 250 MB library costs no space; plain copy otherwise."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        run(["cp", "-cR", src, dst], stderr=subprocess.DEVNULL)
    except Exception:
        shutil.copytree(src, dst, dirs_exist_ok=True)


def renamer(a):
    lower = a.name.lower()
    pairs = [
        ("com.flatwalkthrough.typeg", a.package),
        ("FlatTypeGBuild", a.name + "Build"),
        ("FlatTypeG", a.name),
        ("flattypeg", lower),
        ("flat_typeG", "flat_" + a.slug),
        ("Type G Flat Walkthrough", a.title + " Flat Walkthrough"),
        ("Type G Flat", a.title + " Flat"),
        ("Type G 2BHK", a.title),
        ("Type G", a.title),
    ]

    def f(text):
        for o, n in pairs:
            text = text.replace(o, n)
        return text
    return f


def rewrite_tree(root, fn):
    for d, _, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            if os.path.splitext(f)[1] in TEXT_EXT:
                s = open(p, encoding="utf-8").read()
                t = fn(s)
                if t != s:
                    open(p, "w", encoding="utf-8").write(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--name", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--package")
    ap.add_argument("--plan", action="append", default=[])
    ap.add_argument("--no-keystore", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{2,30}", a.name):
        sys.exit("--name: letters/digits only, 3-31 chars, starting with a letter")
    a.slug = re.sub(r"^flat", "", a.name, flags=re.I).lower() or a.name.lower()
    a.package = a.package or "com.flatwalkthrough." + a.slug
    dest = os.path.abspath(a.dest)
    proj = os.path.join(dest, "unreal", a.name)
    plan = [
        ("kit/blender/scripts", "blender/scripts"),
        ("kit/unreal/scripts", "unreal/scripts"),
        ("kit/unreal/Config", "unreal/%s/Config" % a.name),
        ("kit/unreal/Python", "unreal/%s/Content/Python" % a.name),
        ("base/ue_content/*", "unreal/%s/Content/" % a.name),
        ("base/polyhaven/assets", "blender/assets"),
        ("base/polyhaven/textures", "blender/textures"),
    ]
    print("project %s  title %r  package %s  slug %s\n-> %s" % (a.name, a.title, a.package, a.slug, dest))
    for s, d in plan:
        print("  %-28s -> %s" % (s, d))
    if a.dry_run:
        return
    if os.path.exists(proj):
        sys.exit("refusing to overwrite existing project: " + proj)
    for d in ("blender", "unreal", "reference", "docs", "previews", "build"):
        os.makedirs(os.path.join(dest, d), exist_ok=True)
    shutil.copytree(os.path.join(KIT, "blender/scripts"), os.path.join(dest, "blender/scripts"), dirs_exist_ok=True)
    shutil.copytree(os.path.join(KIT, "unreal/scripts"), os.path.join(dest, "unreal/scripts"), dirs_exist_ok=True)
    shutil.copytree(os.path.join(KIT, "unreal/Config"), os.path.join(proj, "Config"))
    os.makedirs(os.path.join(proj, "Content"), exist_ok=True)
    shutil.copytree(os.path.join(KIT, "unreal/Python"), os.path.join(proj, "Content/Python"))
    for sub in sorted(os.listdir(os.path.join(BASE, "ue_content"))):
        clone_tree(os.path.join(BASE, "ue_content", sub), os.path.join(proj, "Content", sub))
    clone_tree(os.path.join(BASE, "polyhaven/assets"), os.path.join(dest, "blender/assets"))
    clone_tree(os.path.join(BASE, "polyhaven/textures"), os.path.join(dest, "blender/textures"))
    for p in a.plan:
        shutil.copy2(p, os.path.join(dest, "reference", os.path.basename(p)))

    fn = renamer(a)
    rewrite_tree(os.path.join(dest, "blender/scripts"), fn)
    rewrite_tree(os.path.join(dest, "unreal/scripts"), fn)
    rewrite_tree(os.path.join(proj, "Config"), fn)

    # project file + config placeholders
    json.dump({"FileVersion": 3, "EngineAssociation": "5.8", "Category": "",
               "Description": "%s flat - first-person walkthrough" % a.title,
               "Plugins": [{"Name": "ModelingToolsEditorMode", "Enabled": True, "TargetAllowList": ["Editor"]},
                           {"Name": "GameplayStateTree", "Enabled": True},
                           {"Name": "PythonScriptPlugin", "Enabled": True},
                           {"Name": "EditorScriptingUtilities", "Enabled": True}]},
              open(os.path.join(proj, a.name + ".uproject"), "w"), indent="\t")
    sdk = os.path.expanduser("~/Library/Android/sdk")
    ndks = sorted(os.listdir(os.path.join(sdk, "ndk"))) if os.path.isdir(os.path.join(sdk, "ndk")) else []
    pw = secrets.token_hex(12)
    subs = {"__PROJECT_ID__": uuid.uuid4().hex.upper(), "__KEYSTORE_PASSWORD__": pw, "__ANDROID_SDK__": sdk,
            "__ANDROID_NDK__": os.path.join(sdk, "ndk", ndks[-1]) if ndks else ""}
    for f in ("DefaultEngine.ini", "DefaultGame.ini"):
        p = os.path.join(proj, "Config", f)
        s = open(p).read()
        for k, v in subs.items():
            s = s.replace(k, v)
        open(p, "w").write(s)
    if not a.no_keystore:
        ks_dir = os.path.join(proj, "Build", "Android")
        os.makedirs(ks_dir, exist_ok=True)
        cands = ["/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/keytool", shutil.which("keytool")]
        ok = False
        for keytool in [c for c in cands if c and os.path.exists(c)]:
            r = subprocess.run([keytool, "-genkeypair", "-keystore", os.path.join(ks_dir, a.name.lower() + ".keystore"),
                                "-alias", a.name.lower(), "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
                                "-storepass", pw, "-keypass", pw, "-dname", "CN=%s Flat Walkthrough" % a.title],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                ok = True
                break
        print("android keystore created (password stored in Config/DefaultEngine.ini)" if ok else
              "WARNING: no working keytool (install Android Studio); create the keystore before packaging Android")

    json.dump({"name": a.name, "title": a.title, "package": a.package,
               "plans": [os.path.basename(p) for p in a.plan],
               "intake": {"flat_type": "", "floor": None, "storey_height_m": None, "north_or_facing": "",
                          "builder": "", "style_references": [], "variants": ["Furnished"],
                          "environment": False, "lat": None, "lon": None, "targets": ["mac"],
                          "android_devices": [], "unknowns_assumed": []}},
              open(os.path.join(dest, "project.json"), "w"), indent=2)
    json.dump({"lat": None, "lon": None, "env_build": {}}, open(os.path.join(dest, "site.json"), "w"), indent=2)
    open(os.path.join(dest, "FLAT_SPECIFIC.md"), "w").write(FLAT_SPECIFIC)
    print("SCAFFOLD OK", dest)


if __name__ == "__main__":
    main()
