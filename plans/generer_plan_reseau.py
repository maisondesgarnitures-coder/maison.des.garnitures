"""Génère le plan schématique du réseau d'eau (SVG) à partir du croquis à main levée."""
from pathlib import Path

OUT = Path(__file__).with_name("plan-reseau-eau.svg")

C = {
    "sonede": "#1f4fa8", "froide": "#2f74d0", "chaude": "#d6402b",
    "jardin": "#2e9b5f", "piscine": "#14a3b8", "retour": "#e3609e", "arrosage": "#2f74d0",
    "mur": "#2b3440", "fill": "#f4f1ea", "pool": "#d9f1f6", "txt": "#1d2530",
}
svg = []


def rounded(pts, r=18):
    """Chemin orthogonal aux angles arrondis."""
    d = f"M{pts[0][0]},{pts[0][1]}"
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        l1 = max(abs(x1 - x0), abs(y1 - y0)); l2 = max(abs(x2 - x1), abs(y2 - y1))
        rr = min(r, l1 / 2, l2 / 2)
        ax = x1 - (x1 - x0) / l1 * rr; ay = y1 - (y1 - y0) / l1 * rr
        bx = x1 + (x2 - x1) / l2 * rr; by = y1 + (y2 - y1) / l2 * rr
        d += f" L{ax:.1f},{ay:.1f} Q{x1},{y1} {bx:.1f},{by:.1f}"
    d += f" L{pts[-1][0]},{pts[-1][1]}"
    return d


def pipe(pts, color, w=4, dash=None, r=18):
    d = rounded(pts, r) if isinstance(pts, list) else pts
    svg.append(f'<path d="{d}" fill="none" stroke="#fff" stroke-width="{w + 4}" stroke-linejoin="round" stroke-linecap="round"/>')
    da = f' stroke-dasharray="{dash}"' if dash else ""
    svg.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"{da}/>')


def arrow(x, y, direction, color, s=9):
    pts = {"r": [(s, 0), (-s, -s * .8), (-s, s * .8)], "l": [(-s, 0), (s, -s * .8), (s, s * .8)],
           "u": [(0, -s), (-s * .8, s), (s * .8, s)], "d": [(0, s), (-s * .8, -s), (s * .8, -s)]}[direction]
    p = " ".join(f"{x + a:.1f},{y + b:.1f}" for a, b in pts)
    svg.append(f'<polygon points="{p}" fill="{color}" stroke="#fff" stroke-width="1.5"/>')


def text(x, y, s, size=16, weight=500, color=None, anchor="middle", italic=False, extra=""):
    st = ' font-style="italic"' if italic else ""
    svg.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color or C["txt"]}" text-anchor="{anchor}"{st} {extra}>{s}</text>')


def building(x, y, w, h, name, sub=None, fill=None, num=None):
    svg.append(f'<rect x="{x+4}" y="{y+5}" width="{w}" height="{h}" rx="6" fill="#000" opacity=".06"/>')
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill or C["fill"]}" stroke="{C["mur"]}" stroke-width="3"/>')
    cx, cy = x + w / 2, y + h / 2
    if num:
        svg.append(f'<circle cx="{cx}" cy="{cy + 22}" r="20" fill="#fff" stroke="{C["mur"]}" stroke-width="2"/>')
        text(cx, cy + 29, num, 20, 700)
        text(cx, cy - 8, name, 24, 700)
    else:
        text(cx, cy + (0 if sub else 8), name, 22, 700)
        if sub:
            text(cx, cy + 24, sub, 15, 500, "#5b6672")


def vanne(x, y, label=None, side="r"):
    svg.append(f'<g><circle cx="{x}" cy="{y}" r="14" fill="#fff" stroke="{C["mur"]}" stroke-width="2.5"/>'
               f'<path d="M{x-10},{y-10} L{x+10},{y+10} M{x+10},{y-10} L{x-10},{y+10}" stroke="{C["mur"]}" stroke-width="2"/>'
               f'<circle cx="{x}" cy="{y}" r="4" fill="{C["mur"]}"/></g>')
    if label:
        dx = 22 if side == "r" else -22
        anc = "start" if side == "r" else "end"
        text(x + dx, y - 2, "5 conduites", 13, 600, anchor=anc)
        text(x + dx, y + 14, "principales", 13, 600, anchor=anc)


