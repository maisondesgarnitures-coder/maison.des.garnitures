"""
Rapatrie les bannieres de categories depuis la boutique Converty.

Les images sont telechargees dans static/img/produits et rattachees aux
categories portant le meme nom.

    python importer_bannieres_converty.py             # simulation
    python importer_bannieres_converty.py --appliquer
"""

import os
import sys
import unicodedata

import requests

import app as boutique

BASE = "https://la-maison-des-garnitures.converty.shop/api/v1"
ENTETES = {"User-Agent": "Mozilla/5.0"}
TAILLE_MAX = 8 * 1024 * 1024


MOTS_VIDES = ("de", "du", "des", "la", "le", "les", "et", "d", "l", "a")


def sans_accents(texte):
    decompose = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower().strip()


def cle_comparaison(texte):
    """« Accessoires de Cuisine » et « Accessoires cuisine » designent la meme chose."""
    import re
    mots = re.split(r"[^a-z0-9]+", sans_accents(texte))
    return " ".join(m for m in mots if m and m not in MOTS_VIDES)


def url_banniere(categorie):
    """Prend la meilleure resolution disponible parmi les bannieres declarees."""
    for banniere in categorie.get("banners") or []:
        if isinstance(banniere, dict):
            url = banniere.get("desktop") or banniere.get("lg") or banniere.get("mobile")
            if url:
                return url
        elif banniere:
            return banniere

    for champ in ("banner", "image"):
        valeur = categorie.get(champ)
        if isinstance(valeur, dict):
            url = valeur.get("desktop") or valeur.get("lg") or valeur.get("md") or valeur.get("sm")
            if url:
                return url
        elif valeur:
            return valeur
    return None


def telecharger(url):
    reponse = requests.get(url, timeout=30, headers=ENTETES)
    if reponse.status_code != 200:
        return None, "HTTP %s" % reponse.status_code
    if not (reponse.headers.get("Content-Type") or "").lower().startswith("image/"):
        return None, "ce n'est pas une image"
    if len(reponse.content) > TAILLE_MAX:
        return None, "trop lourde"

    extension = os.path.splitext(url.split("?")[0])[1].lower()
    if extension not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        extension = ".webp"

    nom = "%s%s" % (boutique.uuid.uuid4().hex, extension)
    with open(os.path.join(boutique.app.config["UPLOAD_FOLDER"], nom), "wb") as f:
        f.write(reponse.content)
    return nom, len(reponse.content)


def main(appliquer):
    reponse = requests.get(BASE + "/categories", params={"page": 1, "limit": 100},
                           headers=ENTETES, timeout=30)
    reponse.raise_for_status()
    distantes = reponse.json().get("data") or []
    print("%s categories lues chez Converty." % len(distantes))

    with boutique.app.app_context():
        locales = {cle_comparaison(c.nom): c for c in boutique.Categorie.query.all()}
        posees, sans_image, introuvables = 0, [], []

        for distante in distantes:
            nom = (distante.get("name") or "").strip()
            categorie = locales.get(cle_comparaison(nom))
            if not categorie:
                introuvables.append(nom)
                continue

            url = url_banniere(distante)
            if not url:
                sans_image.append(nom)
                continue

            if not appliquer:
                print("  %-30s banniere disponible" % nom)
                posees += 1
                continue

            fichier, info = telecharger(url)
            if not fichier:
                print("  %-30s ECHEC : %s" % (nom, info))
                continue

            categorie.image = fichier
            posees += 1
            print("  %-30s %s (%s Ko)" % (nom, fichier, info // 1024))

        if appliquer:
            boutique.db.session.commit()

        print("\n%s banniere(s) %s" % (posees, "posee(s)" if appliquer else "a poser"))
        if sans_image:
            print("Sans banniere chez Converty : %s" % ", ".join(sans_image))
        if introuvables:
            print("Categories absentes de la boutique locale : %s" % ", ".join(introuvables))

        if appliquer:
            restantes = [c.nom for c in boutique.Categorie.query.filter_by(image=None).all()]
            if restantes:
                print("\nToujours sans banniere ici : %s" % ", ".join(restantes))


if __name__ == "__main__":
    main("--appliquer" in sys.argv)
