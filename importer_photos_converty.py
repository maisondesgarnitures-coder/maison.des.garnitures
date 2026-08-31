"""
Rapatrie les photos supplementaires du catalogue Converty.

La migration initiale n'avait pris que la premiere photo de chaque produit.
Ce script recupere toutes les autres et les ajoute a la galerie, en se basant
sur la reference (SKU) pour retrouver le produit correspondant.

Usage :
    python importer_photos_converty.py            # simulation, rien n'est ecrit
    python importer_photos_converty.py --appliquer
"""

import os
import sys

import requests

import app as boutique

BASE_PUBLIQUE = "https://la-maison-des-garnitures.converty.shop/api/v1"
ENTETES = {"User-Agent": "Mozilla/5.0"}
TAILLE_MAX = 5 * 1024 * 1024


def urls_photos(produit_converty):
    """Toutes les photos du produit, en meilleure resolution disponible."""
    urls = []
    for image in produit_converty.get("images") or []:
        url = image.get("lg") or image.get("md") or image.get("sm") if isinstance(image, dict) else image
        if url and url not in urls:
            urls.append(url)
    return urls


def telecharger(url):
    reponse = requests.get(url, timeout=25, headers=ENTETES)
    if reponse.status_code != 200:
        return None
    if not (reponse.headers.get("Content-Type") or "").lower().startswith("image/"):
        return None
    if len(reponse.content) > TAILLE_MAX:
        return None

    extension = os.path.splitext(url.split("?")[0])[1].lower()
    if extension not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        extension = ".webp"

    nom = "%s%s" % (boutique.uuid.uuid4().hex, extension)
    with open(os.path.join(boutique.app.config["UPLOAD_FOLDER"], nom), "wb") as f:
        f.write(reponse.content)
    return nom


def main(appliquer):
    r = requests.get(BASE_PUBLIQUE + "/products", params={"page": 1, "limit": 200},
                     headers=ENTETES, timeout=40)
    r.raise_for_status()
    catalogue = r.json().get("data") or []
    print("%s produits lus chez Converty." % len(catalogue))

    with boutique.app.app_context():
        # On indexe nos produits par slug Converty ET par reference, car la
        # reference locale vient du SKU admin, absent du catalogue public.
        par_slug = {}
        for p in boutique.Produit.query.all():
            par_slug[(p.nom or "").strip().lower()] = p

        ajoutees, ignorees, introuvables = 0, 0, 0
        for produit_c in catalogue:
            nom = (produit_c.get("name") or "").strip().lower()
            produit = par_slug.get(nom)
            if not produit:
                introuvables += 1
                continue

            urls = urls_photos(produit_c)
            if len(urls) <= 1:
                continue

            deja = {i.fichier for i in produit.images_sup}
            ordre = max([i.ordre for i in produit.images_sup] or [0])

            # La premiere photo est deja la photo principale : on prend la suite.
            for url in urls[1:]:
                if not appliquer:
                    ajoutees += 1
                    continue
                nom_fichier = telecharger(url)
                if not nom_fichier:
                    ignorees += 1
                    continue
                ordre += 1
                boutique.db.session.add(boutique.ImageProduit(
                    produit_id=produit.id, fichier=nom_fichier, ordre=ordre))
                ajoutees += 1

            if appliquer:
                boutique.db.session.commit()

        mode = "ajoutees" if appliquer else "a ajouter (simulation)"
        print("%s photo(s) %s | %s echec(s) | %s produit(s) non retrouve(s)"
              % (ajoutees, mode, ignorees, introuvables))

        if appliquer:
            total = boutique.ImageProduit.query.count()
            avec = len({i.produit_id for i in boutique.ImageProduit.query.all()})
            print("Galerie : %s photos supplementaires sur %s produits." % (total, avec))


if __name__ == "__main__":
    main("--appliquer" in sys.argv)