def douche(x, y, label=True):
    svg.append(f'<rect x="{x-18}" y="{y-18}" width="36" height="36" rx="6" fill="#fff" stroke="{C["mur"]}" stroke-width="2.5"/>'
               f'<circle cx="{x}" cy="{y}" r="7" fill="none" stroke="{C["mur"]}" stroke-width="2"/>')
    for dx, dy in [(-11, -11), (0, -13), (11, -11), (-13, 0), (13, 0), (-11, 11), (0, 13), (11, 11)]:
        svg.append(f'<circle cx="{x+dx*.85}" cy="{y+dy*.85}" r="1.6" fill="{C["froide"]}"/>')
    if label:
        text(x, y - 26, "Douche", 14, 700)


# ---------------------------------------------------------------- terrain
W, H = 1960, 1340
svg.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
svg.append('<defs><pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">'
           '<path d="M20 0H0V20" fill="none" stroke="#e9edf2" stroke-width="1"/></pattern>'
           '<pattern id="water" width="16" height="16" patternUnits="userSpaceOnUse">'
           '<path d="M0 10 Q4 6 8 10 T16 10" fill="none" stroke="#9fd8e3" stroke-width="1.5"/></pattern></defs>')
svg.append('<g transform="translate(40,40)">')
svg.append('<rect x="0" y="0" width="1560" height="1260" fill="url(#grid)" stroke="#9aa5b1" stroke-width="2" stroke-dasharray="10 6" rx="4"/>')
text(14, 1248, "Limite de propriété", 13, 500, "#7b8794", anchor="start", italic=True)

# bâtiments
building(560, 70, 340, 110, "Piscine", fill=C["pool"])
svg.append('<rect x="572" y="82" width="316" height="86" rx="4" fill="url(#water)"/>')
building(540, 240, 420, 250, "Maison", num="2")
building(1060, 235, 210, 275, "Maison", num="1")
svg.append(f'<rect x="960" y="275" width="100" height="70" fill="#ebe7de" stroke="{C["mur"]}" stroke-width="2" stroke-dasharray="6 4"/>')
text(1010, 315, "Liaison", 13, 600, "#5b6672")
building(160, 750, 300, 210, "Garage")
building(460, 750, 480, 210, "Maison", num="3")
building(300, 1110, 420, 100, "Piscine", fill=C["pool"])
svg.append('<rect x="312" y="1122" width="396" height="76" rx="4" fill="url(#water)"/>')
building(960, 1080, 340, 160, "Local", "chaudière", fill="#fbeee3")
building(1300, 1080, 140, 160, "Studio")

# ---------------------------------------------------------------- réseaux
# Tous les départs sortent du même point : le collecteur en haut du local chaudière.
T = 1080  # face supérieure du local chaudière

# --- départs vers l'ouest (de gauche à droite sur le collecteur)
# Douche piscine 2 : EC / EF
pipe([(970, T), (970, 1052), (812, 1052), (812, 1152)], C["chaude"], 4, r=12)
pipe([(980, T), (980, 1040), (792, 1040), (792, 1152)], C["froide"], 4, r=12)
douche(802, 1170, False)
text(802, 1210, "Douche", 13, 700)
text(900, 1175, "EF + EC douche", 12, 600, "#5b6672")
# Eau piscine 2
pipe([(990, T), (990, 1028), (520, 1028), (520, 1110)], C["piscine"], 5, "12 7", r=12)
arrow(660, 1028, "l", C["piscine"]); text(400, 1060, "Eau piscine", 14, 600, C["piscine"])
# Arrivée SONEDE (3 lignes)
for i in range(3):
    x = 58 + 12 * i; y = 1016 - 12 * i; xc = 1000 + 10 * i
    pipe([(x, -8), (x, y), (xc, y), (xc, T)], C["sonede"], 4, r=14)
