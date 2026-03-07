// ═══════════════════════════════════════════════════════════════════════
// MundMaus v5.4 — Landscape Enclosure for ESP32-WROOM-32
// Mouth-controlled assistive device for tetraplegic patients
// Library: BOSL2 | Material: PETG | Printer: Bambu Lab P1S
//
// v5:   Landscape layout, components side-by-side along X.
// v5.4: USB-C adapter bay (+25mm on +X wall), snap clips removed.
//       ESP32 uses Micro-USB-to-USB-C adapter (~25x12mm).
//       Asymmetric shell extension on +X side for adapter clearance.
//
// Layout (top view, patient below):
//   +Y wall (TOP — gooseneck mount)
//   +------------------------------------------------------+-----+
//   | [Sensor]  [Joystick]  oMounto    [ESP32 -->adapter]  |USB-C|
//   +------------------------------------------------------+-----+
//   -Y wall (BOTTOM — vents, closest to patient)
//
// Usage:
//   Preview:  xvfb-run -a openscad -o preview.png --imgsize=1024,768 \
//             --camera=12,0,20,55,0,25,300 -D 'part="assembled"' mundmaus_v5_4_openscad.scad
//   Base STL: xvfb-run -a openscad -o base.stl -D 'part="base"' -D '$fs=0.4' mundmaus_v5_4_openscad.scad
//   Lid STL:  xvfb-run -a openscad -o lid.stl  -D 'part="lid"'  -D '$fs=0.4' mundmaus_v5_4_openscad.scad
// ═══════════════════════════════════════════════════════════════════════

include <BOSL2/std.scad>

$fs = $preview ? 2 : 0.4;
$fa = $preview ? 6 : 1;

/* [Part Selection] */
part = "assembled"; // [base, lid, print, assembled]

/* [Cavity Dimensions] */
cav_x = 130;       // internal length (wide axis)
cav_y = 44;        // internal width (narrow — minimizes patient view blockage)

/* [Wall Structure] */
wall    = 3.0;
floor_t = 3.0;
ceil_t  = 3.0;
corner_r = 12.0;   // organic vertical edge fillet
inner_r  = 2.5;

/* [Base/Lid Split] */
base_inner_h = 28;  // base internal depth
lid_inner_h  = 7;   // lid internal depth

/* [Lid Joint] */
lip_h   = 4.0;
lip_t   = 1.8;
lip_gap = 0.15;

/* [Tolerances — PETG] */
tol       = 0.2;
tol_loose = 0.3;

/* [ESP32-WROOM-32 DevKit 30-pin] */
esp_l = 55.0;        // PCB length (incl. antenna overhang)
esp_w = 28.0;        // PCB width with pin headers
esp_h = 1.2;         // PCB thickness
esp_standoff_h = 3.0;
esp_guide_h    = 3.0;
esp_pos_x = 35.0;    // RIGHT side, Micro-USB faces +X wall
esp_pos_y = -2.0;

/* [USB-C Adapter Bay] */
usb_bay     = 25;     // extra +X depth for Micro-USB-to-USB-C adapter (~25x12mm)
usbc_w      = 12.0;   // USB-C opening width in wall
usbc_h      = 7.0;    // USB-C opening height in wall
usbc_chamfer = 1.5;   // outer chamfer for cable strain relief
usb_pos_z   = 5.5;    // Z center of USB opening (from floor_t)

/* [KY-023 Joystick] */
joy_pcb_l      = 34;
joy_pcb_w      = 26;
joy_housing    = 16;
joy_stick_h    = 17;
joy_platform_h = 15;
joy_pin_d      = 2.8;
joy_pin_h      = 3.0;
joy_opening    = 17;
joy_pos_x = -15.0;
joy_pos_y = -4.0;

/* [Pressure Sensor MPS20N0040D-S] */
pres_l = 20;
pres_w = 15;
pres_h = 5;
pres_pos_x = -48.0;
pres_pos_y = -2.0;

/* [Tube Feedthrough] */
tube_hole_d = 6.5;
tube_pos_y  = -2.0;
tube_pos_z  = 13.0;

