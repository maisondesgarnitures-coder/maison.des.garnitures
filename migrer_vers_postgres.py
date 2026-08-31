"""
Recopie la boutique de SQLite vers PostgreSQL.

    set DATABASE_URL=postgresql://utilisateur:motdepasse@serveur:5432/base
    python migrer_vers_postgres.py

Le fichier SQLite n'est jamais modifie : en cas de probleme, il suffit de
retirer DATABASE_URL pour revenir a lui.

La copie se fait table par table, dans l'ordre des dependances (une commande
avant ses lignes, un produit avant ses photos), puis les compteurs de chaque
table sont recales : sans cela PostgreSQL redonnerait l'identifiant 1 a la
prochaine commande et refuserait de l'enregistrer.
"""

import os
import sys

if not (os.environ.get("DATABASE_URL") or "").strip():
    print("DATABASE_URL n'est pas definie : rien a faire.")
    print('Exemple : set DATABASE_URL=postgresql://user:pass@hote:5432/boutique')
    sys.exit(1)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FICHIER_SQLITE = os.path.join(BASE_DIR, "boutique.db")
if not os.path.exists(FICHIER_SQLITE):
    print("boutique.db introuvable : il n'y a rien a copier.")
    sys.exit(1)

import sqlalchemy as sa

import app as boutique

# Ordre de copie : un parent avant ses enfants.
TABLES = [
    "parametre_boutique", "utilisateur", "categorie", "produit",
    "image_produit", "option_produit", "valeur_option", "variante_produit",
    "palier_prix", "lot_produit", "transporteur", "page_statique",
    "code_promo", "avis_produit", "panier_abandonne",
    "commande", "ligne_commande", "historique_commande",
]


def confirmer(cible):
    print("=" * 64)
    print("  COPIE DE LA BOUTIQUE VERS POSTGRESQL")
    print("=" * 64)
    print("  Source : %s" % FICHIER_SQLITE)
    print("  Cible  : %s" % cible.split("@")[-1])
    print()
    print("  Les tables de la cible seront VIDEES avant la copie.")
    reponse = input("  Taper COPIER pour continuer : ").strip()
    return reponse == "COPIER"


def main():
    cible_url = boutique.app.config["SQLALCHEMY_DATABASE_URI"]
    if not cible_url.startswith("postgresql"):
        print("DATABASE_URL ne pointe pas vers PostgreSQL : %s" % cible_url[:40])
        return 1
    if not confirmer(cible_url):
        print("  Annule.")
        return 1

    source = sa.create_engine("sqlite:///" + FICHIER_SQLITE)
    cible = sa.create_engine(cible_url)

    # Les tables sont creees d'apres les modeles : structure identique.
    with boutique.app.app_context():
        boutique.db.create_all()

    meta_source = sa.MetaData()
    meta_source.reflect(bind=source)
    meta_cible = sa.MetaData()
    meta_cible.reflect(bind=cible)

    total = 0
    with source.connect() as cnx_source, cible.begin() as cnx_cible:
        # Vidage a l'envers : les enfants d'abord, sinon les cles etrangeres
        # bloquent la suppression du parent.
        for nom in reversed(TABLES):
            if nom in meta_cible.tables:
                cnx_cible.execute(sa.text('DELETE FROM "%s"' % nom))

        for nom in TABLES:
            if nom not in meta_source.tables or nom not in meta_cible.tables:
                print("  %-22s absente, ignoree" % nom)
                continue
            table_source = meta_source.tables[nom]
            table_cible = meta_cible.tables[nom]
            colonnes = [c.name for c in table_cible.columns
                        if c.name in table_source.columns]

            lignes = [dict(r._mapping) for r in
                      cnx_source.execute(sa.select(*[table_source.c[c] for c in colonnes]))]
            if lignes:
                cnx_cible.execute(sa.insert(table_cible), lignes)
            total += len(lignes)
            print("  %-22s %5s ligne(s)" % (nom, len(lignes)))

        # Recalage des compteurs d'identifiants.
        for nom in TABLES:
            if nom not in meta_cible.tables:
                continue
            if "id" not in meta_cible.tables[nom].columns:
                continue
            cnx_cible.execute(sa.text(
                "SELECT setval(pg_get_serial_sequence('\\"%s\\"', 'id'), "
                "COALESCE((SELECT MAX(id) FROM \\"%s\\"), 1), true)" % (nom, nom)))

    print()
    print("  %s ligne(s) copiees." % total)
    print("  Verifie la boutique, puis garde boutique.db en sauvegarde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