arrow(70, 300, "d", C["sonede"], 11); arrow(70, 800, "d", C["sonede"], 11); arrow(600, 1004, "r", C["sonede"], 11)
text(36, 520, "Arrivée SONEDE · 3 lignes", 16, 700, C["sonede"], extra='transform="rotate(-90 36 520)"')
svg.append(f'<rect x="42" y="-36" width="56" height="28" rx="4" fill="#fff" stroke="{C["sonede"]}" stroke-width="2.5"/>')
text(70, -16, "C", 15, 800, C["sonede"])
text(106, -15, "Compteur SONEDE — 3 lignes", 14, 600, C["sonede"], anchor="start")
# Conduite jardin (boucle verte) : départ ouest, retour est
pipe([(1030, T), (1030, 980), (120, 980), (120, 30), (1490, 30), (1490, 1056), (1295, 1056), (1295, T)], C["jardin"], 4, r=16)
arrow(120, 560, "u", C["jardin"]); arrow(800, 30, "r", C["jardin"]); arrow(1490, 560, "d", C["jardin"])
text(150, 470, "Conduite jardin · poly 25", 15, 600, C["jardin"], anchor="start", extra='transform="rotate(-90 150 470)"')
text(1520, 640, "Conduite jardin · poly 25", 15, 600, C["jardin"], anchor="start", extra='transform="rotate(-90 1520 640)"')

# --- faisceaux de 5 conduites principales
ORDER = [(C["froide"], None), (C["chaude"], "8 5"), (C["chaude"], "8 5"), (C["chaude"], None), (C["retour"], None)]
for i, (col, da) in enumerate(ORDER):  # -> Maison 3
    x = 1045 + 10 * i; y = 920 - 10 * i
    pipe([(x, T), (x, y), (940, y)], col, 4, da, r=12)
# Arrosage gauche (réseau courbe avec robinets)
d_arr = f"M1100,{T} L1100,760 Q1100,715 1055,715 L430,715 C285,715 270,640 270,500 L270,140"
pipe(d_arr, C["arrosage"], 3)
for (x, y) in [(270, 140), (270, 330), (300, 640), (620, 715), (860, 715)]:
    svg.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{C["arrosage"]}" stroke="#fff" stroke-width="2"/>')
text(290, 128, "Arrosage · tube poly 32", 16, 700, C["arrosage"], anchor="start")
text(560, 705, "Tube poly 32 · robinets", 13, 600, C["arrosage"], italic=True)
for i, (col, da) in enumerate(ORDER):  # -> Maison 2
    x = 1115 + 10 * i; y = 680 - 10 * i; xt = 700 + 10 * i
    pipe([(x, T), (x, y), (xt, y), (xt, 490)], col, 4, da, r=14)
for i, (col, da) in enumerate(ORDER):  # -> Maison 1
    x = 1170 + 10 * i
    pipe([(x, T), (x, 510)], col, 4, da)

# --- départs vers l'est
# Eau piscine 1 & 3 (nord)
pipe([(1265, T), (1265, 1004), (1395, 1004), (1395, 50), (730, 50), (730, 70)], C["piscine"], 5, "12 7", r=14)
arrow(1395, 560, "u", C["piscine"]); arrow(1000, 50, "l", C["piscine"])
text(1420, 420, "Eau piscine", 14, 600, C["piscine"], extra='transform="rotate(-90 1420 420)"')
# Puits -> local chaudière
pipe([(1430, 916), (1430, 1016), (1275, 1016), (1275, T)], C["jardin"], 5, r=14)
arrow(1330, 1016, "l", C["jardin"], 8)
svg.append(f'<circle cx="1430" cy="890" r="26" fill="#fff" stroke="{C["mur"]}" stroke-width="3"/>'
           f'<circle cx="1430" cy="890" r="19" fill="#dbeee3" stroke="{C["jardin"]}" stroke-width="2"/>')