/* [M3 Screw Bosses] */
screw_d       = 3.4;
screw_boss_d  = 7.0;
screw_boss_h  = 10.0;
screw_pilot_d = 2.5;
screw_inset   = 6.0;

/* [3/8"-16 UNC Mic Stand Mount — +Y Wall] */
mic_clear_d   = 10.5;
mic_nut_sw    = 14.29;
mic_nut_h     = 5.56;
mic_nut_tol   = 0.2;
mic_pocket_d  = 7.9;    // pocket depth into collar
mic_collar_d  = 24.0;
mic_pos_x     = 0;

/* [Hinge — Back Edge (+Y)] */
hinge_d     = 6.0;
hinge_pin_d = 2.2;
knuckle_l   = 22.0;
knuckle_gap = 0.4;

/* [Ventilation] */
vent_n     = 6;
vent_w     = 1.6;
vent_len   = 14.0;
vent_pitch = 6.0;

// ═══════════════════════════════════════════════════════════════════════
// Derived Dimensions
// ═══════════════════════════════════════════════════════════════════════

ext_x      = cav_x + 2 * wall;        // 136 (original symmetric width)
ext_y      = cav_y + 2 * wall;        // 50
ext_z_base = floor_t + base_inner_h;   // 31
ext_z_lid  = ceil_t + lid_inner_h;     // 10
mic_pos_z  = ext_z_base / 2;

// Asymmetric shell: +X side extended by usb_bay
// Shell goes from -ext_x/2 to +ext_x/2 + usb_bay
shell_off_x    = usb_bay / 2;          // offset for centered cuboids
total_ext_x    = ext_x + usb_bay;      // 161 total external
total_cav_x    = cav_x + usb_bay;      // 155 total cavity
// +X outer wall at ext_x/2 + usb_bay = 93
// +X inner wall at cav_x/2 + usb_bay = 90
// Gap from ESP USB end (62.5) to inner wall (90) = 27.5mm

// Screw positions (4 corners of asymmetric cavity)
function screw_positions() = [
    [ cav_x/2 + usb_bay - screw_inset,  cav_y/2 - screw_inset],
    [ cav_x/2 + usb_bay - screw_inset, -cav_y/2 + screw_inset],
    [-cav_x/2 + screw_inset,            cav_y/2 - screw_inset],
    [-cav_x/2 + screw_inset,           -cav_y/2 + screw_inset]
];

// Hex nut derived
mic_nut_sw_tol = mic_nut_sw + 2 * mic_nut_tol;
mic_nut_ac_tol = mic_nut_sw_tol / cos(30);

// Hinge geometry
n_knuckles    = 5;   // B-T-B-T-B
knuckle_pitch = knuckle_l + knuckle_gap;
hinge_total_l = n_knuckles * knuckle_l + (n_knuckles - 1) * knuckle_gap;
hinge_start_x = -hinge_total_l / 2;

// Hinge center position (barrel sits on +Y wall exterior)
hinge_cy = ext_y / 2 + hinge_d / 2;
hinge_cz_base = ext_z_base;  // top of base = hinge axis

// ═══════════════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════════════

if (part == "base") {
    base();
} else if (part == "lid") {
    translate([0, 0, ext_z_lid])
        rotate([180, 0, 0])
            lid();
} else if (part == "print") {
    base();
    translate([total_ext_x + 15, 0, ext_z_lid])
        rotate([180, 0, 0])
            lid();
} else { // assembled
    color("DimGray") base();
    color("Silver", 0.5)
        translate([0, 0, ext_z_base])
            lid();
    if ($preview) ghost_components();
}

// ═══════════════════════════════════════════════════════════════════════
// BASE
// ═══════════════════════════════════════════════════════════════════════

module base() {
    difference() {
        union() {
            // Outer shell (asymmetric — extended +X for USB-C adapter bay)
            difference() {
                translate([shell_off_x, 0, 0])
                    cuboid([total_ext_x, ext_y, ext_z_base],
                           rounding = corner_r, except = TOP, anchor = BOTTOM);
                up(floor_t)
                    translate([shell_off_x, 0, 0])
                        cuboid([total_cav_x, cav_y, ext_z_base],
                               rounding = inner_r, except = [TOP, BOTTOM],
                               anchor = BOTTOM);
            }
            screw_bosses();
            esp_cradle();
            joy_platform();
            pres_ledge();
            mic_mount_collar();
            hinge_knuckles_base();
        }
        usb_cutout();
        tube_cutout();
        vent_slots_wall(-ext_y / 2, ext_z_base * 0.55);
        mic_mount_cuts();
    }
}

