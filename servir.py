"""
Serveur de production de la boutique Maison des Garnitures.

    python servir.py

Le serveur de developpement de Flask sert une requete a la fois et affiche
une console d'execution de code sur ses pages d'erreur : il n'a rien a faire
sur Internet. Waitress est un vrai serveur, il fonctionne sous Windows comme
sous Linux, et n'a besoin d'aucune configuration.

Variables d'environnement lues (voir .env.exemple) :

    MODE=production     durcit les cookies et coupe le debogueur
    SECRET_KEY=...      cle de signature des sessions, obligatoire
    DATABASE_URL=...    PostgreSQL ; sans elle, SQLite en local
    PORT=8000           port d'ecoute
    THREADS=8           requetes servies en parallele
"""

import os
import sys


def charger_env():
    """Lit un fichier .env s'il existe, sans ecraser l'environnement reel.

    L'hebergeur fournit ses propres variables : elles doivent primer sur le
    fichier, qui ne sert qu'aux essais sur un poste.
    """
    chemin = os.path.join(os.path.abspath(os.path.dirname(__file__)), ".env")
    if not os.path.exists(chemin):
        return
    for ligne in open(chemin, encoding="utf-8"):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


def main():
    charger_env()
    os.environ.setdefault("MODE", "production")

    try:
        from waitress import serve
    except ImportError:
        print("Waitress n'est pas installe. Lance :  pip install -r requirements.txt")
        return 1

    try:
        from app import app
    except RuntimeError as erreur:
        # Cle absente, base injoignable : un message clair vaut mieux
        # qu'une trace de cinquante lignes.
        print("\nDemarrage impossible : %s\n" % erreur)
        return 1

    port = int(os.environ.get("PORT", "8000"))
    threads = int(os.environ.get("THREADS", "8"))

    print("Boutique servie sur le port %s (%s fils)" % (port, threads))
    print("Mode : %s" % os.environ.get("MODE"))
    print("Base : %s" % app.config["SQLALCHEMY_DATABASE_URI"].split("@")[-1][:60])

    serve(app, host="0.0.0.0", port=port, threads=threads,
          # Derriere le proxy de l'hebergeur, l'adresse du client arrive dans
          # un en-tete : sans cette limite Waitress refuserait de la lire.
          trusted_proxy="*", trusted_proxy_count=1,
          url_scheme=os.environ.get("URL_SCHEME", "https"),
          ident="Maison des Garnitures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