text(1430, 895, "Puits", 12, 700)
# Arrosage droit
pipe([(1285, T), (1285, 1040), (1472, 1040), (1472, 170)], C["arrosage"], 3, r=14)
for yy in [170, 330, 500, 680]:
    svg.append(f'<circle cx="1472" cy="{yy}" r="7" fill="{C["arrosage"]}" stroke="#fff" stroke-width="2"/>')
arrow(1472, 790, "u", C["arrosage"], 8)
text(1462, 600, "Arrosage · tube poly 32", 15, 700, C["arrosage"], extra='transform="rotate(-90 1462 600)"')

# Collecteur : point de départ unique
svg.append(f'<rect x="962" y="{T-6}" width="340" height="12" rx="6" fill="{C["mur"]}"/>')
text(1130, T + 30, "Collecteur — départ unique", 12, 700, "#7a4a1f")

# Douches des piscines du haut : depuis le collecteur, couloir à droite de la Maison 1
SH = [(1222, 860, 1280, 198, "w", C["chaude"]), (1232, 870, 1290, 184, "w", C["froide"]),
      (1242, 880, 1300, 198, "e", C["froide"]), (1252, 890, 1310, 212, "e", C["chaude"])]
for x0, yj, xc, yt, side, col in SH:
    xe = 1018 if side == "w" else 1342
    pipe([(x0, T), (x0, yj), (xc, yj), (xc, yt), (xe, yt)], col, 4, r=10)
douche(1000, 191)

# Piscine 3 à côté de la piscine du haut (devant Maison 1) + douche EF/EC
building(1100, 70, 200, 100, "Piscine", fill=C["pool"])
svg.append('<rect x="1110" y="80" width="180" height="80" rx="4" fill="url(#water)"/>')
pipe([(1200, 50), (1200, 70)], C["piscine"], 5)
svg.append(f'<circle cx="1200" cy="50" r="5" fill="{C["piscine"]}" stroke="#fff" stroke-width="1.5"/>')
douche(1360, 205, False)
text(1360, 238, "Douche", 14, 700)

vanne(900, 900, True, "l")
vanne(678, 540, True, "l")
vanne(1150, 600, True, "l")
svg.append('</g>')

# ---------------------------------------------------------------- cartouche / légende
px = 1640
svg.append(f'<rect x="{px}" y="40" width="290" height="1260" rx="8" fill="#f8fafc" stroke="#cbd2d9" stroke-width="1.5"/>')
text(px + 20, 82, "PLAN DU RÉSEAU", 22, 800, anchor="start")
text(px + 20, 108, "D'EAU ET CHAUFFAGE", 22, 800, anchor="start")
text(px + 20, 134, "Schéma de principe — non à l'échelle", 13, 500, "#5b6672", anchor="start", italic=True)
svg.append(f'<line x1="{px+20}" y1="152" x2="{px+270}" y2="152" stroke="#cbd2d9"/>')
text(px + 20, 186, "LÉGENDE", 15, 800, "#5b6672", anchor="start")

rows = [
    (C["sonede"], 4, None, "Arrivée SONEDE (3 lignes)"),
    (C["froide"], 4, None, "Eau froide"),
    (C["chaude"], 4, None, "Eau chaude sanitaire"),
    (C["chaude"], 4, "8 5", "Chauffage"),
    (C["jardin"], 4, None, "Jardin poly 25 / puits"),
    (C["piscine"], 5, "12 7", "Eau piscine"),
    (C["arrosage"], 3, None, "Arrosage — tube poly 32"),
    (C["retour"], 4, None, "Retour sanitaire"),
]
y = 220
for col, w, dash, lab in rows:
    da = f' stroke-dasharray="{dash}"' if dash else ""
    svg.append(f'<line x1="{px+20}" y1="{y}" x2="{px+80}" y2="{y}" stroke="{col}" stroke-width="{w}" stroke-linecap="round"{da}/>')
    text(px + 95, y + 5, lab, 15, 500, anchor="start")
    y += 38
