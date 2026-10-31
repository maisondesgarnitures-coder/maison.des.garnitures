"""
Recadre en carre, sur fond blanc, la photo principale des produits d'un rayon.

Le cadrage reprend celui des produits modeles (les poignees 179 a 182) : on
mesure la marge blanche qui entoure l'objet sur leurs photos, puis on applique
la meme marge et la meme taille aux autres. L'objet est detoure de son fond
d'origine, centre et pose sur un carre blanc.

Rien n'est detruit : la nouvelle photo est un nouveau fichier, l'ancienne reste
sur le disque et son nom est affiche, pour revenir en arriere au besoin.

A lancer la ou tourne la boutique (meme base, meme dossier static/img/produits).

Usage :
    python recadrer_photos_carrees.py                   # simulation, rien n'est ecrit
    python recadrer_photos_carrees.py --appliquer
    python recadrer_photos_carrees.py --rayons 89 91 --modeles 179 180 181 182
"""

import argparse
import os
import statistics
import uuid

from PIL import Image, ImageChops, ImageOps

import app as boutique

RAYONS = [89, 91]
MODELES = [179, 180, 181, 182]

# Valeurs de secours si les photos modeles sont introuvables.
TAILLE_DEFAUT = 1000
MARGE_DEFAUT = 0.08

# Ecart de couleur (0-255) au-dela duquel un pixel n'est plus du fond.
SEUIL_FOND = 24
BLANC = (255, 255, 255)


def dossier():
    return boutique.app.config["UPLOAD_FOLDER"]


def ouvrir_sur_blanc(chemin):
    """L'image droite (EXIF), en RVB, la transparence aplatie sur du blanc."""
    image = ImageOps.exif_transpose(Image.open(chemin))
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        fond = Image.new("RGB", image.size, BLANC)
        fond.paste(image, mask=image.getchannel("A"))
        return fond
    return image.convert("RGB")


