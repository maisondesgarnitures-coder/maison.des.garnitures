"""
Change le mot de passe d'un compte de l'administration.

    python reinitialiser_mot_de_passe.py

Sans DATABASE_URL, l'outil travaille sur la base locale boutique.db.
Avec DATABASE_URL, il travaille sur la base en ligne :

    $env:DATABASE_URL = "...External Database URL..."
    python reinitialiser_mot_de_passe.py

Le mot de passe est saisi en aveugle : il n'apparait ni a l'ecran, ni dans
l'historique du terminal. Seule son empreinte est enregistree — la base ne
contient jamais le mot de passe lui-meme.
"""

import getpass
import os
import sys

from werkzeug.security import generate_password_hash

import app as boutique

MINIMUM = 8


def choisir_compte(comptes):
    """Un seul compte : on le prend. Plusieurs : on demande lequel."""
    if len(comptes) == 1:
        return comptes[0]
    print()
    for rang, u in enumerate(comptes, start=1):
        print("  %d. %s  (%s)" % (rang, u.email, u.role))
    while True:
        saisi = input("\n  Numero du compte a modifier : ").strip()
        if saisi.isdigit() and 1 <= int(saisi) <= len(comptes):
            return comptes[int(saisi) - 1]
        print("  Numero invalide.")


def main():
    cible = boutique.app.config["SQLALCHEMY_DATABASE_URI"]
    lisible = cible.split("@")[-1] if "@" in cible else cible

    print("=" * 64)
    print("  CHANGEMENT DE MOT DE PASSE")
    print("=" * 64)
    print("  Base : %s" % lisible[:70])

    with boutique.app.app_context():
        comptes = boutique.Utilisateur.query.order_by(
            boutique.Utilisateur.id).all()
        if not comptes:
            print("\n  Aucun compte dans cette base.")
            return 1

        compte = choisir_compte(comptes)
        print("\n  Compte : %s  (%s)" % (compte.email, compte.role))
        print("  Le mot de passe ne s'affichera pas pendant la saisie.\n")

        while True:
            nouveau = getpass.getpass("  Nouveau mot de passe : ")
            if len(nouveau) < MINIMUM:
                print("  Trop court : %d caracteres minimum.\n" % MINIMUM)
                continue
            if nouveau != getpass.getpass("  Confirme le mot de passe : "):
                print("  Les deux saisies different.\n")
                continue
            break

        compte.mot_de_passe_hash = generate_password_hash(nouveau)
        boutique.db.session.commit()

    print("\n  Mot de passe enregistre pour %s." % compte.email)
    print("  Il faut le changer separement sur l'autre base : la locale et")
    print("  celle en ligne ne partagent rien.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
