# -*- coding: utf-8 -*-
"""
Archive complete de la vitrine Converty, pour ne plus en dependre.

    python archiver_converty.py

Tout ce que l'API publique expose est enregistre tel quel dans
« archive_converty/ » : produits, categories, et la page d'accueil entiere
(qui porte la configuration du theme, les integrations et les pages libres).
Les images encore absentes du dossier « static/img/produits » sont
telechargees a cote.

Une fois ce dossier constitue, la boutique Converty peut etre fermee sans
rien perdre : le catalogue vit dans boutique.db, les photos dans static/img,
et cette archive garde la source d'origine en cas de doute.
"""

import io
import json
import os
import re
import sys
from datetime import datetime

import requests

BASE = "https://la-maison-des-garnitures.converty.shop"
DOSSIER = os.path.join(os.path.abspath(os.path.dirname(__file__)), "archive_converty")
PHOTOS_APP = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                          "static", "img", "produits")
ENTETES = {"User-Agent": "Mozilla/5.0"}


def ecrire_json(nom, donnees):
    chemin = os.path.join(DOSSIER, nom)
    with io.open(chemin, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)
    return os.path.getsize(chemin)


def recuperer(chemin, params=None):
    reponse = requests.get(BASE + chemin, params=params, timeout=60, headers=ENTETES)
    reponse.raise_for_status()
    return reponse.json()


def urls_des_images(produits, categories):
    """Toutes les adresses d'images citees par la boutique, sans doublon."""
    trouvees = set()

    def ramasser(valeur):
        if isinstance(valeur, str):
            if valeur.startswith("http") and re.search(
                    r"\.(jpe?g|png|webp|gif)(\?|$)", valeur, re.I):
                trouvees.add(valeur)
        elif isinstance(valeur, dict):
            for v in valeur.values():
                ramasser(v)
        elif isinstance(valeur, list):
            for v in valeur:
                ramasser(v)

    ramasser(produits)
    ramasser(categories)
    return sorted(trouvees)


def deja_dans_l_application(url, presentes):
    """L'image est-elle deja telechargee ? Converty nomme par empreinte."""
    base = os.path.basename(url.split("?")[0])
    souche = os.path.splitext(base)[0]
    # Les imports precedents ont pu convertir en .webp et suffixer « _lg ».
    souche = re.sub(r"_(lg|md|sm|thumb)$", "", souche)
    return any(souche in nom for nom in presentes)


def main():
    if not os.path.isdir(DOSSIER):
        os.makedirs(DOSSIER)

    print("Archive de %s" % BASE)
    print()

    produits = recuperer("/api/v1/products", {"limit": 500})
    categories = recuperer("/api/v1/categories")
    liste_produits = produits.get("data", produits)
    liste_categories = categories.get("data", categories)

    print("  produits   : %d (%d octets)"
          % (len(liste_produits), ecrire_json("produits.json", produits)))
    print("  categories : %d (%d octets)"
          % (len(liste_categories), ecrire_json("categories.json", categories)))

    # La page d'accueil porte le theme, les integrations et les pages libres :
    # rien de tout cela n'a d'API publique dediee.
    accueil = requests.get(BASE + "/", timeout=60, headers=ENTETES)
    chemin_html = os.path.join(DOSSIER, "accueil.html")
    with io.open(chemin_html, "w", encoding="utf-8") as f:
        f.write(accueil.text)
    print("  page d'accueil : %d octets (theme, integrations, pages libres)"
          % os.path.getsize(chemin_html))

    # Images : on ne retelecharge que ce qui manque a l'application.
    presentes = set(os.listdir(PHOTOS_APP)) if os.path.isdir(PHOTOS_APP) else set()
    urls = urls_des_images(liste_produits, liste_categories)
    manquantes = [u for u in urls if not deja_dans_l_application(u, presentes)]
    print()
    print("  images citees par Converty : %d" % len(urls))
    print("  deja dans l'application    : %d" % (len(urls) - len(manquantes)))
    print("  a telecharger              : %d" % len(manquantes))

    if manquantes:
        dossier_images = os.path.join(DOSSIER, "images")
        if not os.path.isdir(dossier_images):
            os.makedirs(dossier_images)
        reussies = 0
        for url in manquantes:
            nom = os.path.basename(url.split("?")[0])
            cible = os.path.join(dossier_images, nom)
            if os.path.exists(cible):
                reussies += 1
                continue
            try:
                r = requests.get(url, timeout=60, headers=ENTETES)
                r.raise_for_status()
                with open(cible, "wb") as f:
                    f.write(r.content)
                reussies += 1
            except Exception as erreur:
                print("     echec %s : %s" % (nom, str(erreur)[:60]))
        print("  telechargees               : %d" % reussies)

    with io.open(os.path.join(DOSSIER, "LISEZMOI.txt"), "w", encoding="utf-8") as f:
        f.write(
            u"Archive de la vitrine Converty « La maison des garnitures »\n"
            u"Constituee le %s\n\n"
            u"produits.json    : les %d fiches, telles que l'API publique les donne\n"
            u"categories.json  : les %d categories avec leurs bannieres\n"
            u"accueil.html     : la page d'accueil entiere. Elle contient la\n"
            u"                   configuration du theme, les integrations (dont le\n"
            u"                   Pixel Meta) et les pages libres.\n"
            u"images/          : les images qui n'etaient pas deja dans\n"
            u"                   static/img/produits\n\n"
            u"Ce que cette archive NE contient PAS, faute d'API publique :\n"
            u"  - les commandes passees sur Converty\n"
            u"  - le jeton Conversions API (secret serveur)\n"
            u"  - les SKU et le stock, deja releves dans skus_stock.csv\n"
            % (datetime.now().strftime("%d/%m/%Y a %H:%M"),
               len(liste_produits), len(liste_categories)))

    print()
    print("Archive ecrite dans : %s" % DOSSIER)


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as erreur:
        sys.exit("Reseau indisponible : %s" % erreur)