// ═══════════════════════════════════════════════════════════════════════
// LID
// ═══════════════════════════════════════════════════════════════════════

module lid() {
    lip_x = total_cav_x - 2 * lip_gap;
    lip_y = cav_y - 2 * lip_gap;
    lip_r = max(0.3, inner_r - lip_gap);
    lid_r = min(corner_r, ext_z_lid / 2 - 0.5);  // clamp to fit lid height

    difference() {
        union() {
            // Outer ceiling (asymmetric — matches base)
            translate([shell_off_x, 0, 0])
                cuboid([total_ext_x, ext_y, ext_z_lid],
                       rounding = lid_r, except = BOTTOM, anchor = BOTTOM);
            // Inner alignment lip (asymmetric)
            translate([shell_off_x, 0, 0])
                down(lip_h)
                    rect_tube(h = lip_h, size = [lip_x, lip_y],
                              wall = lip_t, rounding = lip_r, anchor = BOTTOM);
            // Hinge knuckles
            hinge_knuckles_lid();
        }
        // Hollow interior (asymmetric)
        translate([shell_off_x, 0, 0])
            cuboid([total_cav_x, cav_y, lid_inner_h + 0.01],
                   rounding = inner_r, except = [TOP, BOTTOM], anchor = BOTTOM);
        // Joystick opening
        translate([joy_pos_x, joy_pos_y, -lip_h - 0.01])
            cuboid([joy_opening, joy_opening, ext_z_lid + lip_h + 0.02],
                   anchor = BOTTOM);
        // Screw through-holes
        for (p = screw_positions())
            translate([p[0], p[1], -lip_h - 0.01])
                cyl(h = ext_z_lid + lip_h + 0.02, d = screw_d, anchor = BOTTOM);
        // Top vent slots (3 groups across width)
        for (side = [-1, 0, 1]) {
            xo = side * 35;
            for (i = [0:2])
                translate([xo + (i - 1) * (vent_pitch - 0.5), 0, ext_z_lid / 2])
                    cuboid([vent_w, vent_len + 2, ext_z_lid + 0.02]);
        }
    }
    // Label
    translate([shell_off_x, 14, ext_z_lid - 0.01])
        linear_extrude(0.6)
            text("MundMaus v5.4", size = 6, halign = "center",
                 valign = "center", font = "Liberation Sans:style=Bold");
}

// ═══════════════════════════════════════════════════════════════════════
// DETAIL MODULES
// ═══════════════════════════════════════════════════════════════════════

module screw_bosses() {
    for (p = screw_positions())
        translate([p[0], p[1], floor_t])
            difference() {
                cyl(h = screw_boss_h, d = screw_boss_d, anchor = BOTTOM);
                down(0.01)
                    cyl(h = screw_boss_h + 0.02, d = screw_pilot_d,
                        anchor = BOTTOM);
            }
}

module esp_cradle() {
    post_sz = 3.5;
    rail_t  = 1.5;
    guide_h = esp_standoff_h + esp_h + esp_guide_h;
    corners = [
        [esp_pos_x - esp_l/2 + post_sz/2, esp_pos_y - esp_w/2 + post_sz/2],
        [esp_pos_x - esp_l/2 + post_sz/2, esp_pos_y + esp_w/2 - post_sz/2],
        [esp_pos_x + esp_l/2 - post_sz/2, esp_pos_y - esp_w/2 + post_sz/2],
        [esp_pos_x + esp_l/2 - post_sz/2, esp_pos_y + esp_w/2 - post_sz/2]
    ];
    for (p = corners)
        translate([p[0], p[1], floor_t])
            cuboid([post_sz, post_sz, esp_standoff_h], anchor = BOTTOM);
    // Side guide rails
    for (side = [-1, 1])
        translate([esp_pos_x,
                   esp_pos_y + side * (esp_w/2 + tol_loose + rail_t/2),
                   floor_t])
            cuboid([esp_l * 0.55, rail_t, guide_h], anchor = BOTTOM);
    // End stop (non-USB side, -X end of ESP32)
    translate([esp_pos_x - esp_l/2 - tol_loose - rail_t/2,
               esp_pos_y, floor_t])
        cuboid([rail_t, esp_w * 0.55, guide_h], anchor = BOTTOM);
}

