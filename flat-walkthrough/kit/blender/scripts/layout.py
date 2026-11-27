"""Type G 2BHK - architectural layout data (all values in centimetres).

Coordinate system (matches the orientation of plan_my_flat.jpg):
  origin = inner face of the left exterior wall (x=0) and inner face of the
           bottom party/corridor wall (y=0), finished floor level z=0
  +X     = towards the living room / entrance (right on the plan)
  +Y     = towards the bedroom windows and balconies (up on the plan)
Plan compass: +Y faces roughly South-East, +X roughly South-West.

Tags used in comments:
  [C] confirmed by a printed dimension on both plans
  [M] measured from the drawings (pixel scale ~1.205 cm/px), not printed
  [E] estimate / standard practice, not shown on either plan
"""

H_SLAB = 285        # [E] clear height to slab soffit (Kerala apartments ~2.85-3.0 m)
DOOR_H = 210        # [E] standard door head height
EXT_T = 20          # [E] exterior / party wall (8" block + plaster)
INT_T = 12          # [M] internal partition (4" block + plaster; ~10-12 cm on drawing)

# ---------------------------------------------------------------- zones
# (name, kind, x0, x1, y0, y1)  - first match wins in zone_at()
ZONES = [
    ("Toilet1",   "wet",     150, 390, 402, 552),   # [C] 240x150
    ("Toilet2",   "wet",     744, 894, 217, 457),   # [C] 150x240
    ("Vanity",    "vanity",  744, 894, 150, 205),   # [M] wash-basin alcove off the foyer
    ("VentNiche", "service", 744, 824, 469, 572),   # [M] open ventilation cut-out ("Window & Exhaust")
    ("Shaft2",    "service", 836, 894, 469, 552),   # [M] "unusable area"
    ("ShaftK",    "service", 1519, 1589, 312, 380), # [M] kitchen "unusable area"
    ("ShaftT1",   "service", 275, 400, 572, 640),   # [M] external duct outside Toilet1
    ("Balcony1",  "balcony", -20, 138, 325, 572),   # [C~] 150x233 printed; drawn ~150x245 to railing line
    ("Balcony2",  "balcony", 906, 1217, 425, 572),  # [C~] 300x150 printed; 311x147 to railing line
    ("Kitchen",   "kitchen", 1229, 1589, 312, 552), # [C] 360x240
    ("Bed1",      "room",    0, 390, 0, 390),       # [C] 390x390
    ("Bed1Entry", "room",    402, 534, 0, 150),     # [M] entry pocket of Bed1 under Bed2's wardrobe wall
    ("Bed1Strip", "room",    390, 402, 0, 150),
    ("Bed2",      "room",    402, 732, 162, 552),   # [C] 330x390
    ("Foyer",     "room",    546, 906, 0, 150),     # [C] 150 wide
    ("Dining",    "room",    906, 1217, 0, 413),    # [C] 300x413
    ("Living",    "room",    1206, 1589, 0, 300),   # [C] 383x300
    ("Passage",   "passage", 1095, 1800, -230, -20),# [E] common corridor outside the entrance (context only)
]


def zone_at(x, y):
    for name, kind, x0, x1, y0, y1 in ZONES:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return name, kind
    return "Exterior", "exterior"


# ---------------------------------------------------------------- walls
# (name, x0, x1, y0, y1, openings, height)
# opening = (a0, a1, sill, head, kind) measured along the wall's long axis
W = []
def wall(name, x0, x1, y0, y1, openings=(), h=H_SLAB):
    W.append((name, x0, x1, y0, y1, list(openings), h))

# exterior / party walls
wall("EXT_Bottom", -20, 1609, -20, 0, [(1469, 1574, 0, DOOR_H, "door_main")])            # [M] entrance 105 cm clear
wall("EXT_Left", -20, 0, -20, 341, [(80, 280, 90, 210, "window")])                         # [M] Bed1 window ~200 wide
wall("EXT_LeftCorner", -20, 10, 500, 572)                                                  # [M] balcony corner column
wall("EXT_Top_A", 138, 744, 552, 572, [(205, 265, 150, 210, "vent"), (427, 667, 90, 210, "window")])  # [M] T1 vent, Bed2 window
wall("EXT_Top_B", 824, 906, 552, 572)                                                      # [M] shaft enclosure
wall("EXT_Top_C", 1217, 1609, 552, 572)                                                    # kitchen
wall("EXT_Right", 1589, 1609, -20, 552, [(105, 295, 75, 210, "window"), (395, 505, 105, 210, "window")])  # [M] living + kitchen windows
# internal partitions
wall("INT_Bed1Bed2", 390, 402, 150, 552)
wall("INT_Bed2Bottom", 402, 732, 150, 162, [(642, 732, 0, DOOR_H, "door")])               # [M] Bed2 door 90
wall("INT_Bed1Door", 534, 546, 0, 150, [(60, 150, 0, DOOR_H, "door")])                     # [M] Bed1 door 90
wall("INT_T1Bottom", 138, 390, 390, 402, [(150, 225, 0, DOOR_H, "door")])                  # [M] Toilet1 door 75
wall("INT_Bal1Part", 138, 150, 313, 552)
wall("INT_Bal1Glass", 0, 138, 313, 325, [(0, 138, 0, DOOR_H, "slider")])                   # [C] glazed slider (plan: "Glass")
wall("INT_T2West", 732, 744, 150, 552, [(222, 297, 0, DOOR_H, "door")])                    # [M] Toilet2 door 75
wall("INT_T2East", 894, 906, 150, 552)
wall("INT_T2Bottom", 744, 894, 205, 217)
wall("INT_T2Top", 744, 894, 457, 469, [(754, 814, 150, 210, "vent")])                      # [M] "Window & Exhaust"
wall("INT_NicheShaft", 824, 836, 469, 552)
wall("INT_Bal2Glass", 906, 1217, 413, 425, [(906, 1217, 0, DOOR_H, "slider")])             # [C] "Glass"
wall("INT_KitWest", 1217, 1229, 312, 552, [(312, 405, 0, DOOR_H, "arch")])                 # [M] kitchen opening ~93
wall("INT_KitLiving", 1217, 1589, 300, 312)
wall("INT_ShaftK_W", 1509, 1519, 312, 390)
wall("INT_ShaftK_N", 1519, 1589, 380, 390)
# context: corridor outside the entrance [E]
wall("CTX_PassageS", 1095, 1800, -250, -230)
wall("CTX_PassageW", 1075, 1095, -250, -20)
wall("CTX_PassageE", 1800, 1820, -250, -20)

# Door definitions (hinge on the wall centre-line at the jamb):
# (name, hinge_x, hinge_y, closed_dir(dx,dy), swing_normal(nx,ny), clear_width, open_deg)
DOORS = [
    ("DOOR_Main",   1574, -10,   (-1, 0), (0, 1),  105, 92),
    ("DOOR_Bed1",   540, 150,  (0, -1), (-1, 0), 90, 88),
    ("DOOR_Bed2",   732, 156,  (-1, 0), (0, 1),  90, 90),   # fully open against the T2 wall; leaf has no collision in UE
    ("DOOR_Toilet1", 150, 396, (1, 0),  (0, 1),  75, 90),
    ("DOOR_Toilet2", 738, 222, (0, 1),  (1, 0),  75, 90),   # hinged on the lower jamb so the open leaf rests on the wall
]

# Player spawn just inside the entrance, facing into the living room
SPAWN = (1520, 60, 0, 90.0)   # x, y, z(floor), yaw degrees (+Y)
