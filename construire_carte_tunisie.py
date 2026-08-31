"""
Construit la carte SVG des gouvernorats tunisiens a partir d'OpenStreetMap.

A lancer une seule fois : le resultat est enregistre dans
static/carte_tunisie.json et l'application n'a plus besoin du reseau ensuite.

Donnees (c) contributeurs OpenStreetMap, sous licence ODbL.
"""

import json
import math
import os
import unicodedata

import requests

OVERPASS = "https://overpass-api.de/api/interpreter"
REQUETE = """
[out:json][timeout:240];
area["ISO3166-1"="TN"][admin_level=2]->.tn;
relation(area.tn)["boundary"="administrative"]["admin_level"="4"];
out geom;
"""
SORTIE = os.path.join("static", "carte_tunisie.json")

# La boutique nomme les gouvernorats sans accents : on rapproche les deux graphies.
CORRESPONDANCES = {
    "beja": "Beja", "jendouba": "Jendouba", "le kef": "Le Kef", "kef": "Le Kef",
    "siliana": "Siliana", "kairouan": "Kairouan", "kasserine": "Kasserine",
    "sidi bouzid": "Sidi Bouzid", "gafsa": "Gafsa", "tozeur": "Tozeur",
    "kebili": "Kebili", "gabes": "Gabes", "medenine": "Medenine",
    "tataouine": "Tataouine", "sfax": "Sfax", "mahdia": "Mahdia",
    "monastir": "Monastir", "sousse": "Sousse", "nabeul": "Nabeul",
    "zaghouan": "Zaghouan", "bizerte": "Bizerte", "tunis": "Tunis",
    "ariana": "Ariana", "ben arous": "Ben Arous", "manouba": "Manouba",
    "la manouba": "Manouba", "mannouba": "Manouba", "manubah": "Manouba",
}


def sans_accents(texte):
    decompose = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower().strip()


def nettoyer_libelle(brut):
    """'Gouvernorat La Manouba' -> 'manouba'. OSM varie les formulations."""
    texte = sans_accents(brut)
    for prefixe in ("gouvernorat de ", "gouvernorat d'", "gouvernorat du ", "gouvernorat "):
        if texte.startswith(prefixe):
            texte = texte[len(prefixe):]
            break
    return texte.strip()


def assembler_anneaux(segments):
    """Recolle les troncons de frontiere bout a bout pour former des contours fermes."""
    restants = [list(s) for s in segments if len(s) > 1]
    anneaux = []

    while restants:
        courant = restants.pop(0)
        progresse = True
        while progresse and courant[0] != courant[-1]:
            progresse = False
            for i, seg in enumerate(restants):
                if seg[0] == courant[-1]:
                    courant += seg[1:]; restants.pop(i); progresse = True; break
                if seg[-1] == courant[-1]:
                    courant += seg[::-1][1:]; restants.pop(i); progresse = True; break
                if seg[-1] == courant[0]:
                    courant = seg[:-1] + courant; restants.pop(i); progresse = True; break
                if seg[0] == courant[0]:
                    courant = seg[::-1][:-1] + courant; restants.pop(i); progresse = True; break
        if len(courant) > 3:
            anneaux.append(courant)
    return anneaux


def simplifier(points, tolerance):
    """Douglas-Peucker : retire les points qui ne changent pas la silhouette."""
    if len(points) < 3:
        return points

    def distance(p, a, b):
        if a == b:
            return math.hypot(p[0] - a[0], p[1] - a[1])
        t = max(0, min(1, ((p[0]-a[0])*(b[0]-a[0]) + (p[1]-a[1])*(b[1]-a[1]))
                          / ((b[0]-a[0])**2 + (b[1]-a[1])**2)))
        proj = (a[0] + t*(b[0]-a[0]), a[1] + t*(b[1]-a[1]))
        return math.hypot(p[0]-proj[0], p[1]-proj[1])

    dmax, index = 0, 0
    for i in range(1, len(points) - 1):
        d = distance(points[i], points[0], points[-1])
        if d > dmax:
            dmax, index = d, i

    if dmax > tolerance:
        return (simplifier(points[:index+1], tolerance)[:-1]
                + simplifier(points[index:], tolerance))
    return [points[0], points[-1]]


def main():
    print("Interrogation d'OpenStreetMap...")
    r = requests.post(OVERPASS, data={"data": REQUETE}, timeout=300,
                      headers={"User-Agent": "MaisonDesGarnitures/1.0"})
    r.raise_for_status()
    elements = r.json().get("elements", [])
    print("  %s relations recues (%s Ko)" % (len(elements), len(r.content) // 1024))

    gouvernorats = {}
    for rel in elements:
        etiquettes = rel.get("tags") or {}
        brut = (etiquettes.get("name:fr") or etiquettes.get("name") or "").strip()
        nom = CORRESPONDANCES.get(nettoyer_libelle(brut))
        if not nom:
            print("  ignore (non reconnu) :", brut)
            continue

        segments = [[(p["lon"], p["lat"]) for p in m.get("geometry") or []]
                    for m in rel.get("members", [])
                    if m.get("type") == "way" and m.get("role") in ("outer", "")]
        anneaux = assembler_anneaux(segments)
        if anneaux:
            gouvernorats.setdefault(nom, []).extend(anneaux)

    print("  %s gouvernorats reconnus" % len(gouvernorats))

    # Cadrage commun a toutes les regions
    tous = [p for anneaux in gouvernorats.values() for a in anneaux for p in a]
    lon_min = min(p[0] for p in tous); lon_max = max(p[0] for p in tous)
    lat_min = min(p[1] for p in tous); lat_max = max(p[1] for p in tous)

    largeur = 620.0
    lat_moy = math.radians((lat_min + lat_max) / 2)
    echelle = largeur / ((lon_max - lon_min) * math.cos(lat_moy))
    hauteur = (lat_max - lat_min) * echelle

    def projeter(p):
        x = (p[0] - lon_min) * math.cos(lat_moy) * echelle
        y = (lat_max - p[1]) * echelle
        return (round(x, 1), round(y, 1))

    tracés = {}
    total_points = 0
    for nom, anneaux in gouvernorats.items():
        morceaux = []
        for anneau in sorted(anneaux, key=len, reverse=True)[:6]:
            points = simplifier([projeter(p) for p in anneau], 1.1)
            if len(points) < 4:
                continue
            total_points += len(points)
            morceaux.append("M" + " ".join("%g,%g" % p for p in points) + "Z")
        if morceaux:
            tracés[nom] = " ".join(morceaux)

    carte = {"largeur": round(largeur), "hauteur": round(hauteur),
             "attribution": "(c) contributeurs OpenStreetMap", "regions": tracés}
    os.makedirs("static", exist_ok=True)
    with open(SORTIE, "w", encoding="utf-8") as f:
        json.dump(carte, f, ensure_ascii=False, separators=(",", ":"))

    print("  %s regions tracees, %s points au total" % (len(tracés), total_points))
    print("  %s : %s Ko" % (SORTIE, os.path.getsize(SORTIE) // 1024))
    manquants = set(CORRESPONDANCES.values()) - set(tracés)
    if manquants:
        print("  MANQUANTS :", sorted(manquants))


if __name__ == "__main__":
    main()