module joy_platform() {
    plat_x = joy_pcb_l + 5;
    plat_y = joy_pcb_w + 5;
    translate([joy_pos_x, joy_pos_y, floor_t])
        cuboid([plat_x, plat_y, joy_platform_h],
               rounding = 2.5, except = TOP, anchor = BOTTOM);
    // Snap-fit locating pins (4 corners)
    pin_inset_x = 2.5;
    pin_inset_y = 2.5;
    for (dx = [-1, 1], dy = [-1, 1])
        translate([joy_pos_x + dx * (joy_pcb_l/2 - pin_inset_x),
                   joy_pos_y + dy * (joy_pcb_w/2 - pin_inset_y),
                   floor_t + joy_platform_h])
            cyl(h = joy_pin_h, d1 = joy_pin_d, d2 = joy_pin_d - 0.4,
                anchor = BOTTOM);
}

module pres_ledge() {
    ledge_x = pres_l + 4;
    ledge_y = pres_w + 4;
    ledge_h = 3.0;
    ret_h   = pres_h + 1.5;
    translate([pres_pos_x, pres_pos_y, floor_t])
        cuboid([ledge_x, ledge_y, ledge_h],
               rounding = 1.5, except = TOP, anchor = BOTTOM);
    // Retention walls (3 sides, open one side for insertion)
    walls = [
        [pres_pos_x, pres_pos_y + ledge_y/2 - 0.75, ledge_x, 1.5],
        [pres_pos_x, pres_pos_y - ledge_y/2 + 0.75, ledge_x, 1.5],
        [pres_pos_x + ledge_x/2 - 0.75, pres_pos_y, 1.5, ledge_y]
    ];
    for (w = walls)
        translate([w[0], w[1], floor_t + ledge_h])
            cuboid([w[2], w[3], ret_h], anchor = BOTTOM);
}

module mic_mount_collar() {
    // Internal collar on +Y wall — cylinder extends inward from wall
    wall_inner_y = ext_y / 2 - wall;
    translate([mic_pos_x, wall_inner_y, mic_pos_z])
        rotate([90, 0, 0])
            difference() {
                cyl(h = mic_pocket_d, d = mic_collar_d, anchor = BOTTOM,
                    rounding2 = 1.0);
                // Pre-cut the pocket void (bolt + hex done in mic_mount_cuts)
            }
}

module mic_mount_cuts() {
    wall_inner_y = ext_y / 2 - wall;
    // Bolt clearance hole through +Y wall (from outside)
    translate([mic_pos_x, ext_y / 2 + 0.01, mic_pos_z])
        rotate([-90, 0, 0])
            cyl(h = wall + 0.02, d = mic_clear_d, anchor = BOTTOM);
    // Hex nut pocket inside collar (from cavity side, going into +Y wall)
    translate([mic_pos_x, wall_inner_y + 0.01, mic_pos_z])
        rotate([90, 0, 0])
            cyl(h = mic_pocket_d + 0.02, d = mic_nut_ac_tol,
                $fn = 6, anchor = BOTTOM);
}

module usb_cutout() {
    // USB-C: 12mm x 7mm on +X wall (at extended bay position)
    usb_wall_x = ext_x / 2 + usb_bay;  // outer face of +X wall
    translate([usb_wall_x, esp_pos_y, floor_t + usb_pos_z])
        cuboid([wall * 3, usbc_w, usbc_h]);
    // Outer chamfer for cable strain relief
    translate([usb_wall_x - usbc_chamfer / 2, esp_pos_y, floor_t + usb_pos_z])
        cuboid([usbc_chamfer + 0.1,
                usbc_w + usbc_chamfer * 2,
                usbc_h + usbc_chamfer * 2]);
}

