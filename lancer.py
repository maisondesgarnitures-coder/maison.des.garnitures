"""
Lanceur de la boutique Maison des Garnitures.

    python lancer.py              -> demarre en local et ouvre le navigateur
    python lancer.py --partage    -> demarre et publie une adresse temporaire
                                     accessible depuis n'importe quel ordinateur

En mode partage, le debogueur Flask est desactive : laisse en marche sur
Internet, il permettrait a n'importe qui d'executer du code sur ce PC.
"""

import getpass
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import webbrowser

DOSSIER = os.path.abspath(os.path.dirname(__file__))
FICHIER_CLE = os.path.join(DOSSIER, ".cle_secrete")
MOT_DE_PASSE_PAR_DEFAUT = "ChangeMoi123!"
PORT = int(os.environ.get("PORT", "5000"))


def titre(texte):
    print("\n" + "=" * 62)
    print("  " + texte)
    print("=" * 62)


def cle_secrete():
    """Genere une cle une fois pour toutes et la conserve entre les demarrages."""
    if os.path.exists(FICHIER_CLE):
        cle = open(FICHIER_CLE, encoding="utf-8").read().strip()
        if len(cle) >= 32:
            return cle
    cle = secrets.token_hex(32)
    with open(FICHIER_CLE, "w", encoding="utf-8") as f:
        f.write(cle)
    print("  Cle de securite generee (.cle_secrete)")
    return cle


def installer_si_absent(module, paquet=None):
    try:
        __import__(module)
        return True
    except ImportError:
        paquet = paquet or module
        print("  Installation de %s..." % paquet)
        code = subprocess.call([sys.executable, "-m", "pip", "install", "--quiet", paquet])
        if code != 0:
            print("  ECHEC de l'installation de %s" % paquet)
            return False
        return True


def utiliser_certificats_a_jour():
    """Fait verifier les certificats par la liste de certifi, pas par Windows.

    Sur un poste de domaine dont la mise a jour des racines est bloquee, le
    magasin Windows rejette les certificats Let's Encrypt (« certificate has
    expired ») : le telechargement de ngrok echouait et le partage retombait
    sur le seul reseau local. certifi embarque une liste a jour.
    """
    try:
        import certifi
    except ImportError:
        return
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())


