"""
Envoi d'e-mails par SMTP.

Le serveur se configure par variables d'environnement, jamais dans le code :

    SMTP_HOTE=smtp.gmail.com
    SMTP_PORT=587
    SMTP_UTILISATEUR=maison.des.garnitures@gmail.com
    SMTP_MOTDEPASSE=le-mot-de-passe-d-application
    SMTP_EXPEDITEUR=Maison des Garnitures <maison.des.garnitures@gmail.com>

Avec Gmail, le mot de passe du compte ne fonctionne pas : il faut creer un
« mot de passe d'application » depuis les reglages de securite Google, ce qui
exige la validation en deux etapes. Ce mot de passe ne donne acces qu'a
l'envoi, et se revoque sans toucher au compte.

Sans configuration, envoyer() renvoie False et journalise la raison : la page
qui l'appelle ne doit jamais reveler au visiteur si un compte existe.
"""

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

journal = logging.getLogger(__name__)


def configure():
    """Vrai si les quatre reglages indispensables sont presents."""
    return all(os.environ.get(cle) for cle in
               ("SMTP_HOTE", "SMTP_UTILISATEUR", "SMTP_MOTDEPASSE"))


def expediteur():
    return (os.environ.get("SMTP_EXPEDITEUR")
            or os.environ.get("SMTP_UTILISATEUR") or "")


def envoyer(destinataire, sujet, texte, html=None):
    """Envoie un message. Renvoie True si le serveur l'a accepte.

    Aucune exception ne remonte : un serveur SMTP injoignable ne doit pas
    faire tomber la page qui appelle cette fonction.
    """
    if not configure():
        journal.warning("SMTP non configure : message a %s non envoye",
                        destinataire)
        return False

    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = expediteur()
    message["To"] = destinataire
    message.set_content(texte)
    if html:
        message.add_alternative(html, subtype="html")

    hote = os.environ["SMTP_HOTE"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    utilisateur = os.environ["SMTP_UTILISATEUR"]
    mot_de_passe = os.environ["SMTP_MOTDEPASSE"]

    try:
        contexte = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(hote, port, context=contexte, timeout=20) as s:
                s.login(utilisateur, mot_de_passe)
                s.send_message(message)
        else:
            with smtplib.SMTP(hote, port, timeout=20) as s:
                s.starttls(context=contexte)
                s.login(utilisateur, mot_de_passe)
                s.send_message(message)
        journal.info("Message envoye a %s", destinataire)
        return True
    except Exception as erreur:
        # On journalise sans detailler cote visiteur : le message d'erreur
        # d'un serveur SMTP peut confirmer l'existence d'une adresse.
        journal.error("Envoi a %s impossible : %s", destinataire, erreur)
        return False