module tube_cutout() {
    // Tube feedthrough on -X wall (near pressure sensor) — position unchanged
    translate([-ext_x / 2, tube_pos_y, floor_t + tube_pos_z])
        cyl(h = wall * 3, d = tube_hole_d, orient = LEFT);
    // Outer funnel chamfer
    translate([-(ext_x / 2 - 0.5), tube_pos_y, floor_t + tube_pos_z])
        cyl(h = 1.5, d1 = tube_hole_d + 3, d2 = tube_hole_d,
            orient = LEFT, anchor = BOTTOM);
}

module vent_slots_wall(wall_y, z_center) {
    for (i = [0:vent_n - 1])
        translate([(i - (vent_n - 1) / 2) * vent_pitch, wall_y, z_center])
            cuboid([vent_w, wall * 3, vent_len]);
}

// ═══════════════════════════════════════════════════════════════════════
// HINGE — Knuckle Hinge on Back Edge (+Y)
// ═══════════════════════════════════════════════════════════════════════

module hinge_barrel(length) {
    difference() {
        cyl(h = length, d = hinge_d, orient = RIGHT);
        cyl(h = length + 0.2, d = hinge_pin_d, orient = RIGHT);
    }
}

module hinge_support(length, z_dir) {
    // Bridge connecting barrel to back wall
    translate([0, -hinge_d / 4, z_dir * hinge_d / 4])
        cuboid([length, hinge_d / 2, hinge_d / 2]);
}

module hinge_knuckles_base() {
    for (i = [0, 2, 4]) {
        kx = hinge_start_x + knuckle_l / 2 + i * knuckle_pitch;
        translate([kx, hinge_cy, hinge_cz_base]) {
            hinge_barrel(knuckle_l);
            hinge_support(knuckle_l, -1);  // support below axis
        }
    }
}

module hinge_knuckles_lid() {
    // In lid local coordinates: hinge axis at z=0 (bottom of lid)
    for (i = [1, 3]) {
        kx = hinge_start_x + knuckle_l / 2 + i * knuckle_pitch;
        translate([kx, hinge_cy, 0]) {
            hinge_barrel(knuckle_l);
            hinge_support(knuckle_l, 1);   // support above axis
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// GHOST COMPONENTS (preview only)
// ═══════════════════════════════════════════════════════════════════════

module ghost_components() {
    // ESP32-WROOM-32
    %translate([esp_pos_x, esp_pos_y, floor_t + esp_standoff_h])
        cuboid([esp_l, esp_w, esp_h], anchor = BOTTOM);

    // Micro-USB-to-USB-C adapter (ghost, ~25x12x6mm)
    adapter_l = 25;
    adapter_w = 12;
    adapter_h = 6;
    %translate([esp_pos_x + esp_l / 2 + adapter_l / 2, esp_pos_y,
                floor_t + usb_pos_z])
        color("DarkGray") cuboid([adapter_l, adapter_w, adapter_h]);
    // USB-C cable plug (ghost)
    %translate([cav_x / 2 + usb_bay - 5, esp_pos_y,
                floor_t + usb_pos_z])
        color("Black") cuboid([10, 10, usbc_h]);

    // KY-023 Joystick
    %translate([joy_pos_x, joy_pos_y,
                floor_t + joy_platform_h + joy_pin_h]) {
        cuboid([joy_pcb_l, joy_pcb_w, 1.6], anchor = BOTTOM);
        up(1.6) cuboid([joy_housing, joy_housing, 10], anchor = BOTTOM);
        up(11.6) cyl(h = joy_stick_h - 12, d = 6, anchor = BOTTOM);
    }

    // Pressure sensor
    %translate([pres_pos_x, pres_pos_y, floor_t + 3])
        cuboid([pres_l, pres_w, pres_h], anchor = BOTTOM);

    // Mic mount hex nut (ghost)
    %translate([mic_pos_x, ext_y/2 - wall - mic_pocket_d + mic_nut_h/2,
                mic_pos_z])
        cyl(h = mic_nut_h, d = mic_nut_sw / cos(30), $fn = 6);
}