def port_occupe(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def adresse_reseau_local():
    """Adresse joignable depuis un autre appareil du meme reseau (wifi, bureau)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def verifier_mot_de_passe_admin(partage):
    """En partage, on refuse de publier une boutique avec le mot de passe d'usine."""
    from werkzeug.security import check_password_hash, generate_password_hash
    import app as boutique

    with boutique.app.app_context():
        admin = boutique.Utilisateur.query.filter_by(role="proprietaire").first()
        if not admin:
            return True
        if not check_password_hash(admin.mot_de_passe_hash, MOT_DE_PASSE_PAR_DEFAUT):
            return True

        if not partage:
            print("  Rappel : le mot de passe administrateur est encore celui d'usine.")
            return True

        titre("MOT DE PASSE ADMINISTRATEUR A CHANGER")
        print("  La boutique va etre accessible depuis Internet.")
        print("  Le mot de passe d'usine est connu de tous : il faut le remplacer.\n")
        while True:
            nouveau = getpass.getpass("  Nouveau mot de passe (8 caracteres minimum) : ")
            if len(nouveau) < 8:
                print("  Trop court.\n")
                continue
            if nouveau == MOT_DE_PASSE_PAR_DEFAUT:
                print("  Choisis-en un different.\n")
                continue
            if nouveau != getpass.getpass("  Confirme le mot de passe : "):
                print("  Les deux saisies different.\n")
                continue
            admin.mot_de_passe_hash = generate_password_hash(nouveau)
            boutique.db.session.commit()
            print("\n  Mot de passe enregistre. Identifiant : %s" % admin.email)
            return True


def ouvrir_tunnel():
    """Publie le port local sur une adresse https temporaire, via ngrok."""
    if not installer_si_absent("pyngrok"):
        return None
    from pyngrok import conf, ngrok

    # Un ngrok.exe depose a cote du projet est utilise tel quel : sur ce
    # poste, l'antivirus efface celui que pyngrok telecharge, mais laisse
    # tranquille celui que l'utilisateur a installe lui-meme.
    for candidat in (os.environ.get("NGROK_PATH"),
                     os.path.join(DOSSIER, "ngrok.exe"),
                     os.path.join(DOSSIER, "ngrok", "ngrok.exe")):
        if candidat and os.path.exists(candidat):
            conf.get_default().ngrok_path = candidat
            print("  ngrok trouve sur place : %s" % candidat)
            break

    jeton = os.environ.get("NGROK_AUTHTOKEN") or ""
    fichier_jeton = os.path.join(DOSSIER, ".jeton_ngrok")
    if not jeton and os.path.exists(fichier_jeton):
        jeton = open(fichier_jeton, encoding="utf-8").read().strip()

    if not jeton:
        titre("UN COMPTE NGROK GRATUIT EST NECESSAIRE")
        print("  1. Cree un compte : https://dashboard.ngrok.com/signup")
        print("  2. Copie ton jeton : https://dashboard.ngrok.com/get-started/your-authtoken")
        print()
        jeton = input("  Colle ton jeton ici (puis Entree) : ").strip()
        if not jeton:
            return None
        with open(fichier_jeton, "w", encoding="utf-8") as f:
            f.write(jeton)
        print("  Jeton enregistre : tu n'auras plus a le saisir.")

    try:
        conf.get_default().auth_token = jeton
        tunnel = ngrok.connect(PORT, "http")
        return tunnel.public_url.replace("http://", "https://")
    except Exception as erreur:
        # Tout echec est rattrape : la boutique doit demarrer en local meme
        # quand le tunnel est refuse.
        message = str(erreur)
        print("  Impossible d'ouvrir le tunnel : %s" % message[:200])
        if "Access is denied" in message or "WinError 5" in message:
            print()
            print("  L'antivirus de l'entreprise supprime ngrok des qu'il est")
            print("  telecharge : le partage par tunnel est impossible sur ce")
            print("  poste. Pour voir la boutique sur un telephone, il faut")
            print("  l'heberger en ligne (Render, PythonAnywhere).")
        return None


def main():
    partage = "--partage" in sys.argv
    os.chdir(DOSSIER)

    titre("MAISON DES GARNITURES" + (" - PARTAGE" if partage else " - LOCAL"))

    if port_occupe(PORT):
        print("  Le port %s est deja utilise : la boutique tourne peut-etre deja." % PORT)
        print("  Ouverture de http://localhost:%s" % PORT)
        webbrowser.open("http://localhost:%s" % PORT)
        return

    for module, paquet in [("flask", "Flask"), ("flask_sqlalchemy", "Flask-SQLAlchemy"),
                           ("requests", "requests"), ("openpyxl", "openpyxl"),
                           ("certifi", "certifi")]:
        if not installer_si_absent(module, paquet):
            print("\n  Installation impossible. Verifie ta connexion.")
            input("  Appuie sur Entree pour fermer...")
            return

    utiliser_certificats_a_jour()
    os.environ["SECRET_KEY"] = cle_secrete()
    verifier_mot_de_passe_admin(partage)

    import app as boutique

    adresse_publique = None
    if partage:
        print("\n  Ouverture de l'adresse publique...")
        adresse_publique = ouvrir_tunnel()

    titre("BOUTIQUE EN LIGNE")
    print("  Sur cet ordinateur   : http://localhost:%s" % PORT)
    ip = adresse_reseau_local()
    if ip:
        print("  Sur le meme reseau   : http://%s:%s" % (ip, PORT))
    if adresse_publique:
        print("  Depuis n'importe ou  : %s" % adresse_publique)
        print("\n  Envoie cette derniere adresse a ton collegue.")
        print("  Elle reste valable tant que cette fenetre est ouverte.")
    elif partage:
        print("\n  Adresse publique indisponible : seul le reseau local fonctionne.")
        print("  Regarde l'erreur affichee plus haut dans cette fenetre :")
        print("    « certificate » -> pip install -U certifi, puis relance")
        print("    « authtoken »   -> jeton refuse : supprime .jeton_ngrok")

    print("\n  Administration : /admin")
    print("  Pour arreter : ferme cette fenetre ou appuie sur Ctrl+C")
    print("=" * 62 + "\n")

    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:%s" % PORT)).start()

    try:
        # En partage, le debogueur est coupe : il permettrait d'executer
        # du code a distance sur cet ordinateur.
        boutique.app.run(host="0.0.0.0", port=PORT,
                         debug=not partage, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        if adresse_publique:
            try:
                from pyngrok import ngrok
                ngrok.kill()
            except Exception:
                pass
        print("\n  Boutique arretee.")


if __name__ == "__main__":
    main()
