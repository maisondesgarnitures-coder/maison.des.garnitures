"""
Migration du catalogue Converty vers Maison des Garnitures.

Le catalogue public de la boutique Converty est lisible sans authentification :
on y prend les noms, descriptions, prix et photos. Le SKU et le stock ne sont
exposes que dans l'espace admin : ils sont fournis a part, dans skus_stock.csv,
au format  reference;sku;stock;statut

Usage :
    python migrer_converty.py            # genere produits_converty.csv
    python migrer_converty.py --importer # genere puis charge dans la boutique
"""

import csv
import html
import os
import re
import sys

import requests

BASE_PUBLIQUE = "https://la-maison-des-garnitures.converty.shop/api/v1"
ENTETES = {"User-Agent": "Mozilla/5.0"}
FICHIER_SKUS = "skus_stock.csv"
FICHIER_SORTIE = "produits_converty.csv"

# Balises interdites, meme si le contenu vient de l'admin de la boutique.
BALISES_DANGEREUSES = re.compile(
    r"<\s*(script|style|iframe|object|embed|form|input)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.I | re.S)
BALISE_ORPHELINE = re.compile(r"<\s*(script|style|iframe|object|embed|form|input)\b[^>]*/?>", re.I)
ATTRIBUT_EVENEMENT = re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
LIEN_JAVASCRIPT = re.compile(r"(href|src)\s*=\s*([\"'])\s*javascript:[^\"']*\2", re.I)


def nettoyer_description(brut):
    """Conserve la mise en forme (titres, gras, paragraphes) mais retire tout script."""
    texte = brut or ""
    texte = BALISES_DANGEREUSES.sub("", texte)
    texte = BALISE_ORPHELINE.sub("", texte)
    texte = ATTRIBUT_EVENEMENT.sub("", texte)
    texte = LIEN_JAVASCRIPT.sub("", texte)
    return texte.strip()


def charger_skus():
    """reference -> (sku, stock, statut)"""
    if not os.path.exists(FICHIER_SKUS):
        print("  ! %s absent : les produits partiront sans SKU ni stock." % FICHIER_SKUS)
        return {}
    table = {}
    with open(FICHIER_SKUS, encoding="utf-8") as f:
        for ligne in f:
            morceaux = ligne.strip().split(";")
            if len(morceaux) >= 4 and morceaux[0].isdigit():
                table[morceaux[0]] = (morceaux[1], morceaux[2], morceaux[3])
    return table


def recuperer(chemin, limite=200):
    r = requests.get(BASE_PUBLIQUE + chemin, params={"page": 1, "limit": limite},
                     headers=ENTETES, timeout=30)
    r.raise_for_status()
    return r.json().get("data") or []


def premiere_image(produit):
    for image in produit.get("images") or []:
        if isinstance(image, dict):
            url = image.get("lg") or image.get("md") or image.get("sm")
        else:
            url = image
        if url:
            return url
    return ""


def construire_csv():
    categories = {c["_id"]: c.get("name", "") for c in recuperer("/categories", 100)}
    produits = recuperer("/products", 200)
    skus = charger_skus()
    print("  %s produits, %s categories recuperes." % (len(produits), len(categories)))

    lignes = []
    sans_stock = 0
    for p in produits:
        reference_num = str(p.get("reference", ""))
        sku, stock, statut = skus.get(reference_num, ("", "", "shown"))
        if not sku:
            sku = p.get("slug") or reference_num
        if stock == "":
            sans_stock += 1
            stock = "0"

        prix = float(p.get("price") or 0)
        compare = float(p.get("comparePrice") or 0)
        # Chez Converty, comparePrice est le prix barre (le plus eleve).
        # Chez nous, prix = prix normal et prix_promo = prix reduit affiche.
        if compare > prix > 0:
            prix_affiche, prix_promo = compare, prix
        else:
            prix_affiche, prix_promo = prix, ""

        noms_categories = [categories.get(c, "") for c in (p.get("categories") or [])]
        categorie = next((n for n in noms_categories if n), "")

        lignes.append({
            "Nom": p.get("name", "").strip(),
            "Reference": sku,
            "Categorie": categorie,
            "Prix": "%.3f" % prix_affiche,
            "Prix promo": ("%.3f" % prix_promo) if prix_promo else "",
            "Stock": stock,
            "Description": nettoyer_description(p.get("description")),
            "Couleur": "",
            "Dimensions": "",
            "Image": premiere_image(p),
        })

    with open(FICHIER_SORTIE, "w", encoding="utf-8-sig", newline="") as f:
        writeur = csv.DictWriter(f, fieldnames=list(lignes[0].keys()), delimiter=";")
        writeur.writeheader()
        writeur.writerows(lignes)

    en_promo = sum(1 for l in lignes if l["Prix promo"])
    avec_image = sum(1 for l in lignes if l["Image"])
    print("  %s -> %s lignes | %s en promo | %s avec photo | %s sans stock connu"
          % (FICHIER_SORTIE, len(lignes), en_promo, avec_image, sans_stock))
    return lignes


def importer_dans_la_boutique():
    import io
    import app as boutique

    with open(FICHIER_SORTIE, "rb") as f:
        donnees = f.read()

    client = boutique.app.test_client()
    client.post("/admin/login", data={"email": "admin@maisondesgarnitures.tn",
                                      "mot_de_passe": "ChangeMoi123!"})
    reponse = client.post("/admin/produits/import",
                          data={"fichier_csv": (io.BytesIO(donnees), FICHIER_SORTIE),
                                "telecharger_images": "1"},
                          content_type="multipart/form-data", follow_redirects=True)
    for bloc in reponse.get_data(as_text=True).split('<div class="flash'):
        if "Import termine" in bloc or "Impossible" in bloc:
            print("  " + html.unescape(bloc.split(">")[1].split("<")[0].strip()))


if __name__ == "__main__":
    print("Recuperation du catalogue Converty...")
    construire_csv()
    if "--importer" in sys.argv:
        print("Import dans la boutique...")
        importer_dans_la_boutique()
