# -*- coding: utf-8 -*-
"""Code-barres Code 128 dessine en SVG, sans dependance externe.

Le bon de livraison doit etre lisible par la douchette du transporteur.
Code 128 accepte chiffres et lettres et se lit sur toutes les douchettes du
marche ; le jeu C compacte les chiffres deux par deux, ce qui raccourcit
nettement un numero de suivi.
"""

# Les 107 motifs de Code 128 : largeurs des barres et espaces, en alternance.
MOTIFS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312",
    "132212", "221213", "221312", "231212", "112232", "122132", "122231", "113222",
    "123122", "123221", "223211", "221132", "221231", "213212", "223112", "312131",
    "311222", "321122", "321221", "312212", "322112", "322211", "212123", "212321",
    "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121",
    "313121", "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111", "111224",
    "111422", "121124", "121421", "141122", "141221", "112214", "112412", "122114",
    "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112",
    "421211", "212141", "214121", "412121", "111143", "111341", "131141", "114113",
    "114311", "411113", "411311", "113141", "114131", "311141", "411131", "211412",
    "211214", "211232", "233111", "200000",
]

DEBUT_B, DEBUT_C, BASCULE_B, BASCULE_C, FIN = 104, 105, 100, 99, 106


def _codes(donnee):
    """Suite de codes Code 128, en profitant du jeu C pour les chiffres."""
    codes, position, jeu = [], 0, None

    def chiffres_devant(depuis):
        n = 0
        while depuis + n < len(donnee) and donnee[depuis + n].isdigit():
            n += 1
        return n

    while position < len(donnee):
        suite = chiffres_devant(position)
        # Le jeu C n'est rentable qu'a partir de quatre chiffres d'affilee,
        # ou deux si c'est tout ce qui reste.
        assez = suite >= 4 or (suite >= 2 and position + suite == len(donnee))
        if assez and suite % 2:
            suite -= 1          # le jeu C avance par paires
        if assez and suite >= 2:
            if jeu != "C":
                codes.append(DEBUT_C if jeu is None else BASCULE_C)
                jeu = "C"
            for i in range(0, suite, 2):
                codes.append(int(donnee[position + i:position + i + 2]))
            position += suite
        else:
            if jeu != "B":
                codes.append(DEBUT_B if jeu is None else BASCULE_B)
                jeu = "B"
            codes.append(ord(donnee[position]) - 32)
            position += 1

    if not codes:
        codes = [DEBUT_B]
    total = codes[0] + sum(c * i for i, c in enumerate(codes[1:], start=1))
    codes.append(total % 103)
    codes.append(FIN)
    return codes


def svg(donnee, hauteur=54, largeur_module=2, marge=8, afficher_texte=True):
    """Retourne le code-barres en SVG, pret a etre insere dans une page."""
    donnee = "".join(c for c in str(donnee or "") if 32 <= ord(c) < 127)
    if not donnee:
        return ""

    barres, x, sombre = [], marge, True
    for code in _codes(donnee):
        for largeur in MOTIFS[code]:
            pas = int(largeur) * largeur_module
            if sombre:
                barres.append('<rect x="%s" y="0" width="%s" height="%s"/>' % (x, pas, hauteur))
            x += pas
            sombre = not sombre
        sombre = True   # chaque motif commence par une barre

    largeur_totale = x + marge
    hauteur_totale = hauteur + (18 if afficher_texte else 0)
    texte = ""
    if afficher_texte:
        texte = ('<text x="%s" y="%s" text-anchor="middle" font-size="13" '
                 'font-family="monospace" letter-spacing="2" fill="#000">%s</text>'
                 % (largeur_totale / 2.0, hauteur + 14, donnee))

    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" '
            'viewBox="0 0 %s %s" role="img" aria-label="Code barre %s">'
            '<rect width="100%%" height="100%%" fill="#fff"/>'
            '<g fill="#000">%s</g>%s</svg>'
            % (largeur_totale, hauteur_totale, largeur_totale, hauteur_totale,
               donnee, "".join(barres), texte))