# symboles
svg.append(f'<circle cx="{px+50}" cy="{y}" r="7" fill="{C["arrosage"]}" stroke="#fff" stroke-width="2"/>')
text(px + 95, y + 5, "Robinet d'arrosage", 15, 500, anchor="start"); y += 42
svg.append(f'<circle cx="{px+50}" cy="{y}" r="12" fill="#fff" stroke="{C["mur"]}" stroke-width="2.5"/>'
           f'<path d="M{px+42},{y-8} L{px+58},{y+8} M{px+58},{y-8} L{px+42},{y+8}" stroke="{C["mur"]}" stroke-width="2"/>')
text(px + 95, y - 3, "Vanne / regard", 15, 500, anchor="start")
text(px + 95, y + 15, "5 conduites principales", 13, 500, "#5b6672", anchor="start"); y += 46
svg.append('<g transform="translate(0,0)">'); douche(px + 50, y, False); svg.append('</g>')
text(px + 95, y - 3, "Douche de piscine", 15, 500, anchor="start")
text(px + 95, y + 15, "eau chaude + eau froide", 13, 500, "#5b6672", anchor="start"); y += 48
arrow(px + 50, y, "r", C["txt"], 9); text(px + 95, y + 5, "Sens d'écoulement", 15, 500, anchor="start"); y += 50

svg.append(f'<line x1="{px+20}" y1="{y}" x2="{px+270}" y2="{y}" stroke="#cbd2d9"/>'); y += 34
text(px + 20, y, "FAISCEAU PRINCIPAL", 15, 800, "#5b6672", anchor="start"); y += 28
text(px + 20, y, "Depuis le local chaudière vers", 14, 500, anchor="start"); y += 20
text(px + 20, y, "chaque maison (1, 2, 3) :", 14, 500, anchor="start"); y += 30
for col, da, lab in [(C["froide"], None, "1 × eau froide"), (C["chaude"], "8 5", "2 × chauffage"),
                     (C["chaude"], None, "1 × eau chaude sanitaire"), (C["retour"], None, "1 × retour sanitaire")]:
    dd = f' stroke-dasharray="{da}"' if da else ""
    svg.append(f'<line x1="{px+20}" y1="{y-5}" x2="{px+54}" y2="{y-5}" stroke="{col}" stroke-width="5"{dd}/>')
    text(px + 66, y, lab, 14, 500, anchor="start"); y += 28

# Nord
ny = 1010
svg.append(f'<line x1="{px+20}" y1="{ny-60}" x2="{px+270}" y2="{ny-60}" stroke="#cbd2d9"/>')
svg.append(f'<g transform="translate({px+145},{ny})"><circle r="38" fill="#fff" stroke="#9aa5b1" stroke-width="1.5"/>'
           f'<polygon points="0,-30 10,8 0,2 -10,8" fill="{C["txt"]}"/><polygon points="0,30 10,8 0,2 -10,8" fill="#cbd2d9"/></g>')
text(px + 145, ny - 46, "N", 16, 800)
text(px + 145, ny + 64, "Orientation indicative", 12, 500, "#7b8794", italic=True)
svg.append(f'<line x1="{px+20}" y1="1200" x2="{px+270}" y2="1200" stroke="#cbd2d9"/>')
text(px + 20, 1230, "Établi d'après croquis à main levée", 12, 500, "#5b6672", anchor="start")
text(px + 20, 1250, "Échelle : sans", 12, 500, "#5b6672", anchor="start")
text(px + 20, 1270, "Date : novembre 2026", 12, 500, "#5b6672", anchor="start")

out = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
       f'font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">' + "\n".join(svg) + "</svg>")
OUT.write_text(out, encoding="utf-8")
print("écrit", OUT)