def couleur_du_fond(image):
    """Le fond d'origine, devine sur les quatre coins et le milieu des bords."""
    l, h = image.size
    points = [(0, 0), (l - 1, 0), (0, h - 1), (l - 1, h - 1),
              (l // 2, 0), (l // 2, h - 1), (0, h // 2), (l - 1, h // 2)]
    couleurs = [image.getpixel(p) for p in points]
    return tuple(int(statistics.median(c[i] for c in couleurs)) for i in range(3))


def fond_uni(image):
    """Vrai si le pourtour de l'image est d'une seule couleur (fond studio).

    Sur une photo de mise en scene, detourer au seuil mangerait le decor par
    morceaux : on garde alors la photo entiere, posee sur le carre blanc.
    """
    fond = couleur_du_fond(image)
    l, h = image.size
    pas = max(1, min(l, h) // 100)
    bord = ([(x, y) for x in range(0, l, pas) for y in (0, 1, h - 2, h - 1)]
            + [(x, y) for y in range(0, h, pas) for x in (0, 1, l - 2, l - 1)])
    proches = sum(1 for p in bord
                  if sum(abs(a - b) for a, b in zip(image.getpixel(p), fond)) <= SEUIL_FOND * 2)
    return proches >= 0.9 * len(bord)


def boite_objet(image):
    """Le rectangle qui contient l'objet, ou None si l'image est unie."""
    fond = Image.new("RGB", image.size, couleur_du_fond(image))
    ecart = ImageChops.difference(image, fond).convert("L")
    masque = ecart.point(lambda v: 255 if v > SEUIL_FOND else 0)
    return masque.getbbox()


def mesurer_modele(chemin):
    """Taille du carre et marge relative autour de l'objet sur une photo modele."""
    image = ouvrir_sur_blanc(chemin)
    boite = boite_objet(image)
    if not boite:
        return None
    cote = max(image.size)
    objet = max(boite[2] - boite[0], boite[3] - boite[1])
    return cote, (cote - objet) / 2 / cote


def cadrage_des_modeles(ids_modeles):
    mesures = []
    for produit in boutique.Produit.query.filter(boutique.Produit.id.in_(ids_modeles)):
        chemin = os.path.join(dossier(), produit.image or "")
        if produit.image and os.path.isfile(chemin):
            mesure = mesurer_modele(chemin)
            if mesure:
                mesures.append(mesure)
                print("  modele %s : %s px, marge %.1f %%"
                      % (produit.id, mesure[0], mesure[1] * 100))
    if not mesures:
        print("  photos modeles introuvables, cadrage par defaut.")
        return TAILLE_DEFAUT, MARGE_DEFAUT
    taille = int(statistics.median(m[0] for m in mesures))
    marge = statistics.median(m[1] for m in mesures)
    return min(max(taille, 600), 2000), min(max(marge, 0.0), 0.3)


def recadrer(chemin, taille, marge):
    """Nouvelle image carree, objet centre sur blanc.

    Renvoie aussi un drapeau : vrai si le fond n'etait pas uni et que la photo
    a ete posee telle quelle, a verifier a l'oeil.
    """
    image = ouvrir_sur_blanc(chemin)
    if fond_uni(image):
        a_verifier = False
        boite = boite_objet(image) or (0, 0, image.width, image.height)
        objet = image.crop(boite)
        # Le fond d'origine autour de l'objet devient blanc, sans toucher a
        # l'objet : seuls les pixels proches du fond ET relies au bord changent.
        fond = couleur_du_fond(image)
        if sum(abs(a - b) for a, b in zip(fond, BLANC)) > SEUIL_FOND:
            objet = blanchir_fond(objet, fond)
    else:
        a_verifier, objet, marge = True, image, 0

    utile = max(1, round(taille * (1 - 2 * marge)))
    echelle = utile / max(objet.size)
    objet = objet.resize((max(1, round(objet.width * echelle)),
                          max(1, round(objet.height * echelle))), Image.LANCZOS)

    carre = Image.new("RGB", (taille, taille), BLANC)
    carre.paste(objet, ((taille - objet.width) // 2, (taille - objet.height) // 2))
    return carre, a_verifier


def blanchir_fond(image, fond):
    """Remplit de blanc la zone de fond reliee aux bords (remplissage par diffusion)."""
    from PIL import ImageDraw
    image = image.copy()
    l, h = image.size
    pas = max(1, min(l, h) // 20)
    bords = ([(x, 0) for x in range(0, l, pas)] + [(x, h - 1) for x in range(0, l, pas)]
             + [(0, y) for y in range(0, h, pas)] + [(l - 1, y) for y in range(0, h, pas)])
    for point in bords:
        pixel = image.getpixel(point)
        if pixel != BLANC and sum(abs(a - b) for a, b in zip(pixel, fond)) <= SEUIL_FOND * 2:
            ImageDraw.floodfill(image, point, BLANC, thresh=SEUIL_FOND)
    return image


def deja_au_format(chemin, taille, marge):
    """Vrai si la photo est deja carree, sur blanc, avec la bonne marge."""
    image = ouvrir_sur_blanc(chemin)
    if image.width != image.height or not fond_uni(image):
        return False
    if sum(abs(a - b) for a, b in zip(couleur_du_fond(image), BLANC)) > SEUIL_FOND:
        return False
    mesure = mesurer_modele(chemin)
    return bool(mesure) and abs(mesure[1] - marge) <= 0.02


def ids_des_rayons(ids):
    """Les rayons demandes et tous leurs sous-rayons."""
    tous, a_voir = set(), list(ids)
    while a_voir:
        cid = a_voir.pop()
        if cid in tous:
            continue
        tous.add(cid)
        a_voir += [c.id for c in boutique.Categorie.query.filter_by(parent_id=cid)]
    return tous


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--appliquer", action="store_true")
    parser.add_argument("--rayons", type=int, nargs="+", default=RAYONS)
    parser.add_argument("--modeles", type=int, nargs="+", default=MODELES)
    args = parser.parse_args()

    with boutique.app.app_context():
        for cid in args.rayons:
            c = boutique.db.session.get(boutique.Categorie, cid)
            print("Rayon %s : %s" % (cid, c.nom if c else "INTROUVABLE"))

        print("Cadrage des modeles %s :" % ", ".join(map(str, args.modeles)))
        taille, marge = cadrage_des_modeles(args.modeles)
        print("=> carre de %s px, marge %.1f %%\n" % (taille, marge * 100))

        rayons = ids_des_rayons(args.rayons)
        produits = (boutique.Produit.query
                    .filter(boutique.Produit.categorie_id.in_(rayons))
                    .filter(~boutique.Produit.id.in_(args.modeles))
                    .order_by(boutique.Produit.id).all())
        print("%s produit(s) dans ces rayons.\n" % len(produits))

        faits, sans_photo, echecs, deja, a_voir = 0, 0, 0, 0, []
        for produit in produits:
            ancien = produit.image
            chemin = os.path.join(dossier(), ancien or "")
            if not ancien or not os.path.isfile(chemin):
                sans_photo += 1
                print("  %4s  SANS PHOTO       %s" % (produit.id, produit.nom))
                continue
            if deja_au_format(chemin, taille, marge):
                deja += 1
                print("  %4s  deja au format  %s" % (produit.id, produit.nom))
                continue
            try:
                image, douteux = recadrer(chemin, taille, marge)
            except Exception as erreur:
                echecs += 1
                print("  %4s  ECHEC (%s)  %s" % (produit.id, erreur, produit.nom))
                continue

            note = "  [fond non uni : photo entiere, A VERIFIER]" if douteux else ""
            if douteux:
                a_voir.append(produit.id)
            if not args.appliquer:
                faits += 1
                print("  %4s  a recadrer      %s%s" % (produit.id, produit.nom, note))
                continue

            nouveau = "%s.webp" % uuid.uuid4().hex
            image.save(os.path.join(dossier(), nouveau), "WEBP", quality=90, method=6)
            produit.image = nouveau
            # La photo principale figure parfois aussi dans la galerie.
            for photo in produit.images_sup:
                if photo.fichier == ancien:
                    photo.fichier = nouveau
            faits += 1
            print("  %4s  recadree  %s -> %s  %s%s"
                  % (produit.id, ancien, nouveau, produit.nom, note))

        if args.appliquer:
            boutique.db.session.commit()

        mode = "recadree(s)" if args.appliquer else "a recadrer (simulation, --appliquer pour ecrire)"
        print("\n%s photo(s) %s | %s deja au format | %s sans photo | %s echec(s)"
              % (faits, mode, deja, sans_photo, echecs))
        if a_voir:
            print("Fond non uni, a verifier a l'oeil : produits %s" % ", ".join(map(str, a_voir)))


if __name__ == "__main__":
    main()
