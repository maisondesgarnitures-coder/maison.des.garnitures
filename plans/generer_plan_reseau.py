"""Génère le plan schématique du réseau d'eau (SVG) à partir du croquis à main levée."""
from pathlib import Path

OUT = Path(__file__).with_name("plan-reseau-eau.svg")

C = {
    "sonede": "#1f4fa8", "froide": "#2f74d0", "chaude": "#d6402b",
    "jardin": "#2e9b5f", "piscine": "#14a3b8", "arrosage": "#2f74d0",
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
building(960, 1000, 240, 200, "Local", "chaudière", fill="#fbeee3")
building(1200, 1000, 220, 200, "Studio")

# ---------------------------------------------------------------- réseaux
# Conduite jardin (boucle verte)
pipe([(960, 1020), (120, 1020), (120, 30), (1490, 30), (1490, 1235), (1150, 1235), (1150, 1200)], C["jardin"], 4)
arrow(120, 560, "u", C["jardin"]); arrow(800, 30, "r", C["jardin"]); arrow(1490, 560, "d", C["jardin"])
text(150, 470, "Conduite jardin", 15, 600, C["jardin"], anchor="start", extra='transform="rotate(-90 150 470)"')
text(1520, 640, "Conduite jardin", 15, 600, C["jardin"], anchor="start", extra='transform="rotate(-90 1520 640)"')

# Arrivée SONEDE
for i in range(3):  # 3 lignes depuis le compteur
    x = 58 + 12 * i; y = 1062 - 12 * i
    pipe([(x, -8), (x, y), (960, y)], C["sonede"], 4, r=16)
arrow(70, 300, "d", C["sonede"], 11); arrow(70, 800, "d", C["sonede"], 11); arrow(600, 1050, "r", C["sonede"], 11)
text(36, 520, "Arrivée SONEDE · 3 lignes", 16, 700, C["sonede"], extra='transform="rotate(-90 36 520)"')
svg.append(f'<rect x="42" y="-36" width="56" height="28" rx="4" fill="#fff" stroke="{C["sonede"]}" stroke-width="2.5"/>')
text(70, -16, "C", 15, 800, C["sonede"])
text(106, -15, "Compteur SONEDE — 3 lignes", 14, 600, C["sonede"], anchor="start")

# Eau piscine 2 (sud)
pipe([(960, 1085), (520, 1085), (520, 1110)], C["piscine"], 5, "12 7")
arrow(760, 1085, "l", C["piscine"]); text(760, 1076, "Eau piscine", 14, 600, C["piscine"])

# Eau piscine 1 (nord)
pipe([(1175, 1000), (1175, 960), (1395, 960), (1395, 125), (900, 125)], C["piscine"], 5, "12 7")
arrow(1395, 560, "u", C["piscine"]); arrow(1150, 125, "l", C["piscine"])
text(1150, 115, "Eau piscine", 14, 600, C["piscine"])

# Puits
pipe([(1445, 922), (1445, 978), (1190, 978), (1190, 1000)], C["jardin"], 5)
arrow(1320, 978, "l", C["jardin"])
svg.append(f'<circle cx="1445" cy="890" r="32" fill="#fff" stroke="{C["mur"]}" stroke-width="3"/>'
           f'<circle cx="1445" cy="890" r="22" fill="#dbeee3" stroke="{C["jardin"]}" stroke-width="2"/>')
text(1445, 896, "Puits", 15, 700)

# Arrosage (réseau courbe avec robinets)
d_arr = "M1035,1000 L1035,760 Q1035,715 990,715 L430,715 C285,715 270,640 270,500 L270,140"
pipe(d_arr, C["arrosage"], 3)
for (x, y) in [(270, 140), (270, 330), (300, 640), (620, 715), (860, 715)]:
    svg.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{C["arrosage"]}" stroke="#fff" stroke-width="2"/>')
text(290, 128, "Arrosage", 16, 700, C["arrosage"], anchor="start")
text(560, 705, "Ligne d'arrosage · robinets", 13, 600, C["arrosage"], italic=True)

# Faisceaux de 5 conduites principales
ORDER = [C["froide"], C["froide"], C["chaude"], C["chaude"], C["jardin"]]
# -> Maison 3
for i, col in enumerate(ORDER):
    x = 975 + 10 * i; y = 920 - 10 * i
    pipe([(x, 1000), (x, y), (940, y)], col, 4, r=12)
# -> Maison 2
for i, col in enumerate(ORDER):
    x = 1055 + 10 * i; y = 680 - 10 * i; xt = 700 + 10 * i
    pipe([(x, 1000), (x, y), (xt, y), (xt, 490)], col, 4, r=14)
# -> Maison 1
for i, col in enumerate(ORDER):
    x = 1115 + 10 * i
    pipe([(x, 1000), (x, 510)], col, 4)

vanne(900, 900, True, "l")
vanne(678, 540, True, "l")
vanne(1180, 560, True, "r")
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
    (C["chaude"], 4, None, "Eau chaude (chaudière)"),
    (C["jardin"], 4, None, "Conduite jardin / puits"),
    (C["piscine"], 5, "12 7", "Eau piscine"),
    (C["arrosage"], 3, None, "Ligne d'arrosage"),
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
arrow(px + 50, y, "r", C["txt"], 9); text(px + 95, y + 5, "Sens d'écoulement", 15, 500, anchor="start"); y += 50

svg.append(f'<line x1="{px+20}" y1="{y}" x2="{px+270}" y2="{y}" stroke="#cbd2d9"/>'); y += 34
text(px + 20, y, "FAISCEAU PRINCIPAL", 15, 800, "#5b6672", anchor="start"); y += 28
text(px + 20, y, "Depuis le local chaudière vers", 14, 500, anchor="start"); y += 20
text(px + 20, y, "chaque maison (1, 2, 3) :", 14, 500, anchor="start"); y += 30
for col, lab in [(C["froide"], "2 × eau froide"), (C["chaude"], "2 × eau chaude"), (C["jardin"], "1 × conduite jardin")]:
    svg.append(f'<rect x="{px+20}" y="{y-12}" width="34" height="14" rx="3" fill="{col}"/>')
    text(px + 66, y, lab, 14, 500, anchor="start"); y += 28

# Nord
ny = 920
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
