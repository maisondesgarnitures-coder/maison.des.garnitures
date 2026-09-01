import os
import re
import mimetypes
import time
import uuid

import codebarres
import courriel
import hashlib
import secrets
import html
import threading
import json
import itertools
import openpyxl
from traductions import LANGUES, LANGUE_DEFAUT, traduire
from urllib.parse import quote, urlsplit, urlunsplit, parse_qsl, urlencode
import io
import csv
import requests
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Windows ne connait pas le WebP dans sa base de types : sans cette ligne,
# les bannieres partent en « application/octet-stream ». Les navigateurs
# devinent et affichent quand meme, mais un cache ou un robot peut refuser.
mimetypes.add_type("image/webp", ".webp")

def charger_env():
    """Lit le fichier .env s'il existe, sans ecraser l'environnement reel.

    Les reglages secrets ne sont pas versionnes : en ligne ils viennent de
    l'hebergeur, sur un poste ils viennent de ce fichier. Sans cette lecture,
    une variable posee dans .env ne servait qu'a servir.py, pas au lancement
    ordinaire de l'application.
    """
    chemin = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(chemin):
        return
    for ligne in open(chemin, encoding="utf-8"):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        # setdefault : l'hebergeur a toujours le dernier mot sur le fichier.
        os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


charger_env()

# « production » des que la boutique est joignable depuis Internet. Ce seul
# reglage durcit les cookies, coupe le debogueur et exige une vraie cle.
EN_PRODUCTION = os.environ.get("MODE", "local").lower() == "production"


def cle_de_session():
    """Cle de signature des cookies : jamais de valeur connue d'avance.

    Une cle devinable laisse fabriquer une session d'administrateur. On la
    prend dans l'environnement, sinon dans un fichier local genere une fois.
    En production, on refuse de demarrer sans elle plutot que d'inventer une
    cle qui changerait a chaque redemarrage et deconnecterait tout le monde.
    """
    depuis_env = (os.environ.get("SECRET_KEY") or "").strip()
    if len(depuis_env) >= 32:
        return depuis_env
    if EN_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY absente ou trop courte. Genere-la une fois avec "
            "«python -c \"import secrets;print(secrets.token_hex(32))\"» "
            "et mets-la dans les variables d'environnement du serveur.")

    fichier = os.path.join(BASE_DIR, ".cle_secrete")
    if os.path.exists(fichier):
        cle = open(fichier, encoding="utf-8").read().strip()
        if len(cle) >= 32:
            return cle
    cle = secrets.token_hex(32)
    with open(fichier, "w", encoding="utf-8") as f:
        f.write(cle)
    return cle


def adresse_base():
    """PostgreSQL si le serveur en fournit une, SQLite en local."""
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        return "sqlite:///" + os.path.join(BASE_DIR, "boutique.db")
    # Les hebergeurs ecrivent « postgres:// », que SQLAlchemy ne reconnait plus.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    # Devant « postgresql:// », SQLAlchemy va chercher psycopg2, un pilote que
    # le projet n'installe pas : requirements.txt fournit psycopg 3. On nomme
    # donc le pilote explicitement, sinon le demarrage echoue sur
    # « No module named psycopg2 ».
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


app = Flask(__name__)
app.config["SECRET_KEY"] = cle_de_session()
app.config["SQLALCHEMY_DATABASE_URI"] = adresse_base()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Une connexion PostgreSQL inactive est coupee par l'hebergeur : on la
# recycle avant, sinon la premiere visite du matin tombe en erreur.
if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True,
                                               "pool_recycle": 280}

app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "static", "img", "produits")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Le cookie de session ne doit etre lisible ni par un script de la page, ni
# par un reseau qui ecoute, ni servir a une requete venue d'un autre site.
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = EN_PRODUCTION
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=14)
# Plafond des envois : la video autorisee monte a 40 Mo, on garde de la marge
# pour le reste du formulaire. Au-dela, la requete est refusee avant lecture.
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

# Derriere un proxy (hebergeur, Cloudflare), Flask ne voit que le proxy :
# sans cela il croirait la connexion en clair et refuserait le cookie securise.
if EN_PRODUCTION:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config["PREFERRED_URL_SCHEME"] = "https"

db = SQLAlchemy(app)


@app.after_request
def entetes_de_securite(reponse):
    """En-tetes que tout site marchand devrait envoyer."""
    reponse.headers.setdefault("X-Content-Type-Options", "nosniff")
    reponse.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    reponse.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if EN_PRODUCTION:
        reponse.headers.setdefault("Strict-Transport-Security",
                                   "max-age=15552000; includeSubDomains")
    return reponse


@app.errorhandler(413)
def fichier_trop_lourd(erreur):
    flash("Fichier trop lourd. La video est limitee a 40 Mo, les photos a "
          "quelques Mo chacune.", "erreur")
    return redirect(request.referrer or url_for("admin_produits")), 302

MASQUE_JETON = "**********"

# Liste de depart, reprise dans la table Transporteur au premier lancement.
TRANSPORTEURS_TUNISIE = ["First Delivery", "Aramex", "Intigo", "Rapid Poste", "MedEx", "Navex", "Tunisie Express", "Bouguerra Delivery", "Colivry", "Livreur independant", "Autre"]

GOUVERNORATS_TUNISIE = {
    "Tunis": ["Tunis Ville", "Bab El Bhar", "Bab Souika", "Carthage", "El Kabaria", "El Menzah", "El Omrane", "La Marsa", "Le Bardo", "Sidi Hassine"],
    "Ariana": ["Ariana Ville", "Ettadhamen", "Kalaat El Andalous", "La Soukra", "Mnihla", "Raoued", "Sidi Thabet"],
    "Ben Arous": ["Ben Arous", "Bou Mhel El Bassatine", "El Mourouj", "Ezzahra", "Fouchana", "Hammam Chott", "Hammam Lif", "Megrine", "Mornag", "Rades"],
    "Manouba": ["Den Den", "Douar Hicher", "El Batan", "Jedaida", "Manouba", "Mornaguia", "Oued Ellil", "Tebourba"],
    "Nabeul": ["Nabeul", "Beni Khalled", "Beni Khiar", "Dar Chaabane", "El Haouaria", "Grombalia", "Hammamet", "Kelibia", "Korba", "Menzel Temime", "Soliman", "Takelsa"],
    "Zaghouan": ["Zaghouan", "Bir Mcherga", "El Fahs", "Nadhour", "Saouaf", "Zriba"],
    "Bizerte": ["Bizerte Nord", "Bizerte Sud", "El Alia", "Ghar El Melh", "Ghezala", "Joumine", "Mateur", "Menzel Bourguiba", "Menzel Jemil", "Ras Jebel", "Sejnane", "Tinja", "Utique"],
    "Beja": ["Beja Nord", "Beja Sud", "Amdoun", "Goubellat", "Medjez El Bab", "Nefza", "Teboursouk", "Testour", "Thibar"],
    "Jendouba": ["Jendouba", "Jendouba Nord", "Ain Draham", "Balta-Bou Aouane", "Bou Salem", "Fernana", "Ghardimaou", "Oued Meliz", "Tabarka"],
    "Le Kef": ["Le Kef Est", "Le Kef Ouest", "Dahmani", "Jerissa", "Kalaat Khasba", "Kalaat Senan", "Ksour", "Nebeur", "Sakiet Sidi Youssef", "Sers", "Tajerouine", "Touiref"],
    "Siliana": ["Siliana Nord", "Siliana Sud", "Bargou", "Bou Arada", "El Aroussa", "El Krib", "Gaafour", "Kesra", "Makthar", "Rouhia", "Sidi Bou Rouis"],
    "Kairouan": ["Kairouan Nord", "Kairouan Sud", "Bou Hajla", "Chebika", "Cherarda", "El Alaa", "Hajeb El Ayoun", "Haffouz", "Nasrallah", "Oueslatia", "Sbikha"],
    "Kasserine": ["Kasserine Nord", "Kasserine Sud", "El Ayoun", "Ezzouhour", "Feriana", "Foussana", "Hassi El Ferid", "Hidra", "Sbeitla", "Sbiba", "Thala"],
    "Sidi Bouzid": ["Sidi Bouzid Est", "Sidi Bouzid Ouest", "Bir El Hafey", "Cebbala", "Jelma", "Meknassy", "Mezzouna", "Ouled Haffouz", "Regueb", "Souk Jedid"],
    "Sousse": ["Sousse Ville", "Sousse Jaouhara", "Sousse Riadh", "Akouda", "Bouficha", "Enfidha", "Hammam Sousse", "Hergla", "Kalaa Kebira", "Kalaa Seghira", "Kondar", "Msaken", "Sidi Bou Ali", "Sidi El Hani"],
    "Monastir": ["Monastir", "Bekalta", "Bembla", "Beni Hassen", "Jemmal", "Ksar Hellal", "Ksibet El Mediouni", "Moknine", "Ouerdanine", "Sahline", "Teboulba", "Zeramdine"],
    "Mahdia": ["Mahdia", "Bou Merdes", "Chebba", "Chorbane", "El Jem", "Essouassi", "Hebira", "Ksour Essef", "Melloulech", "Ouled Chamekh", "Sidi Alouane"],
    "Sfax": ["Sfax Ville", "Sfax Ouest", "Sfax Sud", "El Amra", "El Hencha", "Ghraiba", "Jebeniana", "Kerkennah", "Mahres", "Menzel Chaker", "Sakiet Eddaier", "Sakiet Ezzit", "Skhira", "Thyna"],
    "Gabes": ["Gabes Ville", "Gabes Ouest", "Gabes Sud", "El Hamma", "El Metouia", "Ghannouch", "Matmata", "Menzel Habib", "Mareth"],
    "Medenine": ["Medenine Nord", "Medenine Sud", "Ben Gardane", "Beni Khedache", "Djerba Ajim", "Djerba Houmt Souk", "Djerba Midoun", "Sidi Makhlouf", "Zarzis"],
    "Tataouine": ["Tataouine Nord", "Tataouine Sud", "Bir Lahmar", "Dhiba", "Ghomrassen", "Remada", "Smar"],
    "Gafsa": ["Gafsa Nord", "Gafsa Sud", "Belkhir", "El Guettar", "El Ksar", "Mdhilla", "Metlaoui", "Redeyef", "Sened", "Sidi Aich"],
    "Tozeur": ["Tozeur", "Degueche", "Hazoua", "Nefta", "Tameghza"],
    "Kebili": ["Kebili Nord", "Kebili Sud", "Douz Nord", "Douz Sud", "Faouar", "Souk El Ahad"],
}

FIRST_DELIVERY_TOKEN = os.environ.get("FIRST_DELIVERY_TOKEN", "")
FIRST_DELIVERY_BASE_URL = "https://www.firstdeliverygroup.com/api/v2"

class CodeReinitialisation(db.Model):
    """Code a usage unique pour reprendre la main sur un compte.

    Le code n'est jamais enregistre en clair : seule son empreinte l'est,
    comme un mot de passe. Quelqu'un qui lirait la base ne pourrait pas s'en
    servir. Il expire vite et ne supporte qu'un petit nombre d'essais, sans
    quoi six chiffres se devinent en quelques milliers de tentatives.
    """
    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateur.id"),
                               nullable=False)
    code_hash = db.Column(db.String(255), nullable=False)
    expire_le = db.Column(db.DateTime, nullable=False)
    essais = db.Column(db.Integer, default=0)
    utilise = db.Column(db.Boolean, default=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    utilisateur = db.relationship("Utilisateur")

    @property
    def valide(self):
        return (not self.utilise
                and self.essais < ESSAIS_CODE_MAX
                and datetime.utcnow() < self.expire_le)


class Utilisateur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    mot_de_passe_hash = db.Column(db.String(255), nullable=False)
    prenom = db.Column(db.String(120))
    telephone = db.Column(db.String(40))
    role = db.Column(db.String(30), nullable=False, default="commandes")
    # Droits detailles (JSON) : {"commandes": ["lire", "modifier"], ...}
    permissions = db.Column(db.Text)
    actif = db.Column(db.Boolean, default=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    alertes_lues_le = db.Column(db.DateTime)
    # Vrai apres une reinitialisation par le proprietaire : le mot de passe
    # provisoire a transite par WhatsApp ou de vive voix, il ne doit pas rester.
    doit_changer_mdp = db.Column(db.Boolean, default=False)

    def verifier_mot_de_passe(self, mdp): return check_password_hash(self.mot_de_passe_hash, mdp)

    @property
    def email_masque(self):
        """m****@gmail.com : de quoi se reconnaitre sans divulguer l'adresse."""
        nom, _, domaine = (self.email or "").partition("@")
        if not domaine:
            return ""
        return "%s%s@%s" % (nom[:1], "*" * max(len(nom) - 1, 1), domaine)

    @property
    def nom_affiche(self):
        return ("%s %s" % (self.prenom or "", self.nom or "")).strip() or self.email

    @property
    def droits(self):
        """Droits detailles, ou ceux du role predefini a defaut."""
        if self.permissions:
            try:
                return json.loads(self.permissions)
            except ValueError:
                pass
        return DROITS_PAR_ROLE.get(self.role, {})

    def enregistrer_droits(self, valeurs):
        self.permissions = json.dumps(valeurs, ensure_ascii=False)

    def peut(self, rubrique, action="lire"):
        """Le proprietaire passe partout ; les autres suivent leur tableau."""
        if self.role == "proprietaire":
            return True
        return action in (self.droits.get(rubrique) or [])

# Quatre crans : type d'outil, matiere, marque, puis le critere d'achat
# (diametre de queue). Au-dela, on empile des clics sans aider a trouver.
PROFONDEUR_MAX = 4


class Categorie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), nullable=False)
    nom_ar = db.Column(db.String(120))
    slug = db.Column(db.String(140), unique=True, nullable=False)
    image = db.Column(db.String(255))
    ordre = db.Column(db.Integer, default=0)
    actif = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text)
    meta_titre = db.Column(db.String(200))
    meta_description = db.Column(db.String(320))
    parent_id = db.Column(db.Integer, db.ForeignKey("categorie.id"))
    produits = db.relationship("Produit", backref="categorie", lazy=True)
    enfants = db.relationship("Categorie", backref=db.backref("parent", remote_side=[id]),
                              order_by="Categorie.ordre")

    @property
    def est_sous_categorie(self):
        return self.parent_id is not None

    @property
    def niveau(self):
        """0 pour une racine, 1 pour une sous-categorie, 2 pour le dernier cran."""
        rang, courante, garde = 0, self.parent, 0
        while courante is not None and garde < PROFONDEUR_MAX:
            rang += 1
            courante = courante.parent
            garde += 1
        return rang

    @property
    def chemin(self):
        """De la racine jusqu'a elle : sert au fil d'Ariane."""
        suite, courante, garde = [], self, 0
        while courante is not None and garde <= PROFONDEUR_MAX:
            suite.insert(0, courante)
            courante = courante.parent
            garde += 1
        return suite

    @property
    def descendants(self):
        """Toutes les categories sous celle-ci, quel que soit le niveau."""
        suite = []
        for enfant in self.enfants:
            suite.append(enfant)
            suite.extend(enfant.descendants)
        return suite

    @property
    def enfants_actifs(self):
        return [e for e in self.enfants if e.actif]

    @property
    def produits_visibles(self):
        return [p for p in self.produits if p.actif]

    @property
    def produits_avec_descendants(self):
        """Les produits de la categorie et de tout ce qui se trouve dessous.

        C'est ce qu'attend un client qui clique sur « BOSCH » : il veut voir
        les fraises droites aussi, pas une page vide.
        """
        vus, resultat = set(), []
        for categorie in [self] + self.descendants:
            for produit in categorie.produits_visibles:
                if produit.id not in vus:
                    vus.add(produit.id)
                    resultat.append(produit)
        return resultat

    @property
    def nb_produits_total(self):
        """Une categorie parente compte aussi les produits de ses descendants."""
        return len(self.produits_avec_descendants)
    @property
    def valeur_stock(self):
        """Valeur marchande, sous-categories comprises.

        Sans les descendants, une categorie qui ne sert que de rayon
        affichait zero alors qu'elle abrite tout le stock.
        """
        return round(sum((p.prix_affiche or 0) * (p.stock or 0)
                         for p in self.produits_avec_descendants), 3)

    @property
    def unites_en_stock(self):
        return sum((p.stock or 0) for p in self.produits_avec_descendants)

class Produit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    # Nom arabe : vide, on retombe sur le francais (voir intitule()).
    nom_ar = db.Column(db.String(200))
    reference = db.Column(db.String(80), unique=True)
    description = db.Column(db.Text)
    prix = db.Column(db.Float, nullable=False, default=0)
    prix_promo = db.Column(db.Float)
    cout = db.Column(db.Float, default=0)
    # Livraison : vide = on applique les frais generaux de la boutique.
    prix_livraison = db.Column(db.Float)
    cout_livraison = db.Column(db.Float)
    # Stock : seuil d'alerte propre au produit, vide = seuil general.
    seuil_alerte = db.Column(db.Integer)
    stock_entrant = db.Column(db.Integer, default=0)
    stock_abime = db.Column(db.Integer, default=0)
    vente_en_rupture = db.Column(db.Boolean, default=False)
    # Remise par quantite : a partir de N articles, X %% ou X TND de moins.
    lot_quantite = db.Column(db.Integer)
    lot_type = db.Column(db.String(20), default="pourcentage")
    lot_valeur = db.Column(db.Float, default=0)
    # Referencement
    slug = db.Column(db.String(220))
    meta_titre = db.Column(db.String(200))
    meta_description = db.Column(db.String(320))
    produits_lies = db.Column(db.Text)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(255))
    # Demonstration : un fichier televerse, ou un lien YouTube / Facebook / TikTok.
    video = db.Column(db.String(255))
    video_url = db.Column(db.String(500))
    # Format vertical impose : certaines adresses ne le laissent pas deviner.
    video_verticale = db.Column(db.Boolean, default=False)
    couleur = db.Column(db.String(80))
    # Cotes des fraises et meches : ce sur quoi le client cherche vraiment.
    queue_mm = db.Column(db.Float)
    coupe_mm = db.Column(db.Float)
    longueur_mm = db.Column(db.Float)   # longueur de coupe utile
    dimensions = db.Column(db.String(120))
    actif = db.Column(db.Boolean, default=True)
    vedette = db.Column(db.Boolean, default=False)
    offre_panier = db.Column(db.Boolean, default=False)
    date_maj_stock = db.Column(db.DateTime, default=datetime.utcnow)
    ordre = db.Column(db.Integer, default=0)
    categorie_id = db.Column(db.Integer, db.ForeignKey("categorie.id"))
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    @property
    def prix_affiche(self): return self.prix_promo if self.prix_promo else self.prix
    @property
    def galerie(self):
        """Toutes les photos, la principale en tete."""
        photos = [self.image] if self.image else []
        photos += [i.fichier for i in self.images_sup
                   if i.fichier and i.fichier != self.image]
        return photos
    @property
    def en_rupture(self):
        """Avec variantes, c'est leur somme qui compte.

        Sans cela, une fiche dont les variantes sont pleines mais dont le
        champ « stock » est reste a zero s'affiche en rupture et cache le
        formulaire d'achat, donc aussi le choix des options.
        """
        return (self.stock_total or 0) <= 0
    @property
    def commandable(self):
        """En rupture, le produit reste vendable si la precommande est autorisee."""
        return self.actif and (not self.en_rupture or bool(self.vente_en_rupture))
    @property
    def marge_unitaire(self):
        return round((self.prix_affiche or 0) - (self.cout or 0), 3)
    @property
    def taux_marge(self):
        prix = self.prix_affiche or 0
        return round(self.marge_unitaire / prix * 100, 1) if prix else 0
    @property
    def ids_lies(self):
        try:
            return [int(x) for x in json.loads(self.produits_lies or "[]")]
        except (ValueError, TypeError):
            return []
    @property
    def video_est_verticale(self):
        """Vrai si la video doit s'afficher en portrait."""
        if self.video_verticale:
            return True
        lien = self.video_url or ""
        return ("tiktok" in lien or "/shorts/" in lien
                or "/reel/" in lien or "/reels/" in lien)

    @property
    def a_variantes(self):
        return bool(self.options) and bool(self.variantes)
    @property
    def stock_total(self):
        """Avec variantes, le stock vendable est la somme des combinaisons."""
        if self.a_variantes:
            return sum(v.stock or 0 for v in self.variantes)
        return self.stock or 0
    def prix_par_quantite(self, quantite, prix_de_base=None):
        """Prix unitaire applicable pour cette quantite, selon les paliers."""
        base = prix_de_base if prix_de_base is not None else (self.prix_affiche or 0)
        applicable = base
        for palier in self.paliers:
            if quantite >= (palier.quantite_min or 1):
                applicable = palier.prix
        return applicable
    @property
    def a_paliers(self):
        return len(self.paliers) > 0
    @property
    def remise_lot(self):
        """Texte de l'offre par quantite, ou None."""
        if not self.lot_quantite or self.lot_quantite < 2 or not self.lot_valeur:
            return None
        return {"quantite": self.lot_quantite, "type": self.lot_type, "valeur": self.lot_valeur}
    @property
    def avis_publies(self): return [a for a in self.avis if a.approuve]
    @property
    def note_moyenne(self):
        publies = self.avis_publies
        return round(sum(a.note for a in publies) / len(publies), 1) if publies else 0
    @property
    def en_promo(self):
        barre = self.prix_barre_vitrine
        return bool(barre and barre > self.prix_vitrine)

    @property
    def variante_par_defaut(self):
        """Celle qui est proposee d'emblee sur la fiche."""
        for v in self.variantes:
            if v.par_defaut:
                return v
        return self.variantes[0] if self.variantes else None

    @property
    def prix_vitrine(self):
        """Prix montre tant que le client n'a rien choisi.

        Avec des variantes, c'est celui de la variante par defaut : sinon la
        boutique annonce un prix qu'aucun choix ne permet d'obtenir.
        """
        variante = self.variante_par_defaut if self.a_variantes else None
        return variante.prix_effectif if variante else self.prix_affiche

    @property
    def prix_barre_vitrine(self):
        """Prix barre correspondant, ou None s'il n'y a pas de promotion."""
        variante = self.variante_par_defaut if self.a_variantes else None
        if variante is not None:
            reference = variante.prix if variante.prix is not None else self.prix
            return reference if reference and reference > variante.prix_effectif else None
        return self.prix if self.prix_promo and self.prix_promo < self.prix else None

class Commande(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(30), unique=True, nullable=False)
    nom_client = db.Column(db.String(150), nullable=False)
    telephone = db.Column(db.String(30), nullable=False)
    gouvernorat = db.Column(db.String(80))
    ville = db.Column(db.String(80))
    adresse = db.Column(db.String(255))
    commentaire = db.Column(db.Text)
    total = db.Column(db.Float, default=0)
    frais_livraison = db.Column(db.Float, default=0)
    statut = db.Column(db.String(30), default="nouvelle")
    mode_paiement = db.Column(db.String(30), default="cod")
    telephone2 = db.Column(db.String(40))
    email = db.Column(db.String(150))
    note_privee = db.Column(db.Text)      # visible seulement dans l'administration
    # Corbeille : une commande supprimee est mise de cote, pas effacee.
    # Une suppression accidentelle reste ainsi rattrapable.
    supprimee_le = db.Column(db.DateTime)
    # Date de la derniere impression : permet de ne pas reimprimer deux fois.
    imprimee_le = db.Column(db.DateTime)
    transporteur = db.Column(db.String(80))
    numero_suivi = db.Column(db.String(80))
    lien_bordereau = db.Column(db.String(500))
    # Transporteur qui a emis le bordereau ci-dessus : changer de
    # livreur rend l'etiquette precedente caduque.
    transporteur_bordereau = db.Column(db.String(80))
    code_promo_utilise = db.Column(db.String(50))
    event_id_purchase = db.Column(db.String(60))
    utm_source = db.Column(db.String(120))
    utm_medium = db.Column(db.String(120))
    utm_campagne = db.Column(db.String(200))
    utm_adset = db.Column(db.String(200))
    utm_annonce = db.Column(db.String(200))
    numero_facture = db.Column(db.String(40), unique=True)
    date_facture = db.Column(db.DateTime)
    montant_reduction = db.Column(db.Float, default=0)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    lignes = db.relationship("LigneCommande", backref="commande", lazy=True, cascade="all, delete-orphan")

class LigneCommande(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    commande_id = db.Column(db.Integer, db.ForeignKey("commande.id"))
    produit_id = db.Column(db.Integer, db.ForeignKey("produit.id"))
    nom_produit = db.Column(db.String(200))
    prix_unitaire = db.Column(db.Float)
    cout_unitaire = db.Column(db.Float, default=0)
    quantite = db.Column(db.Integer, default=1)
    produit = db.relationship("Produit")

class HistoriqueCommande(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    commande_id = db.Column(db.Integer, db.ForeignKey("commande.id"))
    ancien_statut = db.Column(db.String(30))
    nouveau_statut = db.Column(db.String(30))
    nom_utilisateur = db.Column(db.String(120))
    date_evenement = db.Column(db.DateTime, default=datetime.utcnow)
    commande = db.relationship("Commande", backref="historique")

class CodePromo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    type_reduction = db.Column(db.String(20), default="pourcentage")
    valeur = db.Column(db.Float, nullable=False, default=0)
    montant_minimum = db.Column(db.Float, default=0)
    date_debut = db.Column(db.DateTime)
    date_fin = db.Column(db.DateTime)
    utilisation_max = db.Column(db.Integer, default=0)
    utilisation_actuelle = db.Column(db.Integer, default=0)
    actif = db.Column(db.Boolean, default=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    def est_valide(self, montant):
        maintenant = datetime.utcnow()
        if not self.actif: return False, "Ce code promo n'est plus actif."
        if self.date_debut and maintenant < self.date_debut: return False, "Ce code promo n'est pas encore actif."
        if self.date_fin and maintenant > self.date_fin: return False, "Ce code promo a expire."
        if self.utilisation_max and self.utilisation_actuelle >= self.utilisation_max: return False, "Limite d'utilisation atteinte."
        if montant < self.montant_minimum: return False, f"Commande minimum de {self.montant_minimum:.2f} TND requise."
        return True, ""
    def calculer_reduction(self, montant):
        if self.type_reduction == "pourcentage": return round(montant * self.valeur / 100, 2)
        return min(round(self.valeur, 2), montant)

class OptionProduit(db.Model):
    """Un critere de choix : Couleur, Taille, Configuration..."""
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("produit.id"))
    nom = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(20), default="texte")   # texte | couleur | image
    ordre = db.Column(db.Integer, default=0)
    produit = db.relationship("Produit", backref=db.backref(
        "options", cascade="all, delete-orphan", order_by="OptionProduit.ordre"))


class ValeurOption(db.Model):
    """Une valeur possible : Rouge, 35 mm, Avec meche..."""
    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey("option_produit.id"))
    valeur = db.Column(db.String(160), nullable=False)
    couleur_hex = db.Column(db.String(20))
    image = db.Column(db.String(255))
    ordre = db.Column(db.Integer, default=0)
    option = db.relationship("OptionProduit", backref=db.backref(
        "valeurs", cascade="all, delete-orphan", order_by="ValeurOption.ordre"))


class VarianteProduit(db.Model):
    """Une combinaison de valeurs, avec son propre prix et son propre stock."""
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("produit.id"))
    combinaison = db.Column(db.Text)          # JSON : ["Rouge", "35 mm"]
    reference = db.Column(db.String(80))
    prix = db.Column(db.Float)                # vide = prix du produit
    prix_promo = db.Column(db.Float)
    cout = db.Column(db.Float)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(255))
    par_defaut = db.Column(db.Boolean, default=False)
    produit = db.relationship("Produit", backref=db.backref(
        "variantes", cascade="all, delete-orphan"))

    @property
    def valeurs(self):
        try:
            return json.loads(self.combinaison or "[]")
        except ValueError:
            return []
    @property
    def libelle(self):
        return " / ".join(self.valeurs)

    @property
    def pour_formulaire(self):
        """Ce que le navigateur doit connaitre pour redessiner sa ligne."""
        return {"cle": self.libelle,
                "reference": self.reference or "",
                "prix": "" if self.prix is None else "%.3f" % self.prix,
                "prix_promo": "" if self.prix_promo is None else "%.3f" % self.prix_promo,
                "cout": "" if self.cout is None else "%.3f" % self.cout,
                "stock": self.stock or 0,
                "image": self.image or "",
                "defaut": bool(self.par_defaut)}
    @property
    def prix_effectif(self):
        base = self.prix if self.prix is not None else (self.produit.prix if self.produit else 0)
        promo = self.prix_promo if self.prix_promo is not None else (
            self.produit.prix_promo if self.produit else None)
        return promo if promo and promo < base else base
    @property
    def cout_effectif(self):
        return self.cout if self.cout is not None else ((self.produit.cout or 0) if self.produit else 0)
    @property
    def en_rupture(self):
        return (self.stock or 0) <= 0


class PalierPrix(db.Model):
    """Prix degressif : a partir de N pieces, le prix unitaire baisse."""
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("produit.id"))
    quantite_min = db.Column(db.Integer, nullable=False, default=1)
    prix = db.Column(db.Float, nullable=False, default=0)
    produit = db.relationship("Produit", backref=db.backref(
        "paliers", cascade="all, delete-orphan", order_by="PalierPrix.quantite_min"))


class LotProduit(db.Model):
    """Un palier d'achat propose sur la fiche : \"Prenez-en 3\"."""
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("produit.id"))
    nom = db.Column(db.String(120), nullable=False)      # "Achetez 2"
    etiquette = db.Column(db.String(160))                # "Economisez 20 DT"
    quantite = db.Column(db.Integer, default=1)
    prix = db.Column(db.Float, nullable=False, default=0)   # prix total du lot
    prix_barre = db.Column(db.Float)
    prix_livraison = db.Column(db.Float)
    image = db.Column(db.String(255))
    couleur_badge = db.Column(db.String(20), default="vert")
    par_defaut = db.Column(db.Boolean, default=False)
    ordre = db.Column(db.Integer, default=0)
    produit = db.relationship("Produit", backref=db.backref(
        "lots", cascade="all, delete-orphan", order_by="LotProduit.ordre"))

    @property
    def prix_unitaire(self):
        return round((self.prix or 0) / self.quantite, 3) if self.quantite else 0
    @property
    def economie(self):
        reference = self.prix_barre or ((self.produit.prix_affiche or 0) * (self.quantite or 1)
                                        if self.produit else 0)
        return round(max(0, reference - (self.prix or 0)), 3)
    @property
    def pourcentage(self):
        reference = self.prix_barre or ((self.produit.prix_affiche or 0) * (self.quantite or 1)
                                        if self.produit else 0)
        return round(self.economie / reference * 100) if reference else 0


class ImageProduit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("produit.id"))
    fichier = db.Column(db.String(255), nullable=False)
    ordre = db.Column(db.Integer, default=0)
    produit = db.relationship("Produit", backref=db.backref(
        "images_sup", cascade="all, delete-orphan", order_by="ImageProduit.ordre"))


class AvisProduit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("produit.id"))
    nom_client = db.Column(db.String(150), nullable=False)
    telephone = db.Column(db.String(30))
    note = db.Column(db.Integer, default=5)
    commentaire = db.Column(db.Text)
    approuve = db.Column(db.Boolean, default=False)
    achat_verifie = db.Column(db.Boolean, default=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    produit = db.relationship("Produit", backref="avis")


class PageStatique(db.Model):
    """Pages d'information : a propos, conditions, retours, confidentialite."""
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    titre_fr = db.Column(db.String(160), nullable=False)
    titre_ar = db.Column(db.String(160))
    contenu_fr = db.Column(db.Text)
    contenu_ar = db.Column(db.Text)
    ordre = db.Column(db.Integer, default=0)
    actif = db.Column(db.Boolean, default=True)
    date_maj = db.Column(db.DateTime, default=datetime.utcnow)

    def titre(self, langue):
        return (self.titre_ar or self.titre_fr) if langue == "ar" else self.titre_fr
    def contenu(self, langue):
        return (self.contenu_ar or self.contenu_fr) if langue == "ar" else self.contenu_fr


class Transporteur(db.Model):
    """Un transporteur utilisable pour expedier les commandes."""
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(80), nullable=False, unique=True)
    actif = db.Column(db.Boolean, default=True)
    # Lien de suivi public : {code} est remplace par le numero de suivi.
    url_suivi = db.Column(db.String(300))
    logo = db.Column(db.String(255))
    # Jeton d'API, quand le transporteur en fournit une.
    jeton_api = db.Column(db.String(300))
    # Les autres identifiants, propres a chaque transporteur (JSON).
    config = db.Column(db.Text)
    ordre = db.Column(db.Integer, default=0)

    @property
    def reglages(self):
        """Identifiants enregistres, sous forme de dictionnaire."""
        try:
            return json.loads(self.config) if self.config else {}
        except ValueError:
            return {}

    def enregistrer_reglages(self, valeurs):
        self.config = json.dumps(valeurs, ensure_ascii=False)

    @property
    def schema(self):
        """Description des champs a remplir pour ce transporteur."""
        return CHAMPS_TRANSPORTEUR.get(self.nom, CHAMPS_TRANSPORTEUR["_defaut"])

    def valeur(self, champ):
        """Valeur d'un champ : la cle d'API garde sa colonne dediee."""
        if champ == "jeton_api":
            return self.jeton_api or ""
        return self.reglages.get(champ, "")

    @property
    def champs_manquants(self):
        """Champs obligatoires encore vides."""
        manquants = []
        for groupe in self.schema:
            for champ in groupe["champs"]:
                if champ.get("requis") and not self.valeur(champ["nom"]):
                    manquants.append(champ["libelle"])
        return manquants

    @property
    def est_configure(self):
        """Rien d'obligatoire ne manque, et quelque chose a bien ete saisi.

        Un transporteur sans champ obligatoire ne doit pas s'annoncer pret
        alors que sa fiche est entierement vide.
        """
        if self.champs_manquants:
            return False
        return any(self.valeur(c["nom"])
                   for g in self.schema for c in g["champs"])

    @property
    def sait_etiqueter(self):
        """Vrai si on sait vraiment lui demander ses bordereaux."""
        return self.nom in TRANSPORTEURS_AVEC_API and self.est_configure

    @property
    def initiales(self):
        """Deux lettres tirees du nom, pour la pastille de repli."""
        mots = [m for m in (self.nom or "?").replace("-", " ").split() if m]
        if len(mots) >= 2:
            return (mots[0][0] + mots[1][0]).upper()
        return (mots[0][:2] if mots else "?").upper()

    @property
    def couleur(self):
        """Couleur stable deduite du nom : chaque transporteur garde la sienne."""
        palette = ["#1F7A4D", "#1769E0", "#C81D35", "#7A4DBE", "#C2610A",
                   "#0E7490", "#B4237A", "#4D5B7A"]
        # Couleur donnee par le rang, pas par un hachage du nom : avec huit
        # teintes et une poignee de transporteurs, un hachage produisait des
        # doublons. Le rang garantit des couleurs distinctes.
        rang = self.ordre if self.ordre is not None else (self.id or 0)
        return palette[rang % len(palette)]

    def lien_suivi(self, code):
        if not code or not self.url_suivi or "{code}" not in self.url_suivi:
            return None
        return self.url_suivi.replace("{code}", str(code).strip())


# Champs de configuration, transporteur par transporteur. Ils reprennent ce
# que chaque societe demande reellement : inutile de reclamer un numero de
# compte Aramex a Navex, qui ne travaille qu'avec une cle unique.
OUI_NON = [("", "--"), ("oui", "Oui"), ("non", "Non")]

CHAMPS_TRANSPORTEUR = {
    "First Delivery": [
        {"titre": "Cle", "champs": [
            {"nom": "jeton_api", "libelle": "Cle d'API", "type": "secret", "requis": True,
             "aide": "Fournie par First Delivery dans ton espace partenaire."},
        ]},
        {"titre": "Cout", "champs": [
            {"nom": "cout_livraison", "libelle": "Cout de livraison", "type": "nombre"},
            {"nom": "cout_retour", "libelle": "Cout de retour", "type": "nombre"},
        ]},
    ],
    "Aramex": [
        {"titre": "Cle", "champs": [
            {"nom": "utilisateur", "libelle": "Username", "requis": True},
            {"nom": "mot_de_passe", "libelle": "Password", "type": "secret", "requis": True},
            {"nom": "code_compte", "libelle": "Account Pin", "type": "secret", "requis": True},
            {"nom": "numero_compte", "libelle": "Account Number", "requis": True},
        ]},
        {"titre": "Cout", "champs": [
            {"nom": "cout_livraison", "libelle": "Cout de livraison", "type": "nombre"},
            {"nom": "cout_retour", "libelle": "Cout de retour", "type": "nombre"},
        ]},
        {"titre": "Etiquette", "champs": [
            {"nom": "nom_boutique", "libelle": "Nom de la boutique"},
            {"nom": "tel_boutique", "libelle": "Telephone de la boutique"},
            {"nom": "ville_boutique", "libelle": "Ville de la boutique", "type": "gouvernorat"},
            {"nom": "adresse_enlevement", "libelle": "Adresse d'enlevement", "requis": True},
            {"nom": "matricule_tva", "libelle": "Matricule fiscal"},
        ]},
    ],
    "Navex": [
        {"titre": "Cle", "champs": [
            {"nom": "cle", "libelle": "Cle", "type": "secret", "requis": True},
        ]},
        {"titre": "Cout", "champs": [
            {"nom": "cout_livraison", "libelle": "Cout de livraison", "type": "nombre"},
            {"nom": "cout_retour", "libelle": "Cout de retour", "type": "nombre"},
        ]},
        {"titre": "Etiquette", "champs": [
            {"nom": "nom_boutique", "libelle": "Nom de la boutique"},
            {"nom": "tel_boutique", "libelle": "Telephone de la boutique"},
            {"nom": "adresse_boutique", "libelle": "Adresse de la boutique"},
            {"nom": "colis_ouvrable", "libelle": "Colis ouvrable a la livraison",
             "type": "choix", "options": OUI_NON},
            {"nom": "matricule_tva", "libelle": "Matricule fiscal"},
        ]},
    ],
    "Jetpack": [
        {"titre": "Cle", "champs": [
            {"nom": "jeton_commande", "libelle": "Jeton de creation de commande",
             "type": "secret", "requis": True},
            {"nom": "jeton_suivi", "libelle": "Jeton de suivi", "type": "secret"},
        ]},
        {"titre": "Cout", "champs": [
            {"nom": "cout_livraison", "libelle": "Cout de livraison", "type": "nombre"},
            {"nom": "cout_retour", "libelle": "Cout de retour", "type": "nombre"},
        ]},
        {"titre": "Etiquette", "champs": [
            {"nom": "colis_ouvrable", "libelle": "Colis ouvrable a la livraison",
             "type": "choix", "options": OUI_NON},
            {"nom": "fragile", "libelle": "Colis fragile", "type": "choix", "options": OUI_NON},
            {"nom": "nom_boutique", "libelle": "Nom de la boutique"},
            {"nom": "tel_boutique", "libelle": "Telephone de la boutique"},
            {"nom": "adresse_boutique", "libelle": "Adresse de la boutique"},
            {"nom": "matricule_tva", "libelle": "Matricule fiscal"},
        ]},
    ],
    "_defaut": [
        {"titre": "Cle", "champs": [
            {"nom": "jeton_api", "libelle": "Cle d'API", "type": "secret",
             "aide": "Si le transporteur en fournit une."},
        ]},
        {"titre": "Cout", "champs": [
            {"nom": "cout_livraison", "libelle": "Cout de livraison", "type": "nombre"},
            {"nom": "cout_retour", "libelle": "Cout de retour", "type": "nombre"},
        ]},
        {"titre": "Etiquette", "champs": [
            {"nom": "nom_boutique", "libelle": "Nom de la boutique"},
            {"nom": "tel_boutique", "libelle": "Telephone de la boutique"},
            {"nom": "adresse_boutique", "libelle": "Adresse de la boutique"},
        ]},
    ],
}


def transporteurs_actifs():
    return Transporteur.query.filter_by(actif=True).order_by(Transporteur.ordre,
                                                             Transporteur.nom).all()


def transporteur_par_nom(nom):
    return Transporteur.query.filter_by(nom=(nom or "").strip()).first() if nom else None


def lien_de_suivi(commande):
    """Lien public de suivi d'une commande, ou None si on ne l'a pas."""
    t = transporteur_par_nom(commande.transporteur)
    return t.lien_suivi(commande.numero_suivi) if t else None


class PanierAbandonne(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_client = db.Column(db.String(150))
    telephone = db.Column(db.String(30))
    telephone_normalise = db.Column(db.String(30), index=True)
    gouvernorat = db.Column(db.String(80))
    ville = db.Column(db.String(80))
    contenu = db.Column(db.Text)
    total = db.Column(db.Float, default=0)
    statut = db.Column(db.String(20), default="actif")
    nb_relances = db.Column(db.Integer, default=0)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_maj = db.Column(db.DateTime, default=datetime.utcnow)
    date_relance = db.Column(db.DateTime)
    commande_numero = db.Column(db.String(30))


class ParametreBoutique(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_boutique = db.Column(db.String(150), default="Maison des Garnitures")
    telephone = db.Column(db.String(30), default="")
    whatsapp = db.Column(db.String(30), default="")
    adresse = db.Column(db.String(255), default="")
    facebook = db.Column(db.String(255), default="")
    instagram = db.Column(db.String(255), default="")
    tiktok = db.Column(db.String(255), default="")
    email = db.Column(db.String(150), default="")
    frais_livraison_defaut = db.Column(db.Float, default=8.0)
    montant_livraison_gratuite = db.Column(db.Float, default=150.0)
    pixel_meta_id = db.Column(db.String(80), default="")
    meta_capi_token = db.Column(db.Text, default="")
    meta_test_event_code = db.Column(db.String(50), default="")
    # Mesure d'audience : un champ vide = le service n'est pas charge du tout.
    google_analytics_id = db.Column(db.String(40), default="")
    google_verification = db.Column(db.String(120), default="")
    # Meta delivre un code par domaine : celui de la vitrine Converty ne
    # vaudra pas pour le domaine propre de la boutique.
    meta_domain_verification = db.Column(db.String(120), default="")
    clarity_id = db.Column(db.String(40), default="")
    texte_bandeau = db.Column(db.String(255), default="Livraison partout en Tunisie - Paiement a la livraison")
    modele_whatsapp_confirmation = db.Column(db.Text, default="")
    modele_whatsapp_expedition = db.Column(db.Text, default="")
    modele_whatsapp_relance = db.Column(db.Text, default="")
    raison_sociale = db.Column(db.String(200), default="")
    matricule_fiscal = db.Column(db.String(60), default="")
    registre_commerce = db.Column(db.String(60), default="")
    taux_tva = db.Column(db.Float, default=19.0)
    timbre_fiscal = db.Column(db.Float, default=1.0)
    seuil_alerte_stock = db.Column(db.Integer, default=1)

# ---------------------------------------------------------------------------
# TRACKING META (Pixel navigateur + Conversions API serveur)
#
# Chaque evenement part deux fois : une fois depuis le navigateur (Pixel) et
# une fois depuis le serveur (Conversions API). Les deux portent le meme
# event_id, donc Meta les fusionne au lieu de compter deux conversions.
# L'envoi serveur est indispensable : bloqueurs de pub et iOS font perdre
# 30 a 50 % des evenements navigateur.
# ---------------------------------------------------------------------------

META_API_VERSION = "v21.0"


def config_meta():
    """Retourne (pixel_id, token, code_test) ou (None, None, None) si non configure."""
    params = ParametreBoutique.query.first()
    if not params or not params.pixel_meta_id:
        return None, None, None
    return params.pixel_meta_id, (params.meta_capi_token or ""), (params.meta_test_event_code or "")


def hacher(valeur):
    """Meta exige les donnees personnelles en SHA-256 minuscule, jamais en clair."""
    valeur = (valeur or "").strip().lower()
    if not valeur:
        return None
    return hashlib.sha256(valeur.encode("utf-8")).hexdigest()


def telephone_e164(numero):
    """20123456 -> 21620123456 (format attendu par Meta, sans le +)."""
    chiffres = re.sub(r"[^0-9]", "", numero or "")
    if not chiffres:
        return None
    if chiffres.startswith("216"):
        return chiffres
    return "216" + chiffres[-8:] if len(chiffres) >= 8 else None


def nouvel_event_id():
    return uuid.uuid4().hex


def donnees_client_meta(commande=None):
    """Assemble les identifiants de correspondance : plus il y en a, mieux Meta attribue."""
    donnees = {
        "client_ip_address": request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip(),
        "client_user_agent": request.headers.get("User-Agent", ""),
    }
    # Cookies deposes par le Pixel : ils relient la visite au clic publicitaire.
    poses = cookies_meta()
    fbp = request.cookies.get("_fbp") or poses.get("_fbp")
    fbc = request.cookies.get("_fbc") or poses.get("_fbc")
    if fbp:
        donnees["fbp"] = fbp
    if fbc:
        donnees["fbc"] = fbc

    if commande is not None:
        courriel = hacher(commande.email)
        if courriel:
            donnees["em"] = [courriel]
        telephone = telephone_e164(commande.telephone)
        if telephone:
            empreinte = hashlib.sha256(telephone.encode("utf-8")).hexdigest()
            donnees["ph"] = [empreinte]
            # Chez un marchand en paiement a la livraison, le telephone est la
            # seule cle qui suit la personne d'une commande a l'autre : c'est
            # donc lui qui sert d'identifiant externe.
            donnees["external_id"] = [empreinte]
        morceaux = (commande.nom_client or "").split()
        if morceaux:
            prenom = hacher(morceaux[0])
            if prenom:
                donnees["fn"] = [prenom]
            if len(morceaux) > 1:
                nom = hacher(" ".join(morceaux[1:]))
                if nom:
                    donnees["ln"] = [nom]
        ville = hacher(commande.ville)
        if ville:
            donnees["ct"] = [ville]
        region = hacher(commande.gouvernorat)
        if region:
            donnees["st"] = [region]
        donnees["country"] = [hacher("tn")]

    return donnees


def _poster_evenement_meta(pixel_id, token, charge):
    try:
        reponse = requests.post(
            "https://graph.facebook.com/%s/%s/events" % (META_API_VERSION, pixel_id),
            json=charge, timeout=10)
        if reponse.status_code >= 400:
            app.logger.warning("Conversions API refuse l'evenement : %s", reponse.text[:400])
    except Exception as erreur:
        app.logger.warning("Conversions API injoignable : %s", erreur)


def envoyer_evenement_meta(nom_evenement, event_id, url_source, donnees_client, donnees_custom=None):
    """Envoi serveur, en tache de fond : le client ne doit jamais attendre Meta."""
    pixel_id, token, code_test = config_meta()
    if not pixel_id or not token:
        return

    evenement = {
        "event_name": nom_evenement,
        "event_time": int(time.time()),
        "event_id": event_id,
        "event_source_url": url_source,
        "action_source": "website",
        "user_data": donnees_client,
    }
    if donnees_custom:
        evenement["custom_data"] = donnees_custom

    charge = {"data": [evenement], "access_token": token}
    if code_test:
        charge["test_event_code"] = code_test

    threading.Thread(target=_poster_evenement_meta, args=(pixel_id, token, charge), daemon=True).start()


def contenus_meta(articles):
    """articles = [{"produit": p, "quantite": n}, ...] -> format attendu par Meta."""
    return [{
        "id": a["produit"].reference or str(a["produit"].id),
        "quantity": a["quantite"],
        "item_price": round(a["produit"].prix_affiche, 3),
    } for a in articles]


def generer_numero_commande():
    """MDG + horodatage + 4 caracteres aleatoires. On verifie quand meme en base."""
    for _ in range(12):
        candidat = "MDG%s%s" % (datetime.utcnow().strftime("%y%m%d%H%M%S"),
                                uuid.uuid4().hex[:4].upper())
        if not Commande.query.filter_by(numero=candidat).first():
            return candidat
    return "MDG" + uuid.uuid4().hex[:14].upper()


def telephone_valide(numero):
    """Un numero tunisien : 8 chiffres, avec ou sans indicatif +216."""
    chiffres = re.sub(r"[^0-9]", "", numero or "")
    if chiffres.startswith("216"):
        chiffres = chiffres[3:]
    return len(chiffres) == 8 and chiffres[0] in "2459"


def utilisateur_courant():
    uid = session.get("user_id")
    return Utilisateur.query.get(uid) if uid else None

# Pages encore ouvertes a qui traine un mot de passe provisoire : celle qui
# le remplace, et la sortie. Tout le reste attend.
PAGES_HORS_BLOCAGE = ("admin_changer_mot_de_passe", "admin_logout", "static")


def connexion_requise(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = utilisateur_courant()
        if not u: return redirect(url_for("admin_login"))
        # Un mot de passe provisoire a circule en clair (WhatsApp, oral) : tant
        # qu'il n'est pas remplace, le compte n'est protege par rien.
        if u.doit_changer_mdp and request.endpoint not in PAGES_HORS_BLOCAGE:
            return redirect(url_for("admin_changer_mot_de_passe"))
        return f(*args, **kwargs)
    return wrapper

# Rubriques du menu et actions possibles sur chacune. Ce tableau sert a la
# fois a dessiner la grille des droits et a controler l'acces aux pages :
# une seule source, donc pas de case cochee sans effet reel.
ACTIONS = [("lire", "Lire"), ("creer", "Creer"),
           ("modifier", "Modifier"), ("supprimer", "Supprimer")]

RUBRIQUES = [
    ("commandes", "Commandes", ["lire", "creer", "modifier", "supprimer"]),
    ("paniers", "Paniers abandonnes", ["lire"]),
    ("produits", "Produits", ["lire", "creer", "modifier", "supprimer"]),
    ("categories", "Categories", ["lire", "creer", "modifier", "supprimer"]),
    ("promotions", "Codes promo", ["lire", "creer", "modifier", "supprimer"]),
    ("avis", "Avis clients", ["lire", "modifier", "supprimer"]),
    ("statistiques", "Statistiques", ["lire"]),
    ("equipe", "Equipe", ["lire", "creer", "modifier", "supprimer"]),
    ("boutique", "Boutique", ["lire", "modifier"]),
    ("transporteurs", "Integrations", ["lire", "modifier"]),
]

# Roles predefinis : un point de depart, que la grille peut ensuite ajuster.
DROITS_PAR_ROLE = {
    "proprietaire": {cle: list(actions) for cle, _, actions in RUBRIQUES},
    "commandes": {
        "commandes": ["lire", "creer", "modifier"],
        "paniers": ["lire"],
        "produits": ["lire"],
        "categories": ["lire"],
        "avis": ["lire", "modifier"],
        "statistiques": ["lire"],
    },
    "livraison": {
        "commandes": ["lire", "modifier"],
        "transporteurs": ["lire"],
        "statistiques": ["lire"],
    },
}

# Prefixe d'endpoint -> rubrique concernee. Le premier qui correspond gagne,
# donc les prefixes les plus longs viennent en tete.
RUBRIQUE_DES_PAGES = [
    ("admin_paniers", "paniers"),
    ("admin_produits_import", "produits"),
    ("admin_produit", "produits"),
    ("admin_photo", "produits"),
    ("admin_options", "produits"),
    ("admin_variantes", "produits"),
    ("admin_paliers", "produits"),
    ("admin_lots", "produits"),
    ("admin_categorie", "categories"),
    ("admin_promotion", "promotions"),
    ("admin_commande", "commandes"),
    ("admin_bon_livraison", "commandes"),
    ("admin_bons_groupes", "commandes"),
    ("admin_bordereau", "commandes"),
    ("admin_imprimer", "commandes"),
    ("admin_expedier", "commandes"),
    ("admin_verifier_statut", "commandes"),
    ("admin_avis", "avis"),
    ("admin_stat", "statistiques"),
    ("admin_utilisateur", "equipe"),
    ("admin_transporteur", "transporteurs"),
    ("admin_tester_first", "transporteurs"),
    ("admin_parametres", "boutique"),
    ("admin_page", "boutique"),
]

MOTS_SUPPRESSION = ("supprimer", "effacer")
MOTS_CREATION = ("nouveau", "nouvelle", "ajouter", "import")


def droit_exige(endpoint, methode):
    """Rubrique et action exigees par une page, ou None si elle est libre."""
    if not endpoint or not endpoint.startswith("admin_"):
        return None
    for prefixe, rubrique in RUBRIQUE_DES_PAGES:
        if endpoint.startswith(prefixe):
            break
    else:
        return None

    if methode in ("GET", "HEAD"):
        return rubrique, "lire"
    if any(mot in endpoint for mot in MOTS_SUPPRESSION):
        return rubrique, "supprimer"
    if any(mot in endpoint for mot in MOTS_CREATION):
        return rubrique, "creer"
    return rubrique, "modifier"


@app.before_request
def verifier_les_droits():
    """Ferme une page a qui n'a pas le droit correspondant dans sa grille.

    Le controle se fait ici plutot que route par route : une page ajoutee plus
    tard est couverte d'office par le prefixe de son nom.
    """
    exige = droit_exige(request.endpoint, request.method)
    if not exige:
        return None
    utilisateur = utilisateur_courant()
    if utilisateur is None:
        return None  # la page redirigera elle-meme vers la connexion
    if not utilisateur.peut(*exige):
        abort(403)
    return None


def roles_requis(*roles):
    """Filtre par role, sauf la ou la grille des droits a deja tranche.

    Les pages couvertes par « droit_exige » sont controlees en amont, case par
    case : leur imposer en plus un role fige rendrait la grille sans effet.
    """
    def decorateur(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            u = utilisateur_courant()
            if not u: return redirect(url_for("admin_login"))
            if droit_exige(request.endpoint, request.method) is None and u.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorateur

@db.event.listens_for(Produit.stock, "set")
def _horodater_mouvement_stock(produit, valeur, ancienne, initiateur):
    """Se declenche sur toutes les voies : commande, annulation, admin, import."""
    if ancienne is not None and valeur != ancienne:
        produit.date_maj_stock = datetime.utcnow()


def alertes_stock():
    """Produits actifs dont le stock est tombe au niveau d'alerte."""
    params = ParametreBoutique.query.first()
    seuil = params.seuil_alerte_stock if params and params.seuil_alerte_stock is not None else 1
    produits = [p for p in Produit.query.filter(Produit.actif == True).all()
                if (p.stock or 0) <= (p.seuil_alerte if p.seuil_alerte is not None else seuil)]
    produits.sort(key=lambda p: ((p.stock or 0), p.nom or ""))
    return produits, seuil


@app.route("/admin/alertes/lues", methods=["POST"])
@connexion_requise
def admin_alertes_lues():
    u = utilisateur_courant()
    u.alertes_lues_le = datetime.utcnow()
    db.session.commit()
    return redirect(request.referrer or url_for("admin_dashboard"))


# Meta remplace ces variables dans l'URL de destination si tu ajoutes les
# "parametres d'URL" a tes publicites. Le clic garde ainsi sa provenance
# jusqu'a la commande, ce qui permet de savoir quelle annonce fait vendre.
PARAMETRES_ATTRIBUTION = {
    "utm_source": "utm_source",
    "utm_medium": "utm_medium",
    "utm_campaign": "utm_campagne",
    "utm_content": "utm_adset",
    "utm_term": "utm_annonce",
    "campaign_name": "utm_campagne",
    "adset_name": "utm_adset",
    "ad_name": "utm_annonce",
}


# Meta relie une visite a un clic publicitaire par deux cookies que le Pixel
# pose en JavaScript. Quand le Pixel est bloque - ou simplement pas encore
# execute, ce qui est le cas au tout premier affichage - ils n'existent pas,
# et l'evenement serveur part sans le lien vers la publicite. Meta le signale
# dans ses diagnostics : « faible couverture de fbc via l'API Conversions ».
# On les pose donc nous-memes, au format documente : fb.1.<horodatage ms>.<valeur>.
DUREE_COOKIES_META = 90 * 24 * 3600


def fbc_depuis_le_clic():
    """Reconstruit _fbc a partir du fbclid laisse par la publicite."""
    fbclid = (request.args.get("fbclid") or "").strip()[:400]
    return "fb.1.%d.%s" % (int(time.time() * 1000), fbclid) if fbclid else None


def cookies_meta():
    """Ceux qui manquent et que le serveur doit poser sur cette reponse."""
    return getattr(g, "_cookies_meta", None) or {}


@app.after_request
def poser_cookies_meta(reponse):
    for nom, valeur in cookies_meta().items():
        # Lisible en JavaScript : le Pixel doit retrouver la meme valeur que
        # le serveur, sans quoi les deux envois ne se rejoindraient pas.
        reponse.set_cookie(nom, valeur, max_age=DUREE_COOKIES_META,
                           samesite="Lax", secure=EN_PRODUCTION, httponly=False)
    return reponse


@app.before_request
def memoriser_attribution():
    """La provenance est retenue au premier clic, pas au dernier."""
    if request.path.startswith(("/admin", "/static")):
        return
    capture = session.get("attribution") or {}
    nouveau = False
    for parametre, champ in PARAMETRES_ATTRIBUTION.items():
        valeur = (request.args.get(parametre) or "").strip()[:200]
        if valeur and not capture.get(champ):
            capture[champ] = valeur
            nouveau = True
    # Un clic depuis Facebook laisse fbclid meme sans parametres d'URL.
    if not capture.get("utm_source") and request.args.get("fbclid"):
        capture["utm_source"] = "facebook"
        nouveau = True
    if nouveau:
        session["attribution"] = capture

    manquants = {}
    if not request.cookies.get("_fbc"):
        depuis_clic = fbc_depuis_le_clic()
        if depuis_clic:
            manquants["_fbc"] = depuis_clic
    if not request.cookies.get("_fbp"):
        manquants["_fbp"] = "fb.1.%d.%d" % (int(time.time() * 1000),
                                            secrets.randbelow(10 ** 10))
    g._cookies_meta = manquants


def langue_courante():
    langue = session.get("langue")
    if langue in LANGUES:
        return langue
    # A defaut, on suit la langue du navigateur : beaucoup de clients sont arabophones.
    prefere = request.accept_languages.best_match(list(LANGUES.keys()))
    return prefere or LANGUE_DEFAUT


@app.route("/langue/<code>")
def changer_langue(code):
    if code in LANGUES:
        session["langue"] = code
    return redirect(request.referrer or url_for("accueil"))


def intitule(objet, langue=None):
    """Nom d'un produit ou d'une categorie dans la langue affichee.

    Le francais sert de repli : une fiche sans traduction reste lisible
    plutot que d'afficher un blanc.
    """
    if objet is None:
        return ""
    if (langue or langue_courante()) == "ar":
        return (getattr(objet, "nom_ar", None) or "").strip() or objet.nom
    return objet.nom


# Une fiche porte le badge « Nouveau » si elle est parmi les dernieres
# arrivees ET recente. Sans le plafond, l'import Converty du 28/08 aurait
# marque les 83 fiches d'un coup : un badge que tout le monde porte ne
# signale plus rien.
NOUVEAUTES_MAX = 8
NOUVEAUTES_JOURS = 30


def ids_nouveautes():
    """Identifiants des fiches qui meritent le badge « Nouveau »."""
    depuis = datetime.utcnow() - timedelta(days=NOUVEAUTES_JOURS)
    recentes = (Produit.query.filter(Produit.actif.is_(True),
                                     Produit.date_creation >= depuis)
                .order_by(Produit.date_creation.desc())
                .limit(NOUVEAUTES_MAX).all())
    return {p.id for p in recentes}


@app.context_processor
def globales():
    params = ParametreBoutique.query.first()
    nb_articles = sum(e.get("quantite", 0) for e in lire_panier().values())
    # Une categorie sans produit visible donne une page vide : on la masque du
    # menu sans la supprimer, elle reste disponible dans l'admin. Celle qui
    # presente des rayons fait exception : sa page montre ses marques, elle a
    # donc quelque chose a offrir meme avant d'avoir recu son premier article.
    categories_menu = [c for c in Categorie.query.filter_by(parent_id=None, actif=True)
                       .order_by(Categorie.ordre, Categorie.nom).all()
                       if c.nb_produits_total or c.enfants_actifs]
    langue = langue_courante()

    # Les alertes ne concernent que l'administration : on ne les calcule pas
    # sur les pages boutique, qui sont les plus consultees.
    produits_alerte, seuil, non_lues = [], 0, False
    if request.path.startswith("/admin") and utilisateur_courant():
        produits_alerte, seuil = alertes_stock()
        vue_le = utilisateur_courant().alertes_lues_le
        non_lues = bool(produits_alerte) and (
            vue_le is None or any((p.date_maj_stock or datetime.min) > vue_le for p in produits_alerte))

    pages_pied = (PageStatique.query.filter_by(actif=True)
                  .order_by(PageStatique.ordre, PageStatique.id).all())
    return {"parametres": params, "categories_menu": categories_menu, "pages_pied": pages_pied,
            "produits_alerte": produits_alerte, "seuil_alerte": seuil,
            "alertes_non_lues": non_lues,
            "t": lambda cle, **kw: traduire(cle, langue, **kw),
            "intitule": lambda objet: intitule(objet, langue),
            "video_integree": video_integree,
            # Inutile cote administration, ou la liste a ses propres reperes.
            "ids_nouveautes": set() if request.path.startswith("/admin")
                              else ids_nouveautes(),
            "langue": langue, "langues": LANGUES,
            "direction": LANGUES[langue]["direction"], "nb_articles_panier": nb_articles,
            "annee_courante": datetime.now().year, "utilisateur": utilisateur_courant()}

@app.route("/")
def accueil():
    en_rayon = produits_ordonnes()
    return render_template("shop/accueil.html",
                           produits_vedette=[p for p in en_rayon if p.vedette][:8],
                           nouveautes=Produit.query.filter_by(actif=True).order_by(Produit.date_creation.desc()).limit(8).all(),
                           tous_produits=en_rayon[:12],
                           nb_produits=Produit.query.filter_by(actif=True).count(), categories=[c for c in Categorie.query.filter_by(parent_id=None, actif=True)
                                       .order_by(Categorie.ordre, Categorie.nom).all()
                                       if c.nb_produits_total or c.enfants_actifs])

PAR_PAGE = 24

TRIS = {
    # Meme depart que la page Produits de l'administration, jusqu'au
    # departage des ex aequo : une seule liste de reference pour tout le site.
    "defaut":   ("Nos suggestions",
                 lambda q: q.order_by(Produit.ordre, Produit.date_creation.desc())),
    "recent":   ("Nouveautés", lambda q: q.order_by(Produit.date_creation.desc())),
    # On trie sur le prix reellement paye, pas sur le prix barre : sinon un
    # produit en promo se retrouve classe a sa valeur d'avant remise.
    "prix_bas": ("Prix croissant",
                 lambda q: q.order_by(db.func.coalesce(Produit.prix_promo, Produit.prix))),
    "prix_haut": ("Prix décroissant",
                  lambda q: q.order_by(db.func.coalesce(Produit.prix_promo, Produit.prix).desc())),
    "promo":    ("Promotions", lambda q: q.order_by(Produit.prix_promo.is_(None), Produit.ordre)),
}


def correspond_au_texte(produit, terme):
    """Recherche insensible aux accents et a la casse.

    SQLite ne sait pas ignorer les accents : « charniere » ne trouverait pas
    « Charniere » ecrit avec un accent. On compare donc des formes normalisees."""
    cible = sans_accents_simple(terme)
    if not cible:
        return True
    # On cherche dans le nom et la reference seulement : fouiller les
    # descriptions entieres ramenait trop de resultats sans rapport.
    champs = (produit.nom or "", produit.nom_ar or "", produit.reference or "")
    return any(cible in sans_accents_simple(c) for c in champs)


def page_produits(requete, tri=None, terme=None):
    """Decoupe une liste de produits en pages, avec le tri demande."""
    cle = tri if tri in TRIS else "defaut"
    requete = TRIS[cle][1](requete)

    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    if terme:
        # Le filtre texte se fait en memoire : le catalogue reste petit et
        # cela permet d'ignorer les accents, ce que SQLite ne sait pas faire.
        tous = [p for p in requete.all() if correspond_au_texte(p, terme)]
        total = len(tous)
        produits = tous[(page - 1) * PAR_PAGE: page * PAR_PAGE]
    else:
        total = requete.count()
        produits = requete.offset((page - 1) * PAR_PAGE).limit(PAR_PAGE).all()
    return {
        "produits": produits, "page": page, "total": total, "tri": cle, "tris": TRIS,
        "pages": max(1, (total + PAR_PAGE - 1) // PAR_PAGE),
        "reste": max(0, total - page * PAR_PAGE),
    }


@app.route("/page/<slug>")
def voir_page(slug):
    page = PageStatique.query.filter_by(slug=slug, actif=True).first_or_404()
    return render_template("shop/page.html", page=page, langue=langue_courante())


def grouper_par_rayon(articles, masquees=False):
    """Range une liste d'articles par rayon, dans l'ordre de l'arbre.

    Une categorie qui ne sert que d'etage n'apparait pas : seules celles qui
    contiennent vraiment des articles font une section. Cote boutique on saute
    les rayons masques ; cote administration on veut tout voir.

    L'ordre des articles dans chaque section est celui de la liste recue : le
    tri reste la decision de l'appelant.
    """
    par_categorie = {}
    for produit in articles:
        par_categorie.setdefault(produit.categorie_id, []).append(produit)

    groupes = []

    def descendre(categorie):
        lot = par_categorie.pop(categorie.id, None)
        if lot:
            groupes.append({"categorie": categorie,
                            "chemin": categorie.chemin,
                            "produits": lot})
        for enfant in sorted(categorie.enfants, key=lambda c: (c.ordre, c.nom)):
            if masquees or enfant.actif:
                descendre(enfant)

    for racine in (Categorie.query.filter_by(parent_id=None)
                   .order_by(Categorie.ordre, Categorie.nom).all()):
        if masquees or racine.actif:
            descendre(racine)

    # Un article sans rayon, ou range dans un rayon masque, ne doit pas
    # disparaitre de la liste pour autant.
    restants = [p for lot in par_categorie.values() for p in lot]
    if restants:
        groupes.append({"categorie": None, "chemin": [], "produits": restants})
    return groupes


def produits_par_rayon():
    """Les produits en vente, groupes par rayon, pour la boutique.

    Meme tri que la page Produits de l'administration : ce qui est range
    la-bas se retrouve dans le meme ordre en vitrine, y compris quand deux
    articles partagent le meme numero d'ordre.
    """
    return grouper_par_rayon(Produit.query.filter_by(actif=True)
                             .order_by(Produit.ordre, Produit.date_creation.desc())
                             .all())


def produits_ordonnes(limite=None):
    """La meme liste, mise a plat : pour les vitrines en simple grille.

    « ordre » est un numero global, il ne connait pas les rayons : trier
    dessus melange les rayons entre eux. On passe donc par l'arbre, puis on
    deroule, et l'accueil montre le debut de la boutique telle qu'elle est
    rangee.
    """
    liste = [p for groupe in produits_par_rayon() for p in groupe["produits"]]
    return liste[:limite] if limite else liste


@app.route("/produits")
def catalogue():
    """Tous les produits de la boutique, tries et pagines."""
    base = Produit.query.filter(Produit.actif == True)
    tri = request.args.get("tri")
    contexte = page_produits(base, tri)

    # Le bouton « voir plus » recharge seulement la grille, pas toute la page.
    if request.args.get("fragment"):
        return render_template("shop/_grille_paginee.html", **contexte)

    # Sans tri particulier, on suit l'ordre des rayons. Des qu'un tri est
    # demande (prix, nouveautes), le classement prime et la grille redevient
    # une simple liste.
    rayons = produits_par_rayon() if contexte["tri"] == "defaut" else None
    return render_template("shop/catalogue.html", rayons=rayons, **contexte)


@app.route("/categorie/<slug>")
def voir_categorie(slug):
    c = Categorie.query.filter_by(slug=slug).first_or_404()
    if not c.actif:
        abort(404)

    # Tous les niveaux au-dessous : un client qui clique sur « BOSCH » veut
    # voir les fraises droites aussi, pas une page vide.
    ids = [c.id] + [d.id for d in c.descendants if d.actif]
    base = Produit.query.filter(Produit.categorie_id.in_(ids), Produit.actif == True)
    contexte = page_produits(base, request.args.get("tri"))

    if request.args.get("fragment"):
        return render_template("shop/_grille_paginee.html", **contexte)

    # Etage des rayons : on presente les rayons, pas leur contenu en vrac.
    rayons = c.enfants_actifs
    etage_des_rayons = any(e.enfants_actifs for e in rayons)

    return render_template("shop/categorie.html", categorie=c,
                           fil=c.chemin, sous_categories=rayons,
                           masquer_produits=etage_des_rayons, **contexte)

@app.route("/produit/<int:produit_id>")
def voir_produit(produit_id):
    p = Produit.query.get_or_404(produit_id)
    event_id = nouvel_event_id()
    envoyer_evenement_meta("ViewContent", event_id, request.url, donnees_client_meta(), {
        "currency": "TND",
        "value": round(p.prix_affiche, 3),
        "content_type": "product",
        "content_name": p.nom,
        "content_ids": [p.reference or str(p.id)],
    })
    lies = (Produit.query.filter(Produit.id.in_(p.ids_lies), Produit.actif == True).all()
            if p.ids_lies else [])
    if not lies:
        lies = Produit.query.filter(Produit.categorie_id == p.categorie_id,
                                    Produit.id != p.id, Produit.actif == True).limit(4).all()
    params = ParametreBoutique.query.first()
    return render_template("shop/produit.html", produit=p, event_id=event_id,
                           avis=sorted(p.avis_publies, key=lambda a: a.date_creation, reverse=True),
                           produits_associes=lies,
                           gouvernorats_json=GOUVERNORATS_TUNISIE,
                           frais_livraison=(p.prix_livraison if p.prix_livraison is not None
                                            else (params.frais_livraison_defaut if params else 8.0)),
                           seuil_gratuit=(params.montant_livraison_gratuite if params else 0))

@app.route("/recherche")
def recherche():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("shop/recherche.html", requete="", produits=[], total=0,
                               page=1, pages=1, reste=0, tri="defaut", tris=TRIS)

    base = Produit.query.filter(Produit.actif == True)
    contexte = page_produits(base, request.args.get("tri"), terme=q)
    if request.args.get("fragment"):
        # « Voir plus » recharge la suite de la meme recherche : compter un
        # second Search ferait passer une seule intention pour deux.
        return render_template("shop/_grille_paginee.html", **contexte)

    event_id = nouvel_event_id()
    envoyer_evenement_meta("Search", event_id, request.url, donnees_client_meta(), {
        "search_string": q[:200],
        "content_type": "product",
        "content_ids": [p.reference or str(p.id) for p in contexte["produits"][:10]],
    })
    return render_template("shop/recherche.html", requete=q, event_id=event_id, **contexte)

# ---------------------------------------------------------------------------
# PANIER
#
# Une ligne n'est plus un simple produit : elle peut porter une variante
# (couleur, taille) et un lot (palier d'achat). La cle du panier combine les
# trois, pour que deux choix differents du meme produit coexistent.
# ---------------------------------------------------------------------------

def cle_panier(produit_id, variante_id=None, lot_id=None):
    return "%s-%s-%s" % (produit_id, variante_id or 0, lot_id or 0)


def lire_panier():
    """Retourne {cle: {produit_id, variante_id, lot_id, quantite}}.
    Les paniers enregistres a l'ancien format {id: quantite} sont convertis."""
    brut = session.get("panier") or {}
    propre, migre = {}, False

    for cle, valeur in brut.items():
        if isinstance(valeur, dict):
            propre[cle] = valeur
            continue
        migre = True
        try:
            pid = int(str(cle).split("-")[0])
        except ValueError:
            continue
        propre[cle_panier(pid)] = {"produit_id": pid, "variante_id": None,
                                   "lot_id": None, "quantite": int(valeur)}
    if migre:
        session["panier"] = propre
    return propre


def ecrire_panier(panier):
    session["panier"] = panier


def prix_lot_simple(produit, unitaire, quantite):
    """Prix total pour cette quantite. Retourne (sous_total, economie).

    Deux mecanismes possibles, les paliers ayant la priorite :
      - une grille de prix degressifs (100 pieces -> 1.95 au lieu de 2.25) ;
      - une remise simple a partir d'une quantite donnee."""
    plein = unitaire * quantite

    if produit.a_paliers:
        applique = produit.prix_par_quantite(quantite, unitaire)
        total = applique * quantite
        return round(total, 3), round(max(0, plein - total), 3)

    offre = produit.remise_lot
    if not offre or quantite < offre["quantite"]:
        return round(plein, 3), 0.0
    if offre["type"] == "pourcentage":
        economie = plein * offre["valeur"] / 100.0
    else:
        economie = offre["valeur"] * (quantite // offre["quantite"])
    economie = min(economie, plein)
    return round(plein - economie, 3), round(economie, 3)


def detailler_panier():
    """Transforme le panier en lignes exploitables, prix et remises compris."""
    articles, total, economies = [], 0.0, 0.0

    for cle, entree in lire_panier().items():
        produit = Produit.query.get(entree["produit_id"])
        if not produit:
            continue
        variante = (VarianteProduit.query.get(entree["variante_id"])
                    if entree.get("variante_id") else None)
        lot = LotProduit.query.get(entree["lot_id"]) if entree.get("lot_id") else None
        quantite = max(1, int(entree.get("quantite") or 1))

        if lot:
            # Le lot fixe un prix total : la quantite du panier compte les lots.
            unitaire = lot.prix_unitaire
            sous_total = round((lot.prix or 0) * quantite, 3)
            economie = round(lot.economie * quantite, 3)
            articles_reels = (lot.quantite or 1) * quantite
        else:
            unitaire = variante.prix_effectif if variante else (produit.prix_affiche or 0)
            sous_total, economie = prix_lot_simple(produit, unitaire, quantite)
            articles_reels = quantite

        total += sous_total
        economies += economie
        articles.append({
            "cle": cle, "produit": produit, "variante": variante, "lot": lot,
            "quantite": quantite, "unitaire": unitaire, "sous_total": sous_total,
            "economie": economie, "articles_reels": articles_reels,
            "nom_affiche": intitule(produit) + (" - " + variante.libelle if variante else ""),
            "image": (variante.image if variante and variante.image else produit.image),
            "cout": (variante.cout_effectif if variante else (produit.cout or 0)),
        })

    return articles, round(total, 3), round(economies, 3)


def stock_disponible(produit, variante=None):
    if variante:
        return variante.stock or 0
    if produit.a_variantes:
        return produit.stock_total
    return produit.stock or 0


def frais_livraison_panier(articles, params):
    """Le produit le plus cher a livrer fixe les frais : on ne cumule pas les
    livraisons quand plusieurs articles partent dans le meme colis."""
    defaut = params.frais_livraison_defaut if params else 8.0
    specifiques = [a["produit"].prix_livraison for a in articles
                   if a["produit"].prix_livraison is not None]
    specifiques += [a["lot"].prix_livraison for a in articles
                    if a.get("lot") and a["lot"].prix_livraison is not None]
    return max(specifiques) if specifiques else defaut


def suggestions_panier(ids_dans_panier, limite=3):
    """Produits proposes en complement : ceux marques comme offre, puis a
    defaut les produits de la meme categorie que le panier."""
    exclus = [int(i) for i in ids_dans_panier]
    base = Produit.query.filter(Produit.actif == True, Produit.stock > 0)
    if exclus:
        base = base.filter(~Produit.id.in_(exclus))

    offres = base.filter(Produit.offre_panier == True).limit(limite).all()
    if len(offres) >= limite:
        return offres

    categories = [p.categorie_id for p in Produit.query.filter(Produit.id.in_(exclus)).all()
                  if p.categorie_id] if exclus else []
    if categories:
        deja = [p.id for p in offres]
        complement = base.filter(Produit.categorie_id.in_(categories))
        if deja:
            complement = complement.filter(~Produit.id.in_(deja))
        offres += complement.order_by(Produit.vedette.desc()).limit(limite - len(offres)).all()
    return offres


@app.route("/panier/ajouter/<int:produit_id>", methods=["POST"])
def ajouter_panier(produit_id):
    produit = Produit.query.get_or_404(produit_id)
    langue = langue_courante()

    variante = None
    if produit.a_variantes:
        vid = request.form.get("variante_id")
        variante = VarianteProduit.query.filter_by(id=vid, produit_id=produit.id).first() if vid else None
        if not variante:
            flash(traduire("choisir_option", langue), "erreur")
            return redirect(url_for("voir_produit", produit_id=produit.id))

    lot = None
    lid = request.form.get("lot_id")
    if lid:
        lot = LotProduit.query.filter_by(id=lid, produit_id=produit.id).first()

    quantite = max(1, int(request.form.get("quantite", 1)))
    panier = lire_panier()
    cle = cle_panier(produit.id, variante.id if variante else None, lot.id if lot else None)
    deja = panier.get(cle, {}).get("quantite", 0)

    if not produit.commandable:
        flash(traduire("rupture_stock", langue), "erreur")
        return redirect(request.referrer or url_for("accueil"))

    # Un lot consomme plusieurs unites : on compte en articles reels.
    par_unite = (lot.quantite or 1) if lot else 1
    demande = (deja + quantite) * par_unite
    disponible = stock_disponible(produit, variante)
    if not produit.vente_en_rupture and demande > disponible:
        flash(traduire("stock_insuffisant", langue,
                       produit=produit.nom, stock=disponible), "erreur")
        return redirect(url_for("voir_produit", produit_id=produit.id))

    panier[cle] = {"produit_id": produit.id,
                   "variante_id": variante.id if variante else None,
                   "lot_id": lot.id if lot else None,
                   "quantite": deja + quantite}
    ecrire_panier(panier)

    prix_evt = (lot.prix if lot else (variante.prix_effectif if variante else produit.prix_affiche))
    envoyer_evenement_meta("AddToCart", request.form.get("event_id") or nouvel_event_id(),
                           request.referrer or request.url, donnees_client_meta(), {
        "currency": "TND",
        "value": round((prix_evt or 0) * quantite, 3),
        "content_type": "product",
        "content_name": produit.nom,
        "content_ids": [produit.reference or str(produit.id)],
        "contents": [{"id": produit.reference or str(produit.id), "quantity": quantite,
                      "item_price": round(prix_evt or 0, 3)}],
    })
    return redirect(request.referrer or url_for("accueil"))


@app.route("/panier")
def voir_panier():
    articles, total, economies = detailler_panier()

    reduction, promo = 0, None
    code = session.get("code_promo")
    if code:
        promo = CodePromo.query.filter_by(code=code).first()
        if promo:
            ok, _ = promo.est_valide(total)
            if ok: reduction = promo.calculer_reduction(total)
            else: session.pop("code_promo", None); promo = None

    return render_template("shop/panier.html", articles=articles, total=total,
                           reduction=reduction, promo_active=promo,
                           total_final=total-reduction, economies=economies,
                           suggestions=suggestions_panier(
                               [a["produit"].id for a in articles]))


@app.route("/panier/maj/<cle>", methods=["POST"])
def maj_panier(cle):
    panier = lire_panier()
    if cle in panier:
        qte = int(request.form.get("quantite", 1))
        if qte <= 0:
            panier.pop(cle)
        else:
            panier[cle]["quantite"] = qte
        ecrire_panier(panier)
    return redirect(url_for("voir_panier"))


@app.route("/panier/supprimer/<cle>")
def supprimer_panier(cle):
    panier = lire_panier()
    panier.pop(cle, None)
    ecrire_panier(panier)
    return redirect(url_for("voir_panier"))


@app.route("/panier/appliquer-promo", methods=["POST"])
def appliquer_code_promo():
    code = request.form.get("code_promo", "").strip().upper()
    montant = detailler_panier()[1]
    promo = CodePromo.query.filter_by(code=code).first()
    if not promo: flash(traduire("code_invalide", langue_courante()), "erreur")
    else:
        ok, message = promo.est_valide(montant)
        if ok: session["code_promo"] = code; flash(traduire("code_applique_ok", langue_courante(), code=code), "succes")
        else: flash(message, "erreur")
    return redirect(url_for("voir_panier"))

@app.route("/panier/retirer-promo")
def retirer_code_promo():
    session.pop("code_promo", None); return redirect(url_for("voir_panier"))

# ---------------------------------------------------------------------------
# ENREGISTREMENT D'UNE COMMANDE
#
# Deux chemins y menent : le panier classique, et l'achat direct depuis la
# fiche produit. La logique est la meme, elle est donc ecrite une seule fois.
# ---------------------------------------------------------------------------

def calculer_livraison(articles, total, params):
    """Un port fixe par l'admin s'impose, meme au-dessus du seuil de gratuite."""
    port_specifique = [a["produit"].prix_livraison for a in articles
                       if a["produit"].prix_livraison is not None]
    port_specifique += [a["lot"].prix_livraison for a in articles
                        if a.get("lot") and a["lot"].prix_livraison is not None]
    if port_specifique:
        return max(port_specifique)
    if params and total >= (params.montant_livraison_gratuite or 0):
        return 0
    return frais_livraison_panier(articles, params)


def valider_coordonnees(formulaire, articles):
    erreurs = []
    langue = langue_courante()
    if len((formulaire.get("nom_client") or "").strip()) < 3:
        erreurs.append(traduire("nom_requis", langue))
    if not telephone_valide(formulaire.get("telephone") or ""):
        erreurs.append(traduire("telephone_invalide", langue))
    for a in articles:
        dispo = stock_disponible(a["produit"], a["variante"])
        if not a["produit"].vente_en_rupture and a["articles_reels"] > dispo:
            erreurs.append(traduire("stock_insuffisant", langue,
                                    produit=a["nom_affiche"], stock=dispo))
    return erreurs


def enregistrer_commande(articles, formulaire, livraison, total, reduction, promo, vider_panier):
    """Cree la commande, decremente les stocks, previent Meta. Retourne le numero."""
    nom_client = (formulaire.get("nom_client") or "").strip()
    telephone = (formulaire.get("telephone") or "").strip()
    numero = generer_numero_commande()

    commande = Commande(
        numero=numero, nom_client=nom_client, telephone=telephone,
        gouvernorat=(formulaire.get("gouvernorat") or "").strip(),
        ville=(formulaire.get("ville") or "").strip(),
        adresse=(formulaire.get("adresse") or "").strip(),
        commentaire=(formulaire.get("commentaire") or "").strip(),
        total=round(total + livraison - reduction, 3), frais_livraison=livraison,
        code_promo_utilise=promo.code if promo else None, montant_reduction=reduction)
    db.session.add(commande)
    db.session.flush()

    for a in articles:
        # On enregistre en articles reels : un lot de 3 compte pour 3 pieces,
        # et le prix unitaire tient compte des remises.
        unites = a["articles_reels"]
        unitaire = round(a["sous_total"] / unites, 3) if unites else 0
        libelle = a["nom_affiche"] + (" [%s]" % a["lot"].nom if a["lot"] else "")
        db.session.add(LigneCommande(commande_id=commande.id, produit_id=a["produit"].id,
                                     nom_produit=libelle, prix_unitaire=unitaire,
                                     cout_unitaire=a["cout"], quantite=unites))
        if a["variante"]:
            a["variante"].stock = (a["variante"].stock or 0) - unites
        else:
            a["produit"].stock = (a["produit"].stock or 0) - unites

    if promo:
        promo.utilisation_actuelle += 1

    attribution = session.get("attribution") or {}
    for champ in ("utm_source", "utm_medium", "utm_campagne", "utm_adset", "utm_annonce"):
        setattr(commande, champ, attribution.get(champ))

    commande.event_id_purchase = nouvel_event_id()

    abandon = PanierAbandonne.query.filter_by(
        telephone_normalise=telephone_e164(telephone)).filter(
        PanierAbandonne.statut != "recupere").first()
    if abandon:
        abandon.statut = "recupere"
        abandon.commande_numero = numero

    db.session.commit()

    envoyer_evenement_meta("Purchase", commande.event_id_purchase, request.url,
                           donnees_client_meta(commande), {
        "currency": "TND",
        "value": round(commande.total or 0, 3),
        "content_type": "product",
        "contents": contenus_meta(articles),
        "num_items": sum(a["quantite"] for a in articles),
        "order_id": numero,
    })

    if vider_panier:
        ecrire_panier({})
        session.pop("code_promo", None)
    return numero


@app.route("/produit/<int:produit_id>/acheter", methods=["POST"])
def acheter_direct(produit_id):
    """Commande en une etape depuis la fiche produit, sans passer par le panier."""
    produit = Produit.query.get_or_404(produit_id)
    langue = langue_courante()

    variante = None
    if produit.a_variantes:
        vid = request.form.get("variante_id")
        variante = VarianteProduit.query.filter_by(id=vid, produit_id=produit.id).first() if vid else None
        if not variante:
            flash(traduire("choisir_option", langue), "erreur")
            return redirect(url_for("voir_produit", produit_id=produit.id))

    lot = None
    lid = request.form.get("lot_id")
    if lid:
        lot = LotProduit.query.filter_by(id=lid, produit_id=produit.id).first()

    if not produit.commandable:
        flash(traduire("rupture_stock", langue), "erreur")
        return redirect(url_for("voir_produit", produit_id=produit.id))

    quantite = max(1, int(request.form.get("quantite") or 1))
    if lot:
        unitaire = lot.prix_unitaire
        sous_total = round((lot.prix or 0) * quantite, 3)
        economie = round(lot.economie * quantite, 3)
        articles_reels = (lot.quantite or 1) * quantite
    else:
        unitaire = variante.prix_effectif if variante else (produit.prix_affiche or 0)
        sous_total, economie = prix_lot_simple(produit, unitaire, quantite)
        articles_reels = quantite

    articles = [{
        "cle": cle_panier(produit.id, variante.id if variante else None, lot.id if lot else None),
        "produit": produit, "variante": variante, "lot": lot,
        "quantite": quantite, "unitaire": unitaire, "sous_total": sous_total,
        "economie": economie, "articles_reels": articles_reels,
        "nom_affiche": intitule(produit) + (" - " + variante.libelle if variante else ""),
        "image": (variante.image if variante and variante.image else produit.image),
        "cout": (variante.cout_effectif if variante else (produit.cout or 0)),
    }]

    erreurs = valider_coordonnees(request.form, articles)
    if erreurs:
        for message in erreurs:
            flash(message, "erreur")
        return redirect(url_for("voir_produit", produit_id=produit.id))

    params = ParametreBoutique.query.first()
    livraison = calculer_livraison(articles, sous_total, params)
    numero = enregistrer_commande(articles, request.form, livraison, sous_total, 0, None,
                                  vider_panier=False)
    return redirect(url_for("confirmation_commande", numero=numero))


@app.route("/commander", methods=["GET", "POST"])
def commander():
    if not lire_panier(): return redirect(url_for("accueil"))
    articles, total, economies = detailler_panier()
    if not articles: return redirect(url_for("accueil"))

    params = ParametreBoutique.query.first()
    livraison = calculer_livraison(articles, total, params)
    promo = CodePromo.query.filter_by(code=session.get("code_promo")).first() if session.get("code_promo") else None
    reduction = promo.calculer_reduction(total) if promo and promo.est_valide(total)[0] else 0

    if request.method == "POST":
        erreurs = valider_coordonnees(request.form, articles)
        if erreurs:
            for message in erreurs:
                flash(message, "erreur")
            return render_template("shop/commander.html", articles=articles, total=total,
                                   frais_livraison=livraison, reduction=reduction,
                                   total_final=total+livraison-reduction,
                                   gouvernorats_json=GOUVERNORATS_TUNISIE)

        numero = enregistrer_commande(articles, request.form, livraison, total, reduction,
                                      promo, vider_panier=True)
        return redirect(url_for("confirmation_commande", numero=numero))

    event_id = nouvel_event_id()
    envoyer_evenement_meta("InitiateCheckout", event_id, request.url, donnees_client_meta(), {
        "currency": "TND",
        "value": round(total + livraison - reduction, 3),
        "content_type": "product",
        "contents": contenus_meta(articles),
        "num_items": sum(a["quantite"] for a in articles),
    })
    return render_template("shop/commander.html", articles=articles, total=total,
                           frais_livraison=livraison, reduction=reduction,
                           total_final=total+livraison-reduction, event_id=event_id,
                           gouvernorats_json=GOUVERNORATS_TUNISIE,
                           suggestions=suggestions_panier([a["produit"].id for a in articles], 2))

@app.route("/confirmation/<numero>")
def confirmation_commande(numero):
    commande = Commande.query.filter_by(numero=numero).first_or_404()
    # Les photos viennent des produits : la ligne de commande ne garde que le nom.
    ids = [l.produit_id for l in commande.lignes if l.produit_id]
    produits = {p.id: p for p in Produit.query.filter(Produit.id.in_(ids)).all()} if ids else {}
    return render_template("shop/confirmation.html", commande=commande,
                           produits_par_id=produits,
                           contenus_pixel=[{"id": l.produit.reference or str(l.produit_id) if l.produit else str(l.produit_id),
                                            "quantity": l.quantite,
                                            "item_price": round(l.prix_unitaire or 0, 3)}
                                           for l in commande.lignes])

@app.route("/suivi", methods=["GET", "POST"])
def suivi_commande():
    c = Commande.query.filter_by(numero=request.form.get("numero"), telephone=request.form.get("telephone")).first() if request.method == "POST" else None
    return render_template("shop/suivi.html", commande=c,
                           lien_suivi=(lien_de_suivi(c) if c else None), erreur=traduire("commande_introuvable", langue_courante()) if request.method == "POST" and not c else None)

# Reglages du « mot de passe oublie ». Six chiffres se devinent vite : la
# duree courte et le petit nombre d'essais sont ce qui rend le code sur.
DUREE_CODE_MINUTES = 15
ESSAIS_CODE_MAX = 5
CODES_PAR_QUART_DHEURE = 3


def code_a_six_chiffres():
    """Tire au sort par le generateur cryptographique, pas par random."""
    return "%06d" % secrets.randbelow(1000000)


# Sans O/0 ni I/l/1 : le mot de passe se dicte au telephone et se recopie
# depuis WhatsApp sans faire hesiter sur un caractere.
ALPHABET_PROVISOIRE = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


def mot_de_passe_provisoire(longueur=10):
    return "".join(secrets.choice(ALPHABET_PROVISOIRE) for _ in range(longueur))


def perimer_les_codes(utilisateur):
    """Un code encore en vie rouvrirait le compte : on les fait tous tomber."""
    for demande in CodeReinitialisation.query.filter_by(
            utilisateur_id=utilisateur.id, utilise=False).all():
        demande.utilise = True


def demandes_recentes(utilisateur):
    """Combien de codes ce compte a-t-il demandes dans le dernier quart d'heure."""
    depuis = datetime.utcnow() - timedelta(minutes=DUREE_CODE_MINUTES)
    return CodeReinitialisation.query.filter(
        CodeReinitialisation.utilisateur_id == utilisateur.id,
        CodeReinitialisation.date_creation >= depuis).count()


def envoyer_code(utilisateur):
    """Cree un code, l'envoie, et renvoie True si le courriel est parti."""
    code = code_a_six_chiffres()
    db.session.add(CodeReinitialisation(
        utilisateur_id=utilisateur.id,
        code_hash=generate_password_hash(code),
        expire_le=datetime.utcnow() + timedelta(minutes=DUREE_CODE_MINUTES)))
    db.session.commit()

    boutique = ParametreBoutique.query.first()
    enseigne = (boutique.nom_boutique if boutique else "Maison des Garnitures")
    texte = (
        "Bonjour,\n\n"
        "Voici votre code pour changer le mot de passe de l'administration "
        "%s :\n\n    %s\n\n"
        "Il est valable %d minutes et ne sert qu'une fois.\n\n"
        "Si vous n'avez rien demande, ignorez ce message : votre mot de passe "
        "n'a pas change.\n" % (enseigne, code, DUREE_CODE_MINUTES))

    envoye = courriel.envoyer(utilisateur.email,
                              "%s — code de verification" % enseigne, texte)
    if not envoye and not EN_PRODUCTION:
        # En local, sans serveur d'envoi configure, le code passe par le
        # journal : de quoi essayer la page sans monter un service de mail.
        app.logger.warning("SMTP absent — code pour %s : %s",
                           utilisateur.email, code)
    return envoye


@app.route("/admin/mot-de-passe-oublie", methods=["GET", "POST"])
def admin_mot_de_passe_oublie():
    """Demande d'un code. Ne dit jamais si l'adresse existe.

    Repondre « compte inconnu » permettrait de dresser la liste des adresses
    valides : le message est donc le meme dans tous les cas.
    """
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()[:150]
        u = Utilisateur.query.filter_by(email=email, actif=True).first()
        if u:
            if demandes_recentes(u) >= CODES_PAR_QUART_DHEURE:
                app.logger.warning("Trop de demandes de code pour %s", email)
            else:
                envoyer_code(u)
        return render_template("admin/code_envoye.html", email=email)
    return render_template("admin/mot_de_passe_oublie.html")


@app.route("/admin/reinitialiser", methods=["GET", "POST"])
def admin_reinitialiser():
    """Etape 1 : le code, et rien d'autre.

    Le mot de passe se choisit a l'ecran suivant. Melanger les deux obligeait
    a tout retaper des qu'un chiffre etait faux, et laissait croire que le
    code avait ete refuse quand c'etait la confirmation qui ne suivait pas.
    """
    email = (request.values.get("email") or "").strip().lower()[:150]
    erreur = None

    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        u = Utilisateur.query.filter_by(email=email, actif=True).first()
        demande = None
        if u:
            demande = (CodeReinitialisation.query
                       .filter_by(utilisateur_id=u.id, utilise=False)
                       .order_by(CodeReinitialisation.id.desc()).first())

        if not demande or not demande.valide:
            erreur = "Code expire ou invalide. Demandez-en un nouveau."
        elif not check_password_hash(demande.code_hash, code):
            demande.essais = (demande.essais or 0) + 1
            db.session.commit()
            restants = ESSAIS_CODE_MAX - demande.essais
            erreur = ("Code incorrect. %s"
                      % ("Il ne reste plus d'essai : demandez un nouveau code."
                         if restants <= 0 else "Essais restants : %d." % restants))
        else:
            # Le code n'est pas consomme ici : un abandon a l'ecran suivant
            # obligerait alors a en redemander un. Le laissez-passer tient
            # dans la session signee, que le visiteur ne peut pas fabriquer.
            session["reinit_demande"] = demande.id
            session["reinit_utilisateur"] = u.id
            return redirect(url_for("admin_nouveau_mot_de_passe"))

    return render_template("admin/reinitialiser.html", email=email, erreur=erreur)


def oublier_laissez_passer():
    session.pop("reinit_demande", None)
    session.pop("reinit_utilisateur", None)


@app.route("/admin/nouveau-mot-de-passe", methods=["GET", "POST"])
def admin_nouveau_mot_de_passe():
    """Etape 2 : le nouveau mot de passe, une fois le code reconnu."""
    demande = db.session.get(CodeReinitialisation, session.get("reinit_demande") or 0)
    u = db.session.get(Utilisateur, session.get("reinit_utilisateur") or 0)

    # Le quart d'heure a pu s'ecouler pendant que la page restait ouverte.
    if not demande or not u or demande.utilisateur_id != u.id or not demande.valide:
        oublier_laissez_passer()
        flash("Le code a expire. Demandez-en un nouveau.", "erreur")
        return redirect(url_for("admin_mot_de_passe_oublie"))

    erreur = None
    if request.method == "POST":
        nouveau = request.form.get("mot_de_passe") or ""
        confirme = request.form.get("mot_de_passe_2") or ""

        if len(nouveau) < 8:
            erreur = "Le mot de passe doit faire au moins 8 caracteres."
        elif nouveau != confirme:
            erreur = "Les deux mots de passe ne sont pas identiques."
        else:
            u.mot_de_passe_hash = generate_password_hash(nouveau)
            u.doit_changer_mdp = False
            # Tous les codes de ce compte tombent, pas seulement celui-ci.
            perimer_les_codes(u)
            db.session.commit()
            oublier_laissez_passer()
            app.logger.info("Mot de passe change pour %s", u.email)
            flash("Mot de passe modifie. Vous pouvez vous connecter.", "succes")
            return redirect(url_for("admin_login"))

    return render_template("admin/nouveau_mot_de_passe.html",
                           email_masque=u.email_masque, erreur=erreur)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        u = Utilisateur.query.filter_by(email=request.form.get("email", "").strip().lower(), actif=True).first()
        if u and u.verifier_mot_de_passe(request.form.get("mot_de_passe", "")): session["user_id"] = u.id; return redirect(url_for("admin_dashboard"))
    return render_template("admin/login.html", erreur="Email ou mot de passe incorrect." if request.method == "POST" else None)

@app.route("/admin/mon-mot-de-passe", methods=["GET", "POST"])
@connexion_requise
def admin_changer_mot_de_passe():
    """Chacun change le sien, quel que soit son role.

    Sans cette page, un membre de l'equipe ne peut rien faire seul : la liste
    « Equipe » est reservee au proprietaire. C'est aussi l'ecran impose apres
    un mot de passe provisoire.
    """
    u = utilisateur_courant()
    erreur = None

    if request.method == "POST":
        actuel = request.form.get("actuel") or ""
        nouveau = request.form.get("mot_de_passe") or ""
        confirme = request.form.get("mot_de_passe_2") or ""

        if not u.verifier_mot_de_passe(actuel):
            erreur = "Mot de passe actuel incorrect."
        elif len(nouveau) < 8:
            erreur = "Le nouveau mot de passe doit faire au moins 8 caracteres."
        elif nouveau != confirme:
            erreur = "Les deux mots de passe ne sont pas identiques."
        elif nouveau == actuel:
            erreur = "Choisis un mot de passe different de l'ancien."
        else:
            u.mot_de_passe_hash = generate_password_hash(nouveau)
            u.doit_changer_mdp = False
            perimer_les_codes(u)
            db.session.commit()
            app.logger.info("Mot de passe change par %s", u.email)
            flash("Mot de passe modifie.", "succes")
            return redirect(url_for("admin_dashboard"))

    return render_template("admin/changer_mot_de_passe.html",
                           u=u, impose=bool(u.doit_changer_mdp), erreur=erreur)


@app.route("/admin/logout")
def admin_logout(): session.pop("user_id", None); return redirect(url_for("admin_login"))

@app.route("/admin")
@connexion_requise
def admin_dashboard():
    # Tous les comptes du tableau de bord ignorent la corbeille : une
    # commande supprimee ne doit ni s'afficher, ni gonfler les totaux.
    actives = Commande.query.filter(Commande.supprimee_le.is_(None))

    def combien(statut):
        return actives.filter(Commande.statut == statut).count()

    return render_template(
        "admin/dashboard.html",
        revenus=revenus_par_periode(),
        total_produits=Produit.query.count(),
        commandes_nouvelles=combien("nouvelle"),
        commandes_a_confirmer=combien("a_confirmer"),
        commandes_confirmees=combien("confirmee"),
        ventes_totales=db.session.query(db.func.sum(Commande.total))
                         .filter(Commande.supprimee_le.is_(None)).scalar() or 0,
        dernieres_commandes=actives.order_by(Commande.date_creation.desc()).limit(10).all(),
        produits_rupture=Produit.query.filter(Produit.stock <= 0,
                                              Produit.actif == True).all())

@app.route("/admin/promotions")
@connexion_requise
@roles_requis("proprietaire")
def admin_promotions(): return render_template("admin/promotions.html", promotions=CodePromo.query.order_by(CodePromo.date_creation.desc()).all())

@app.route("/admin/promotions/nouvelle", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_promotion_nouvelle():
    if request.method == "POST":
        p = CodePromo(titre=request.form.get("titre", "").strip(), code=request.form.get("code", "").strip().upper(), type_reduction=request.form.get("type_reduction", "pourcentage"), valeur=float(request.form.get("valeur") or 0), montant_minimum=float(request.form.get("montant_minimum") or 0), utilisation_max=int(request.form.get("utilisation_max") or 0), date_debut=datetime.strptime(request.form["date_debut"], "%Y-%m-%d") if request.form.get("date_debut") else None, date_fin=datetime.strptime(request.form["date_fin"], "%Y-%m-%d") if request.form.get("date_fin") else None, actif=bool(request.form.get("actif")))
        db.session.add(p); db.session.commit(); return redirect(retour_admin("admin_promotions"))
    return render_template("admin/promotion_form.html", promo=None)

@app.route("/admin/promotions/<int:promo_id>/toggle", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_promotion_toggle(promo_id):
    p = CodePromo.query.get_or_404(promo_id); p.actif = not p.actif; db.session.commit(); return redirect(retour_admin("admin_promotions"))

@app.route("/admin/promotions/<int:promo_id>/supprimer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_promotion_supprimer(promo_id):
    db.session.delete(CodePromo.query.get_or_404(promo_id)); db.session.commit(); return redirect(retour_admin("admin_promotions"))

def compter_par_statut():
    """Nombre de commandes actives par statut, en une seule requete."""
    lignes = (db.session.query(Commande.statut, db.func.count(Commande.id))
              .filter(Commande.supprimee_le.is_(None))
              .group_by(Commande.statut).all())
    comptes = {statut: nombre for statut, nombre in lignes}
    comptes["_toutes"] = sum(comptes.values())
    return comptes


@app.route("/admin/commandes")
@connexion_requise
@roles_requis("proprietaire", "commandes", "livraison")
def admin_commandes():
    corbeille = request.args.get("corbeille") == "1"
    requete = Commande.query.filter(Commande.supprimee_le.isnot(None) if corbeille
                                    else Commande.supprimee_le.is_(None))
    statut = request.args.get("statut", "").strip()
    if statut:
        requete = requete.filter_by(statut=statut)

    # Filtre par periode : on prend la journee entiere pour la date de fin.
    du = (request.args.get("du") or "").strip()
    au = (request.args.get("au") or "").strip()
    for valeur, comparaison in ((du, "debut"), (au, "fin")):
        if not valeur:
            continue
        try:
            jour = datetime.strptime(valeur, "%Y-%m-%d")
        except ValueError:
            continue
        if comparaison == "debut":
            requete = requete.filter(Commande.date_creation >= jour)
        else:
            requete = requete.filter(Commande.date_creation < jour + timedelta(days=1))

    if request.args.get("impression") == "non":
        requete = requete.filter(Commande.imprimee_le.is_(None))
    elif request.args.get("impression") == "oui":
        requete = requete.filter(Commande.imprimee_le.isnot(None))

    transporteur_filtre = (request.args.get("transporteur") or "").strip()
    if transporteur_filtre == "sans":
        requete = requete.filter((Commande.transporteur.is_(None))
                                 | (Commande.transporteur == ""))
    elif transporteur_filtre:
        requete = requete.filter(Commande.transporteur == transporteur_filtre)

    commandes = requete.order_by(Commande.date_creation.desc()).all()

    # Recherche libre : numero, nom, telephone, ville ou numero de suivi.
    # On filtre en memoire pour ignorer accents et espaces, que SQLite ne sait
    # pas traiter.
    recherche = (request.args.get("q") or "").strip()
    if recherche:
        cible = sans_accents_simple(recherche)
        chiffres = "".join(c for c in recherche if c.isdigit())

        def correspond(commande):
            champs = (commande.numero, commande.nom_client, commande.ville,
                      commande.gouvernorat, commande.adresse,
                      commande.gouvernorat, commande.numero_suivi, commande.transporteur)
            if any(cible in sans_accents_simple(c or "") for c in champs):
                return True
            # Un numero se cherche sans espaces et quel que soit l'indicatif :
            # on rapproche sur les huit derniers chiffres, le format tunisien.
            if chiffres:
                tel = "".join(c for c in (commande.telephone or "") if c.isdigit())
                return (chiffres in tel) or (tel and tel[-8:] == chiffres[-8:])
            return False

        commandes = [c for c in commandes if correspond(c)]
    # Un seul acces a la table des transporteurs pour toute la liste.
    par_nom = {t.nom: t for t in Transporteur.query.all()}
    # Pagination : au-dela de quelques dizaines de lignes la page devient lourde.
    par_page = request.args.get("par_page", "25")
    par_page = int(par_page) if par_page.isdigit() and int(par_page) in (25, 50, 100) else 25
    page = request.args.get("page", "1")
    page = int(page) if page.isdigit() and int(page) > 0 else 1
    nb_pages = max(1, (len(commandes) + par_page - 1) // par_page)
    page = min(page, nb_pages)
    total_filtre = len(commandes)
    commandes = commandes[(page - 1) * par_page: page * par_page]

    # Vignette du premier article de chaque commande.
    ids_produits = [l.produit_id for c in commandes for l in c.lignes if l.produit_id]
    vignettes = {p.id: p for p in Produit.query.filter(Produit.id.in_(ids_produits)).all()}         if ids_produits else {}

    return render_template("admin/commandes.html",
                           commandes=commandes,
                           vignettes=vignettes,
                           page=page, nb_pages=nb_pages, par_page=par_page,
                           total_filtre=total_filtre,
                           transporteurs_par_nom=par_nom,
                           transporteurs_liste=transporteurs_actifs(),
                           corbeille=corbeille,
                           statuts=STATUTS_COMMANDE,
                           nb_par_statut=compter_par_statut(),
                           impression=(request.args.get("impression") or ""),
                           nb_corbeille=Commande.query.filter(
                               Commande.supprimee_le.isnot(None)).count(),
                           statut_actif=statut, recherche=recherche,
                           du=du, au=au, transporteur_filtre=transporteur_filtre,
                           total_commandes=Commande.query.filter(
                               Commande.supprimee_le.is_(None)).count(),
                           role=utilisateur_courant().role)

@app.route("/admin/commandes/<int:commande_id>")
@connexion_requise
@roles_requis("proprietaire", "commandes", "livraison")
def admin_commande_detail(commande_id):
    # Une commande supprimee ou un lien devenu obsolete ne doit pas tomber sur
    # la page d'erreur brute du serveur : on renvoie vers la liste avec un mot.
    commande = Commande.query.get(commande_id)
    if commande is None:
        flash("Cette commande n'existe plus (numero %s)." % commande_id, "erreur")
        return redirect(retour_admin("admin_commandes"))
    params = ParametreBoutique.query.first()
    valeurs = {
        "client": commande.nom_client,
        "boutique": params.nom_boutique if params else "Maison des Garnitures",
        "numero": commande.numero,
        "total": "%.2f" % (commande.total or 0),
        "produits": resume_articles([{"nom": l.nom_produit, "quantite": l.quantite,
                                      "prix": l.prix_unitaire or 0} for l in commande.lignes]),
        "transporteur": commande.transporteur or "",
        "suivi": commande.numero_suivi or "",
    }

    def modele(champ):
        valeur = getattr(params, champ, "") if params else ""
        return valeur or MODELES_MESSAGES_DEFAUT[champ]

    return render_template("admin/commande_detail.html", commande=commande,
                           transporteurs_liste=[t.nom for t in transporteurs_actifs()],
                           lien_suivi=lien_de_suivi(commande),
                           transporteur_actuel=transporteur_par_nom(commande.transporteur),
                           transporteurs_objets=transporteurs_actifs(),
                           whatsapp_confirmation=lien_whatsapp(commande.telephone, remplir_modele(modele("modele_whatsapp_confirmation"), valeurs)),
                           whatsapp_expedition=lien_whatsapp(commande.telephone, remplir_modele(modele("modele_whatsapp_expedition"), valeurs)))

# ---------------------------------------------------------------------------
# STATISTIQUES
#
# Toutes les pages partagent la meme periode, choisie en haut d'ecran.
# Les statuts sont regroupes en familles metier : une commande "nouvelle" ou
# "a_confirmer" est en attente, "annulee" et "injoignable" sont des refus.
# ---------------------------------------------------------------------------

# Les neuf etapes de la vie d'une commande, dans l'ordre du parcours.
# Une seule declaration : l'editeur et les filtres la lisent tous les deux,
# sinon un statut ajoute d'un cote reste introuvable de l'autre.
STATUTS_COMMANDE = [
    ("nouvelle", "Nouvelles"),
    ("a_confirmer", "A confirmer"),
    ("confirmee", "Confirmees"),
    ("preparation", "Preparation"),
    ("expediee", "Expediees"),
    ("livree", "Livrees"),
    ("annulee", "Annulees"),
    ("injoignable", "Injoignables"),
    ("retour", "Retours"),
]

STATUTS_ATTENTE = ("nouvelle", "a_confirmer")
STATUTS_CONFIRMEES = ("confirmee", "preparation", "expediee", "livree")
STATUTS_REFUSEES = ("annulee", "injoignable")
STATUTS_RETOUR = ("retour",)

PERIODES = {
    "7j": ("7 derniers jours", 7),
    "30j": ("30 derniers jours", 30),
    "90j": ("90 derniers jours", 90),
    "365j": ("12 derniers mois", 365),
}


def periode_demandee():
    """Retourne (debut, fin, cle, libelle). Les dates saisies priment sur le raccourci."""
    depuis = request.args.get("depuis", "")
    jusqua = request.args.get("jusqua", "")
    cle = request.args.get("periode", "30j")

    if depuis and jusqua:
        try:
            debut = datetime.strptime(depuis, "%Y-%m-%d")
            fin = datetime.strptime(jusqua, "%Y-%m-%d") + timedelta(days=1)
            return debut, fin, "perso", "%s au %s" % (
                debut.strftime("%d/%m/%Y"), (fin - timedelta(days=1)).strftime("%d/%m/%Y"))
        except ValueError:
            pass

    jours = PERIODES.get(cle, PERIODES["30j"])[1]
    fin = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    debut = fin - timedelta(days=jours)
    return debut, fin, cle if cle in PERIODES else "30j", PERIODES.get(cle, PERIODES["30j"])[0]


def commandes_periode(debut, fin):
    return Commande.query.filter(Commande.date_creation >= debut,
                                 Commande.date_creation < fin).all()


def somme(commandes):
    return round(sum(c.total or 0 for c in commandes), 3)


def marge(commandes):
    """Benefice = ce qui rentre, moins le prix d'achat des articles vendus.
    Les frais de livraison sont refactures au client, on les laisse de cote."""
    total = 0.0
    for c in commandes:
        for l in c.lignes:
            total += ((l.prix_unitaire or 0) - (l.cout_unitaire or 0)) * l.quantite
        total -= (c.montant_reduction or 0)
    return round(total, 3)


def valeur_du_stock():
    """Ce que le stock a coute, et ce qu'il rapporterait une fois vendu.

    Les produits a variantes comptent variante par variante : chacune a son
    propre stock, et parfois son propre cout et son propre prix.
    """
    unites = valeur_achat = revenu = 0.0
    unites_abimees = valeur_abimee = 0.0
    sans_cout = []

    for produit in Produit.query.all():
        if produit.a_variantes:
            lignes = [(v.stock or 0, v.cout_effectif or 0, v.prix_effectif or 0)
                      for v in produit.variantes]
        else:
            lignes = [(produit.stock or 0, produit.cout or 0, produit.prix_affiche or 0)]

        for quantite, cout, prix in lignes:
            if quantite <= 0:
                continue
            unites += quantite
            valeur_achat += quantite * cout
            revenu += quantite * prix
            if not cout:
                sans_cout.append(produit)

        abime = produit.stock_abime or 0
        if abime:
            unites_abimees += abime
            valeur_abimee += abime * (produit.cout or 0)

    return {
        "unites": int(unites),
        "valeur_achat": round(valeur_achat, 3),
        "revenu_estime": round(revenu, 3),
        "benefice_estime": round(revenu - valeur_achat, 3),
        "marge_pourcent": round((revenu - valeur_achat) / revenu * 100, 1) if revenu else 0,
        "unites_abimees": int(unites_abimees),
        "valeur_abimee": round(valeur_abimee, 3),
        # Un produit sans prix d'achat fausse la valeur du stock vers le bas.
        "sans_cout": sorted(set(p.id for p in sans_cout)),
    }


def revenus_par_periode():
    """Chiffre d'affaires encaisse par periode.

    En paiement a la livraison, une commande ne rapporte que lorsqu'elle est
    livree : une commande annulee, refusee au portail ou retournee n'est pas
    du chiffre d'affaires. On calcule donc sur les commandes livrees, et on
    donne a part ce qui est encore en route.
    """
    maintenant = datetime.now()
    debut_jour = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    debut_semaine = debut_jour - timedelta(days=debut_jour.weekday())
    debut_mois = debut_jour.replace(day=1)

    # Une commande a la corbeille n'est plus du chiffre d'affaires.
    toutes = Commande.query.filter(Commande.supprimee_le.is_(None)).all()
    livrees = [c for c in toutes if c.statut == "livree"]
    en_route = [c for c in toutes if c.statut in STATUTS_CONFIRMEES and c.statut != "livree"]

    def depuis(commandes, date):
        return [c for c in commandes if c.date_creation and c.date_creation >= date]

    livrees_jour = depuis(livrees, debut_jour)
    livrees_semaine = depuis(livrees, debut_semaine)
    livrees_mois = depuis(livrees, debut_mois)

    return {
        "jour": somme(livrees_jour), "nb_jour": len(livrees_jour),
        "semaine": somme(livrees_semaine), "nb_semaine": len(livrees_semaine),
        "mois": somme(livrees_mois), "nb_mois": len(livrees_mois),
        "total": somme(livrees), "nb_total": len(livrees),
        "marge_totale": marge(livrees),
        "marge_mois": marge(livrees_mois),
        "en_route": somme(en_route), "nb_en_route": len(en_route),
    }


def indicateurs(commandes):
    """Les chiffres cles, dans le vocabulaire du paiement a la livraison."""
    attente = [c for c in commandes if c.statut in STATUTS_ATTENTE]
    confirmees = [c for c in commandes if c.statut in STATUTS_CONFIRMEES]
    livrees = [c for c in commandes if c.statut == "livree"]
    refusees = [c for c in commandes if c.statut in STATUTS_REFUSEES]
    retours = [c for c in commandes if c.statut in STATUTS_RETOUR]
    traitees = len(livrees) + len(retours)

    return {
        "total": len(commandes), "total_valeur": somme(commandes),
        "attente": len(attente), "attente_valeur": somme(attente),
        "confirmees": len(confirmees), "confirmees_valeur": somme(confirmees),
        "livrees": len(livrees), "livrees_valeur": somme(livrees),
        "refusees": len(refusees), "refusees_valeur": somme(refusees),
        "retours": len(retours), "retours_valeur": somme(retours),
        # Encaisse : seule une commande livree rapporte reellement de l'argent.
        "encaisse": somme(livrees),
        "marge_livree": marge(livrees),
        "marge_attendue": marge(confirmees),
        "perte_retours": marge(retours),
        "panier_moyen": round(somme(livrees) / len(livrees), 3) if livrees else 0,
        "taux_confirmation": round(len(confirmees) / len(commandes) * 100, 1) if commandes else 0,
        "taux_livraison": round(len(livrees) / traitees * 100, 1) if traitees else 0,
        "taux_retour": round(len(retours) / traitees * 100, 1) if traitees else 0,
    }


def serie_journaliere(commandes, debut, fin):
    """Nombre de commandes et chiffre d'affaires par jour, jours vides inclus."""
    jours = []
    curseur = debut
    while curseur < fin:
        jours.append(curseur.date())
        curseur += timedelta(days=1)
    # Au-dela de 90 points le graphique devient illisible : on agrege par semaine.
    par_jour = {j: {"nb": 0, "ca": 0.0} for j in jours}
    for c in commandes:
        j = c.date_creation.date() if c.date_creation else None
        if j in par_jour:
            par_jour[j]["nb"] += 1
            if c.statut == "livree":
                par_jour[j]["ca"] += c.total or 0

    if len(jours) > 90:
        groupes, tampon = [], []
        for j in jours:
            tampon.append(j)
            if len(tampon) == 7:
                groupes.append(tampon); tampon = []
        if tampon:
            groupes.append(tampon)
        return [{"label": g[0].strftime("%d/%m"),
                 "nb": sum(par_jour[x]["nb"] for x in g),
                 "ca": round(sum(par_jour[x]["ca"] for x in g), 3)} for g in groupes]

    return [{"label": j.strftime("%d/%m"), "nb": par_jour[j]["nb"],
             "ca": round(par_jour[j]["ca"], 3)} for j in jours]


def regrouper(commandes, cle, defaut="(non renseigne)"):
    """Regroupe les commandes par un attribut, avec les indicateurs de chaque groupe."""
    groupes = {}
    for c in commandes:
        valeur = (getattr(c, cle, None) or "").strip() or defaut
        groupes.setdefault(valeur, []).append(c)

    lignes = []
    for valeur, lot in groupes.items():
        ind = indicateurs(lot)
        lignes.append({"valeur": valeur, "nb": len(lot), "encaisse": ind["encaisse"],
                       "marge": ind["marge_livree"],
                       "valeur_totale": ind["total_valeur"], "livrees": ind["livrees"],
                       "taux_livraison": ind["taux_livraison"],
                       "part": round(len(lot) / len(commandes) * 100, 1) if commandes else 0})
    return sorted(lignes, key=lambda x: (-x["encaisse"], -x["nb"]))


def contexte_stats(page):
    debut, fin, cle, libelle = periode_demandee()
    commandes = commandes_periode(debut, fin)
    return {
        "page_stats": page, "commandes": commandes,
        "ind": indicateurs(commandes), "serie": serie_journaliere(commandes, debut, fin),
        "periode_cle": cle, "periode_libelle": libelle, "periodes": PERIODES,
        "depuis": debut.strftime("%Y-%m-%d"),
        "jusqua": (fin - timedelta(days=1)).strftime("%Y-%m-%d"),
    }


@app.route("/admin/statistiques")
@connexion_requise
@roles_requis("proprietaire")
def admin_statistiques():
    ctx = contexte_stats("apercu")
    return render_template("admin/stats_apercu.html", **ctx)


@app.route("/admin/statistiques/marketing")
@connexion_requise
@roles_requis("proprietaire")
def admin_stats_marketing():
    ctx = contexte_stats("marketing")
    commandes = ctx["commandes"]

    # Une ligne par combinaison campagne / adset / annonce, comme dans Meta.
    combinaisons = {}
    for c in commandes:
        cle = ((c.utm_campagne or "").strip() or "(inconnue)",
               (c.utm_adset or "").strip() or "(inconnu)",
               (c.utm_annonce or "").strip() or "(inconnue)")
        combinaisons.setdefault(cle, []).append(c)

    campagnes = []
    for (camp, adset, annonce), lot in combinaisons.items():
        ind = indicateurs(lot)
        campagnes.append({"campagne": camp, "adset": adset, "annonce": annonce,
                          "nb": len(lot), "encaisse": ind["encaisse"],
                          "marge": ind["marge_livree"],
                          "valeur_totale": ind["total_valeur"], "livrees": ind["livrees"],
                          "taux_confirmation": ind["taux_confirmation"]})
    campagnes.sort(key=lambda x: (-x["encaisse"], -x["nb"]))

    attribuees = [c for c in commandes if (c.utm_source or c.utm_campagne)]
    return render_template("admin/stats_marketing.html", campagnes=campagnes,
                           sources=regrouper(commandes, "utm_source", "(direct)"),
                           nb_attribuees=len(attribuees),
                           part_attribuee=round(len(attribuees) / len(commandes) * 100, 1) if commandes else 0,
                           **ctx)


@app.route("/admin/statistiques/commandes")
@connexion_requise
@roles_requis("proprietaire")
def admin_stats_commandes():
    ctx = contexte_stats("commandes")
    commandes = ctx["commandes"]

    etapes = [
        ("nouvelle", "Nouvelles"), ("a_confirmer", "A confirmer"), ("confirmee", "Confirmees"),
        ("preparation", "En preparation"), ("expediee", "Expediees"), ("livree", "Livrees"),
        ("annulee", "Annulees"), ("injoignable", "Injoignables"), ("retour", "Retours"),
    ]
    repartition = []
    for statut, libelle in etapes:
        lot = [c for c in commandes if c.statut == statut]
        repartition.append({"statut": statut, "libelle": libelle, "nb": len(lot),
                            "valeur": somme(lot), "marge": marge(lot),
                            "part": round(len(lot) / len(commandes) * 100, 1) if commandes else 0})

    return render_template("admin/stats_commandes.html", repartition=repartition,
                           serie_marge=[{"label": p["label"], "nb": p["nb"], "ca": p["ca"]}
                                        for p in ctx["serie"]], **ctx)


@app.route("/admin/statistiques/equipe")
@connexion_requise
@roles_requis("proprietaire")
def admin_stats_equipe():
    ctx = contexte_stats("equipe")
    debut, fin, _, _ = periode_demandee()

    evenements = HistoriqueCommande.query.filter(
        HistoriqueCommande.date_evenement >= debut,
        HistoriqueCommande.date_evenement < fin).all()

    par_agent = {}
    for e in evenements:
        agent = (e.nom_utilisateur or "").strip() or "(inconnu)"
        fiche = par_agent.setdefault(agent, {
            "nom": agent, "actions": 0, "confirmees": 0, "refusees": 0,
            "expediees": 0, "livrees": 0, "valeur_confirmee": 0.0, "delais": []})
        fiche["actions"] += 1

        if e.nouveau_statut == "confirmee":
            fiche["confirmees"] += 1
            if e.commande:
                fiche["valeur_confirmee"] += e.commande.total or 0
                # Delai entre la commande et sa confirmation, en heures.
                if e.commande.date_creation:
                    ecart = (e.date_evenement - e.commande.date_creation).total_seconds() / 3600
                    if 0 <= ecart < 24 * 30:
                        fiche["delais"].append(ecart)
        elif e.nouveau_statut in STATUTS_REFUSEES:
            fiche["refusees"] += 1
        elif e.nouveau_statut == "expediee":
            fiche["expediees"] += 1
        elif e.nouveau_statut == "livree":
            fiche["livrees"] += 1

    equipe = []
    for fiche in par_agent.values():
        traitees = fiche["confirmees"] + fiche["refusees"]
        fiche["taux_confirmation"] = round(fiche["confirmees"] / traitees * 100, 1) if traitees else 0
        fiche["delai_moyen"] = round(sum(fiche["delais"]) / len(fiche["delais"]), 1) if fiche["delais"] else None
        fiche["valeur_confirmee"] = round(fiche["valeur_confirmee"], 3)
        equipe.append(fiche)
    equipe.sort(key=lambda x: -x["actions"])

    return render_template("admin/stats_equipe.html", equipe=equipe,
                           total_actions=sum(f["actions"] for f in equipe), **ctx)


@app.route("/admin/statistiques/produits")
@connexion_requise
@roles_requis("proprietaire")
def admin_stats_produits():
    ctx = contexte_stats("produits")
    ventes = {}
    for c in ctx["commandes"]:
        if c.statut in STATUTS_REFUSEES:
            continue                      # une commande refusee n'est pas une vente
        for l in c.lignes:
            entree = ventes.setdefault(l.nom_produit or "-", {
                "nom": l.nom_produit or "-", "quantite": 0, "ca": 0.0,
                "livre": 0, "produit_id": l.produit_id})
            entree["quantite"] += l.quantite
            montant = (l.prix_unitaire or 0) * l.quantite
            entree["ca"] += montant
            if c.statut == "livree":
                entree["livre"] += l.quantite

    classement = sorted(ventes.values(), key=lambda x: -x["ca"])
    for e in classement:
        e["ca"] = round(e["ca"], 3)

    return render_template("admin/stats_produits.html", classement=classement,
                           total_articles=sum(e["quantite"] for e in classement), **ctx)


@app.route("/admin/statistiques/livraison")
@connexion_requise
@roles_requis("proprietaire")
def admin_stats_livraison():
    ctx = contexte_stats("livraison")
    return render_template("admin/stats_livraison.html",
                           transporteurs=regrouper(ctx["commandes"], "transporteur", "(non assigne)"),
                           **ctx)


_carte_tunisie = None


def carte_tunisie():
    """Charge la carte une seule fois, au premier affichage."""
    global _carte_tunisie
    if _carte_tunisie is None:
        chemin = os.path.join(BASE_DIR, "static", "carte_tunisie.json")
        try:
            with open(chemin, encoding="utf-8") as f:
                _carte_tunisie = json.load(f)
        except (OSError, ValueError):
            _carte_tunisie = {"largeur": 0, "hauteur": 0, "regions": {}, "attribution": ""}
    return _carte_tunisie


def couleur_taux(taux, sans_donnee):
    """Echelle lisible : rouge quand ca se passe mal, vert quand ca va."""
    if sans_donnee:
        return "#e9ebee"
    if taux < 20: return "#c0392b"
    if taux < 40: return "#e07b39"
    if taux < 60: return "#e0a800"
    if taux < 80: return "#7cb342"
    return "#1e8449"


@app.route("/admin/statistiques/regions")
@connexion_requise
@roles_requis("proprietaire")
def admin_stats_regions():
    ctx = contexte_stats("regions")
    regions = regrouper(ctx["commandes"], "gouvernorat", "(non precise)")
    par_nom = {r["valeur"]: r for r in regions}

    carte = carte_tunisie()
    zones = []
    for nom, trace in sorted(carte.get("regions", {}).items()):
        r = par_nom.get(nom)
        traitees = (r["livrees"] + (r["nb"] - r["livrees"])) if r else 0
        sans_donnee = not r or r["nb"] == 0
        zones.append({
            "nom": nom, "trace": trace,
            "nb": r["nb"] if r else 0,
            "livrees": r["livrees"] if r else 0,
            "taux": r["taux_livraison"] if r else 0,
            "encaisse": r["encaisse"] if r else 0,
            "couleur": couleur_taux(r["taux_livraison"] if r else 0, sans_donnee),
            "sans_donnee": sans_donnee,
        })

    hors_carte = [r["valeur"] for r in regions if r["valeur"] not in carte.get("regions", {})]
    return render_template("admin/stats_regions.html", regions=regions, zones=zones,
                           carte=carte, hors_carte=hors_carte, **ctx)


# ---------------------------------------------------------------------------
# ADMINISTRATION - PRODUITS
# ---------------------------------------------------------------------------

def _adresse_admin(cible):
    """Vrai si l'adresse reste a l'interieur de l'administration.

    Sans ce controle, un « retour » fabrique renverrait l'utilisateur sur
    n'importe quel site apres un enregistrement.
    """
    return bool(cible) and cible.startswith("/admin/") and "://" not in cible \
        and "\\" not in cible


def retour_admin(defaut="admin_produits", surligne=None):
    """Adresse de retour apres un enregistrement, filtres compris.

    Sans elle, modifier un article renvoyait en haut de la liste complete :
    il fallait re-selectionner sa categorie a chaque fiche. On n'accepte
    qu'un chemin interne a l'administration, sinon on ouvrirait une
    redirection vers n'importe quel site.
    """
    cible = (request.args.get("retour") or request.form.get("retour") or "").strip()
    if not _adresse_admin(cible):
        # Repli : la page d'ou part l'envoi. Avec le panneau lateral, le
        # formulaire vit dans la page de la liste, donc le referent porte
        # deja ses filtres. On refuse une page de fiche, qui renverrait le
        # formulaire sur lui-meme.
        venue = urlsplit(request.referrer or "")
        chemin = venue.path + (("?" + venue.query) if venue.query else "")
        # Le repli ne vise qu'une page de liste. Une adresse portant un
        # numero designe une fiche : apres une suppression, y revenir
        # donnerait une erreur 404, l'objet n'existant plus.
        cible = chemin if (_adresse_admin(chemin)
                           and not re.search(r"/\d+(/|$)", venue.path))             else url_for(defaut)
    # Un « modifie » herite du retour precedent ferait doublon, et Flask
    # ne garde que la premiere valeur : le surlignage resterait colle a
    # l'article d'avant. On repart donc d'une adresse nettoyee.
    morceaux = urlsplit(cible)
    parametres = [(c, v) for c, v in parse_qsl(morceaux.query) if c != "modifie"]
    ancre = ""
    if surligne:
        parametres.append(("modifie", str(surligne)))
        ancre = "produit-%s" % surligne
    return urlunsplit(("", "", morceaux.path, urlencode(parametres), ancre))


@app.route("/admin/produits")
@connexion_requise
@roles_requis("proprietaire")
def admin_produits():
    recherche = (request.args.get("q") or "").strip()
    categorie = (request.args.get("categorie") or "").strip()
    statut = (request.args.get("statut") or "").strip()

    requete = Produit.query
    if categorie == "sans":
        requete = requete.filter(Produit.categorie_id.is_(None))
    elif categorie.isdigit():
        # Choisir « Fraise / Mèche » doit montrer ses 43 articles, pas zero :
        # ils sont ranges dans ses sous-rayons, comme en boutique.
        choisie = db.session.get(Categorie, int(categorie))
        ids = ([choisie.id] + [d.id for d in choisie.descendants]
               if choisie else [int(categorie)])
        requete = requete.filter(Produit.categorie_id.in_(ids))

    if statut == "actif":
        requete = requete.filter(Produit.actif == True)
    elif statut == "masque":
        requete = requete.filter(Produit.actif == False)
    elif statut == "rupture":
        requete = requete.filter(Produit.stock <= 0)
    elif statut == "promo":
        requete = requete.filter(Produit.prix_promo.isnot(None))

    stock = valeur_du_stock()
    produits = requete.order_by(Produit.ordre, Produit.date_creation.desc()).all()
    if recherche:
        produits = [p for p in produits if correspond_au_texte(p, recherche)]

    # Range comme la boutique : on retrouve un article la ou on l'a classe.
    # Une recherche ou un filtre traverse les rayons, la liste redevient plate.
    rayons = None if (recherche or categorie or statut) else         grouper_par_rayon(produits, masquees=True)

    return render_template("admin/produits.html", stock=stock, produits=produits,
                           rayons=rayons,
                           recherche=recherche, statut_actif=statut,
                           categorie_active=(int(categorie) if categorie.isdigit() else categorie),
                           categories_filtre=[c for c in categories_a_plat()
                                              if c.actif or c.nb_produits_total],
                           total_produits=Produit.query.count())


@app.route("/admin/produits/nouveau", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_produit_nouveau():
    # Meme ordre que le filtre de la liste : l'arbre, pas l'alphabet.
    categories = categories_a_plat()

    if request.method == "POST":
        image_nom = enregistrer_photo(request.files.get("image"))

        produit = Produit(
            nom=request.form.get("nom", "").strip(),
            nom_ar=(request.form.get("nom_ar") or "").strip() or None,
            reference=request.form.get("reference", "").strip() or None,
            description=request.form.get("description", "").strip(),
            prix=float(request.form.get("prix") or 0),
            prix_promo=float(request.form.get("prix_promo"))
            if request.form.get("prix_promo")
            else None,
            cout=float(request.form.get("cout") or 0),
            stock=int(request.form.get("stock") or 0),
            couleur=request.form.get("couleur", "").strip(),
            queue_mm=nombre_ou_vide(request.form.get("queue_mm")),
            coupe_mm=nombre_ou_vide(request.form.get("coupe_mm")),
            longueur_mm=nombre_ou_vide(request.form.get("longueur_mm")),
            dimensions=request.form.get("dimensions", "").strip(),
            categorie_id=request.form.get("categorie_id") or None,
            actif=bool(request.form.get("actif")),
            vedette=bool(request.form.get("vedette")),
            offre_panier=bool(request.form.get("offre_panier")),
            image=image_nom,
            # Un produit qui vient d'arriver se place en tete de liste : c'est
            # la nouveaute qu'on veut montrer, et qu'on veut retrouver dans
            # l'admin juste apres l'avoir cree. Il reste deplacable ensuite.
            ordre=(db.session.query(db.func.min(Produit.ordre)).scalar() or 0) - 1,
        )

        db.session.add(produit)
        db.session.flush()
        appliquer_champs_avances(produit, request.form)
        appliquer_video(produit, request.form, request.files)
        enregistrer_photos_sup(produit, request.files.getlist("images_sup"))
        enregistrer_onglets(produit, request.form, request.files)
        db.session.commit()
        flash("Produit ajouté avec succès.", "succes")
        return redirect(url_for("admin_produits"))

    return render_template(
        "admin/produit_form.html",
        categories=categories,
        produit=None,
        tous_produits=Produit.query.order_by(Produit.nom).all(),
    )


@app.route("/admin/produits/<int:produit_id>/modifier", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_produit_modifier(produit_id):
    produit = Produit.query.get_or_404(produit_id)
    # Meme ordre que le filtre de la liste : l'arbre, pas l'alphabet.
    categories = categories_a_plat()

    if request.method == "POST":
        nouvelle = enregistrer_photo(request.files.get("image"))
        if nouvelle:
            produit.image = nouvelle
        enregistrer_photos_sup(produit, request.files.getlist("images_sup"))

        produit.nom = request.form.get("nom", "").strip()
        produit.nom_ar = (request.form.get("nom_ar") or "").strip() or None
        appliquer_video(produit, request.form, request.files)
        produit.reference = request.form.get("reference", "").strip() or None
        produit.description = request.form.get("description", "").strip()
        produit.prix = float(request.form.get("prix") or 0)

        prix_promo = request.form.get("prix_promo")
        produit.prix_promo = float(prix_promo) if prix_promo else None
        produit.cout = float(request.form.get("cout") or 0)

        produit.stock = int(request.form.get("stock") or 0)
        produit.couleur = request.form.get("couleur", "").strip()
        produit.queue_mm = nombre_ou_vide(request.form.get("queue_mm"))
        produit.coupe_mm = nombre_ou_vide(request.form.get("coupe_mm"))
        produit.longueur_mm = nombre_ou_vide(request.form.get("longueur_mm"))
        produit.dimensions = request.form.get("dimensions", "").strip()
        produit.categorie_id = request.form.get("categorie_id") or None
        produit.actif = bool(request.form.get("actif"))
        produit.vedette = bool(request.form.get("vedette"))
        produit.offre_panier = bool(request.form.get("offre_panier"))
        appliquer_champs_avances(produit, request.form)
        enregistrer_onglets(produit, request.form, request.files)

        db.session.commit()
        flash("Enregistré : %s" % produit.nom, "succes")
        return redirect(retour_admin(surligne=produit.id))

    return render_template(
        "admin/produit_form.html",
        categories=categories,
        produit=produit,
        tous_produits=Produit.query.filter(Produit.id != produit.id).order_by(Produit.nom).all(),
    )


# ---------------------------------------------------------------------------
# OPTIONS, VARIANTES ET LOTS
#
# Les options decrivent les choix possibles (Couleur, Taille). Le croisement
# de leurs valeurs donne les variantes, chacune avec son prix et son stock.
# Les lots sont des paliers d'achat proposes sur la fiche produit.
# ---------------------------------------------------------------------------

def combinaisons_possibles(produit):
    """Produit cartesien des valeurs de chaque option."""
    listes = [[v.valeur for v in o.valeurs] for o in produit.options if o.valeurs]
    if not listes:
        return []
    return [list(c) for c in itertools.product(*listes)]


def synchroniser_variantes(produit):
    """Cree les combinaisons manquantes, retire celles qui n'existent plus.
    Les prix et stocks deja saisis sont conserves."""
    attendues = combinaisons_possibles(produit)
    cles_attendues = {json.dumps(c, ensure_ascii=False) for c in attendues}

    existantes = {}
    for v in list(produit.variantes):
        cle = json.dumps(v.valeurs, ensure_ascii=False)
        if cle in cles_attendues and cle not in existantes:
            existantes[cle] = v
        else:
            db.session.delete(v)      # option supprimee ou doublon

    for combinaison in attendues:
        cle = json.dumps(combinaison, ensure_ascii=False)
        if cle not in existantes:
            db.session.add(VarianteProduit(produit_id=produit.id, combinaison=cle, stock=0))

    db.session.flush()
    if produit.variantes and not any(v.par_defaut for v in produit.variantes):
        produit.variantes[0].par_defaut = True


def appliquer_options(produit, formulaire):
    """Reecrit les options du produit, puis regenere ses combinaisons."""
    if not formulaire.get("onglet_options"):
        return  # l'onglet n'etait pas dans le formulaire envoye
    noms = formulaire.getlist("option_nom")
    types = formulaire.getlist("option_type")
    valeurs = formulaire.getlist("option_valeurs")

    for o in list(produit.options):
        db.session.delete(o)
    db.session.flush()

    for i, nom in enumerate(noms):
        nom = (nom or "").strip()
        brut = valeurs[i] if i < len(valeurs) else ""
        elements = [v.strip() for v in re.split(r"[,\n;]", brut) if v.strip()]
        if not nom or not elements:
            continue

        option = OptionProduit(produit_id=produit.id, nom=nom[:120],
                               type=(types[i] if i < len(types) else "texte"), ordre=i)
        db.session.add(option)
        db.session.flush()

        for j, element in enumerate(elements[:30]):
            couleur = None
            # "Rouge #c0392b" permet de definir la pastille de couleur.
            trouve = re.search(r"(#[0-9a-fA-F]{3,8})\s*$", element)
            if trouve:
                couleur = trouve.group(1)
                element = element[:trouve.start()].strip()
            db.session.add(ValeurOption(option_id=option.id, valeur=element[:160],
                                        couleur_hex=couleur, ordre=j))

    # Les options viennent d'etre remplacees : la collection en memoire ne le
    # sait pas encore, et les combinaisons seraient calculees sur l'ancienne.
    db.session.flush()
    db.session.expire(produit)
    synchroniser_variantes(produit)
    db.session.flush()
    db.session.expire(produit)


def appliquer_variantes(produit, formulaire, fichiers):
    """Prix, stock et photo de chaque combinaison.

    Les lignes sont reperees par leur libelle et non par un identifiant : le
    navigateur vient peut-etre de les creer, elles n'ont pas encore d'id.
    """
    cles = formulaire.getlist("var_cle")
    if not cles:
        return
    references = formulaire.getlist("var_reference")
    prix = formulaire.getlist("var_prix")
    promos = formulaire.getlist("var_prix_promo")
    couts = formulaire.getlist("var_cout")
    stocks = formulaire.getlist("var_stock")
    images = fichiers.getlist("var_image")
    defaut = formulaire.get("var_defaut")

    # Relecture en base : les combinaisons viennent d'etre creees.
    variantes = VarianteProduit.query.filter_by(produit_id=produit.id).all()
    par_libelle = {v.libelle: v for v in variantes}

    def au_rang(liste, i):
        return liste[i] if i < len(liste) else ""

    for i, cle in enumerate(cles):
        variante = par_libelle.get(cle)
        if variante is None:
            continue
        variante.reference = au_rang(references, i).strip()[:80] or None
        variante.prix = nombre_ou_vide(au_rang(prix, i))
        variante.prix_promo = nombre_ou_vide(au_rang(promos, i))
        variante.cout = nombre_ou_vide(au_rang(couts, i))
        variante.stock = int(nombre_ou_defaut(au_rang(stocks, i), 0))
        variante.par_defaut = (cle == defaut)

        photo = enregistrer_photo(images[i]) if i < len(images) else None
        if photo:
            variante.image = photo

    if variantes and not any(v.par_defaut for v in variantes):
        variantes[0].par_defaut = True


def appliquer_paliers(produit, formulaire):
    """Grille de prix degressifs."""
    if not formulaire.get("onglet_paliers"):
        return
    quantites = formulaire.getlist("palier_quantite")
    prix = formulaire.getlist("palier_prix")

    for p in list(produit.paliers):
        db.session.delete(p)
    db.session.flush()

    vus = set()
    for i, quantite in enumerate(quantites):
        q = int(nombre_ou_defaut(quantite, 0))
        valeur = nombre_ou_vide(prix[i] if i < len(prix) else "")
        if q < 1 or valeur is None or valeur <= 0 or q in vus:
            continue
        vus.add(q)
        db.session.add(PalierPrix(produit_id=produit.id, quantite_min=q, prix=valeur))
    db.session.flush()


def appliquer_lots(produit, formulaire, fichiers):
    """Offres « Achetez 2 », « Pack de 3 »."""
    if not formulaire.get("onglet_lots"):
        return
    noms = formulaire.getlist("lot_nom")
    etiquettes = formulaire.getlist("lot_etiquette")
    quantites = formulaire.getlist("lot_qte")
    prix = formulaire.getlist("lot_prix")
    barres = formulaire.getlist("lot_barre")
    livraisons = formulaire.getlist("lot_livraison")
    couleurs = formulaire.getlist("lot_couleur")
    defaut = formulaire.get("lot_defaut")
    images = fichiers.getlist("lot_image")

    anciennes_images = [l.image for l in produit.lots]
    for l in list(produit.lots):
        db.session.delete(l)
    db.session.flush()

    for i, nom in enumerate(noms):
        nom = (nom or "").strip()
        if not nom:
            continue
        quantite = int(nombre_ou_defaut(quantites[i] if i < len(quantites) else 1, 1)) or 1
        photo = enregistrer_photo(images[i]) if i < len(images) else None

        db.session.add(LotProduit(
            produit_id=produit.id, nom=nom[:120],
            etiquette=(etiquettes[i] if i < len(etiquettes) else "").strip()[:160],
            quantite=max(1, quantite),
            prix=nombre_ou_defaut(prix[i] if i < len(prix) else 0, 0),
            prix_barre=nombre_ou_vide(barres[i] if i < len(barres) else ""),
            prix_livraison=nombre_ou_vide(livraisons[i] if i < len(livraisons) else ""),
            image=photo or (anciennes_images[i] if i < len(anciennes_images) else None),
            couleur_badge=(couleurs[i] if i < len(couleurs) else "vert"),
            par_defaut=(str(i) == defaut), ordre=i))

    db.session.flush()
    lots = LotProduit.query.filter_by(produit_id=produit.id).order_by(LotProduit.ordre).all()
    if lots and not any(l.par_defaut for l in lots):
        lots[0].par_defaut = True


def enregistrer_onglets(produit, formulaire, fichiers):
    """Toute la fiche part en une fois : l'ordre compte.

    Les options sont traitees en premier parce qu'elles creent et suppriment
    les combinaisons ; les lignes de variantes envoyees se rattachent ensuite.
    """
    appliquer_options(produit, formulaire)
    appliquer_variantes(produit, formulaire, fichiers)
    appliquer_paliers(produit, formulaire)
    appliquer_lots(produit, formulaire, fichiers)


# ---------------------------------------------------------------------------
# PHOTOS D'UN PRODUIT
#
# Toutes les photos forment une seule liste ordonnee. La premiere sert de
# photo principale (vignettes, flux Meta, partages) ; les suivantes vont
# dans la galerie. Reordonner revient donc a choisir la photo principale.
# ---------------------------------------------------------------------------

def photos_produit(produit):
    """Liste ordonnee des noms de fichiers, la principale en tete."""
    liste = [produit.image] if produit.image else []
    liste += [i.fichier for i in produit.images_sup if i.fichier and i.fichier != produit.image]
    return liste


def appliquer_ordre_photos(produit, fichiers, autorises=None):
    """Reecrit la photo principale et la galerie a partir d'une liste ordonnee.
    `autorises` permet d'inclure des fichiers tout juste televerses, qui ne
    font pas encore partie des photos connues du produit."""
    connus = set(photos_produit(produit)) | set(autorises or [])
    retenus = []
    for f in fichiers:
        if f in connus and f not in retenus:
            retenus.append(f)

    produit.image = retenus[0] if retenus else None
    for image in list(produit.images_sup):
        db.session.delete(image)
    db.session.flush()

    for position, fichier in enumerate(retenus[1:], start=1):
        db.session.add(ImageProduit(produit_id=produit.id, fichier=fichier, ordre=position))
    return retenus


@app.route("/admin/reordonner/<quoi>", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_reordonner(quoi):
    """Enregistre l'ordre choisi par glisser-deposer dans l'administration."""
    modeles = {"produits": Produit, "categories": Categorie}
    modele = modeles.get(quoi)
    if modele is None:
        return {"ok": False, "erreur": "type inconnu"}, 400

    demandes = (request.get_json(silent=True) or {}).get("ordre") or []
    identifiants = [int(x) for x in demandes if str(x).isdigit()]
    if not identifiants:
        return {"ok": False, "erreur": "liste vide"}, 400

    # On ne touche qu'aux lignes reellement envoyees. Plutot que de renumeroter
    # de 0 a n (ce qui entrerait en collision avec les lignes non envoyees), on
    # reutilise les positions que ces lignes occupaient deja, redistribuees
    # dans le nouvel ordre.
    trouves = {o.id: o for o in modele.query.filter(modele.id.in_(identifiants)).all()}
    ordonnes = [trouves[i] for i in identifiants if i in trouves]
    positions = sorted((o.ordre or 0) for o in ordonnes)
    for objet, position in zip(ordonnes, positions):
        objet.ordre = position
    db.session.commit()
    return {"ok": True, "nombre": len(trouves)}, 200


@app.route("/admin/produits/<int:produit_id>/photos/ordre", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_photos_ordre(produit_id):
    produit = Produit.query.get_or_404(produit_id)
    fichiers = (request.get_json(silent=True) or {}).get("ordre") or []
    retenus = appliquer_ordre_photos(produit, fichiers)
    db.session.commit()
    return {"ok": True, "nombre": len(retenus), "principale": produit.image or ""}, 200


@app.route("/admin/produits/<int:produit_id>/photos/supprimer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_photo_supprimer(produit_id):
    produit = Produit.query.get_or_404(produit_id)
    fichier = (request.get_json(silent=True) or {}).get("fichier") or ""

    restantes = [f for f in photos_produit(produit) if f != fichier]
    appliquer_ordre_photos(produit, restantes)
    db.session.commit()

    # Le fichier n'est efface du disque que si plus rien ne s'en sert.
    encore_utilise = (
        Produit.query.filter(Produit.image == fichier).count()
        + ImageProduit.query.filter(ImageProduit.fichier == fichier).count()
        + VarianteProduit.query.filter(VarianteProduit.image == fichier).count()
        + LotProduit.query.filter(LotProduit.image == fichier).count()
        + Categorie.query.filter(Categorie.image == fichier).count())
    if not encore_utilise:
        chemin = os.path.join(app.config["UPLOAD_FOLDER"], fichier)
        if os.path.exists(chemin):
            os.remove(chemin)

    return {"ok": True, "restantes": len(restantes), "principale": produit.image or ""}, 200


@app.route("/admin/produits/<int:produit_id>/photos/ajouter", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_photos_ajouter(produit_id):
    produit = Produit.query.get_or_404(produit_id)
    ajoutees = []

    for fichier in request.files.getlist("photos"):
        nom = enregistrer_photo(fichier)
        if nom:
            ajoutees.append(nom)

    if ajoutees:
        appliquer_ordre_photos(produit, photos_produit(produit) + ajoutees,
                               autorises=ajoutees)
        db.session.commit()

    return {"ok": True, "ajoutees": len(ajoutees),
            "photos": [{"fichier": f,
                        "url": url_for("static", filename="img/produits/" + f)}
                       for f in photos_produit(produit)]}, 200


@app.route("/admin/produits/<int:produit_id>/supprimer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_produit_supprimer(produit_id):
    produit = Produit.query.get_or_404(produit_id)
    db.session.delete(produit)
    db.session.commit()
    flash("Produit supprimé.", "succes")
    return redirect(retour_admin())


# ---------------------------------------------------------------------------
# ADMINISTRATION - CATEGORIES
#
# Les categories peuvent s'emboiter sur un niveau : une categorie parente
# regroupe des sous-categories. Chacune porte une banniere, un texte et son
# propre referencement.
# ---------------------------------------------------------------------------

def parents_possibles(categorie=None):
    """Categories pouvant accueillir une sous-categorie, dans l'ordre du menu."""
    resultat = []
    for racine in (Categorie.query.filter_by(parent_id=None)
                   .order_by(Categorie.ordre, Categorie.nom).all()):
        resultat.append(racine)
        resultat.extend(racine.enfants)
    interdits = set()
    if categorie is not None and categorie.id is not None:
        interdits = {categorie.id} | {d.id for d in categorie.descendants}
    return [c for c in resultat
            if c.id not in interdits and c.niveau < PROFONDEUR_MAX - 1]


def parent_autorise(categorie, parent_id):
    """Identifiant du parent accepte, ou None.

    Trois refus : se prendre soi-meme, descendre sous l'une de ses propres
    sous-categories (ce qui ferait une boucle infinie a l'affichage), et
    depasser la profondeur prevue.
    """
    if not parent_id or not str(parent_id).isdigit():
        return None
    candidat = db.session.get(Categorie, int(parent_id))
    if candidat is None:
        return None
    if categorie is not None and categorie.id is not None:
        if candidat.id == categorie.id:
            return None
        if candidat.id in {d.id for d in categorie.descendants}:
            return None
        # Le sous-arbre deplace doit tenir dans la profondeur restante.
        hauteur = max([d.niveau for d in categorie.descendants] or [categorie.niveau])
        epaisseur = hauteur - categorie.niveau
        if candidat.niveau + 1 + epaisseur > PROFONDEUR_MAX - 1:
            return None
    elif candidat.niveau + 1 > PROFONDEUR_MAX - 1:
        return None
    return candidat.id


def categories_a_plat():
    """Toutes les categories dans l'ordre de l'arbre, parente avant enfants.

    Trie par nom, une liste de categories est illisible des que l'arbre range
    par type d'outil : « CMT » y figure cinq fois sans rien pour les
    distinguer. On garde donc l'ordre du menu et on affichera le chemin.
    """
    suite = []

    def empiler(categorie):
        suite.append(categorie)
        for enfant in sorted(categorie.enfants, key=lambda c: (c.ordre or 0, c.nom)):
            empiler(enfant)

    for racine in (Categorie.query.filter_by(parent_id=None)
                   .order_by(Categorie.ordre, Categorie.nom).all()):
        empiler(racine)
    return suite


def slug_categorie(nom, categorie_id=None):
    base = re.sub(r"[^a-z0-9]+", "-", sans_accents_simple(nom)).strip("-")[:120] or "categorie"
    candidat, n = base, 2
    while True:
        existant = Categorie.query.filter_by(slug=candidat).first()
        if not existant or existant.id == categorie_id:
            return candidat
        candidat = "%s-%s" % (base, n)
        n += 1


def appliquer_champs_categorie(categorie, formulaire, fichiers):
    categorie.nom = (formulaire.get("nom") or "").strip()[:120]
    categorie.nom_ar = (formulaire.get("nom_ar") or "").strip()[:120] or None
    categorie.description = (formulaire.get("description") or "").strip()
    categorie.meta_titre = (formulaire.get("meta_titre") or "").strip()[:200]
    categorie.meta_description = (formulaire.get("meta_description") or "").strip()[:320]
    categorie.actif = bool(formulaire.get("actif"))

    categorie.parent_id = parent_autorise(categorie, formulaire.get("parent_id"))

    saisi = (formulaire.get("slug") or "").strip()
    categorie.slug = slug_categorie(saisi or categorie.nom, categorie.id)

    banniere = enregistrer_photo(fichiers.get("image"))
    if banniere:
        categorie.image = banniere


# Transporteurs pour lesquels nous savons creer une expedition et recuperer
# leur bordereau. Les autres restent en saisie manuelle.
TRANSPORTEURS_AVEC_API = ("First Delivery",)


def bordereau_valide(commande):
    """Vrai si le bordereau stocke correspond bien au transporteur actuel.

    Les commandes anterieures a cette colonne n'ont pas d'emetteur note : on
    suppose alors que le bordereau est celui du transporteur en place.
    """
    if not commande.lien_bordereau:
        return False
    # Avant cette colonne, seul First Delivery savait emettre un bordereau :
    # c'est donc lui l'auteur de tous les liens deja stockes.
    emetteur = commande.transporteur_bordereau or "First Delivery"
    return emetteur == commande.transporteur


def oublier_expedition(commande):
    """Efface le bordereau et le suivi laisses par le transporteur precedent.

    Les garder ferait imprimer l'etiquette de l'ancien livreur, avec son code
    a barre : le colis partirait chez le mauvais transporteur.
    """
    commande.lien_bordereau = None
    commande.transporteur_bordereau = None
    commande.numero_suivi = None


def peut_etiqueter(commande):
    """Vrai si on peut encore demander son bordereau au transporteur."""
    return (commande.transporteur in TRANSPORTEURS_AVEC_API
            and not bordereau_valide(commande)
            and bool(jeton_first_delivery()))


@app.route("/admin/commandes/imprimer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire", "commandes", "livraison")
def admin_imprimer_bordereaux():
    """Un seul clic : expedition creee si necessaire, puis bordereau ouvert.

    Le bordereau du transporteur prime toujours ; on ne retombe sur notre
    propre bon que pour un transporteur qui n'en fournit pas.
    """
    demandes = [int(x) for x in request.form.getlist("ids") if x.isdigit()]
    if not demandes:
        flash("Aucune commande selectionnee.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    commandes = Commande.query.filter(Commande.id.in_(demandes),
                                      Commande.supprimee_le.is_(None)).all()
    if not commandes:
        flash("Ces commandes n'existent plus.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    if request.form.get("grouper"):
        # Les commandes portant les memes articles se suivent : on prepare
        # une serie de colis identiques sans revenir sans cesse au meme bac.
        def articles(commande):
            return sorted(l.produit_id or 0 for l in commande.lignes)

        commandes.sort(key=lambda c: (articles(c), c.id))

    # 1. On demande au transporteur les bordereaux qui manquent.
    echecs = []
    for commande in commandes:
        if peut_etiqueter(commande):
            souci = creer_expedition_first(commande)
            if souci:
                echecs.append("%s : %s" % (commande.numero, souci))
    if request.form.get("marquer"):
        for commande in commandes:
            commande.imprimee_le = datetime.now()
    db.session.commit()

    for message in echecs[:4]:
        flash("First Delivery, %s" % message, "erreur")

    avec_bordereau = [c for c in commandes if bordereau_valide(c)]
    sans_bordereau = [c for c in commandes if not bordereau_valide(c)]

    # 2. Un seul bordereau : on l'ouvre directement, sans page intermediaire.
    if len(avec_bordereau) == 1 and not sans_bordereau:
        return redirect(avec_bordereau[0].lien_bordereau)

    # 3. Aucun transporteur ne fournit de bordereau : notre bon fait l'affaire.
    if not avec_bordereau:
        return redirect(url_for("admin_bons_groupes",
                                ids=",".join(str(c.id) for c in sans_bordereau)))

    # 4. Plusieurs : une page qui les ouvre les uns apres les autres.
    return render_template("admin/impression_bordereaux.html",
                           avec_bordereau=avec_bordereau,
                           sans_bordereau=sans_bordereau)


@app.route("/admin/commandes/bordereau-remise")
@connexion_requise
@roles_requis("proprietaire", "commandes", "livraison")
def admin_bordereau_remise():
    """Feuille recapitulative a faire signer au livreur."""
    demandes = [x for x in (request.args.get("ids") or "").split(",") if x.isdigit()]
    if not demandes:
        flash("Aucune commande selectionnee.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    trouvees = {c.id: c for c in Commande.query.filter(
        Commande.id.in_([int(x) for x in demandes])).all()}
    commandes = [trouvees[int(x)] for x in demandes if int(x) in trouvees]
    if not commandes:
        flash("Ces commandes n'existent plus.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    if request.args.get("marquer") == "1":
        for commande in commandes:
            commande.imprimee_le = datetime.now()
        db.session.commit()

    return render_template("admin/bordereau_remise.html",
                           commandes=commandes,
                           params=ParametreBoutique.query.first(),
                           total=round(sum(c.total or 0 for c in commandes), 3),
                           colis=len(commandes),
                           aujourdhui=datetime.now())


@app.route("/admin/commandes/bons-groupes")
@connexion_requise
@roles_requis("proprietaire", "commandes", "livraison")
def admin_bons_groupes():
    """Plusieurs bons de livraison sur une seule page, prets a imprimer."""
    demandes = [x for x in (request.args.get("ids") or "").split(",") if x.isdigit()]
    if not demandes:
        flash("Aucune commande selectionnee.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    trouvees = {c.id: c for c in Commande.query.filter(
        Commande.id.in_([int(x) for x in demandes])).all()}
    # On respecte l'ordre de selection.
    commandes = [trouvees[int(x)] for x in demandes if int(x) in trouvees]
    if not commandes:
        flash("Ces commandes n'existent plus.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    params = ParametreBoutique.query.first()
    taux = (params.taux_tva or 0) if params else 0
    ids = [l.produit_id for c in commandes for l in c.lignes if l.produit_id]
    produits = {p.id: p for p in Produit.query.filter(Produit.id.in_(ids)).all()} if ids else {}

    # Les commandes dont le transporteur a fourni son propre bordereau sont
    # mises a part : on ne peut pas fusionner un PDF externe dans notre page,
    # mais on affiche un bouton direct pour chacune.
    externes = [c for c in commandes if bordereau_valide(c)]
    commandes = [c for c in commandes if not bordereau_valide(c)]

    # Marquage : on note l'impression pour pouvoir filtrer plus tard.
    if request.args.get("marquer") == "1":
        for commande in commandes:
            commande.imprimee_le = datetime.now()
        db.session.commit()

    bons = []
    for commande in commandes:
        reference = commande.numero_suivi or commande.numero
        bons.append({
            "commande": commande, "reference": reference,
            "tva": round((commande.total or 0) * taux / (100.0 + taux), 3) if taux else 0,
            "code_barre": codebarres.svg(reference, hauteur=58),
            "code_barre_large": codebarres.svg(reference, hauteur=70, largeur_module=3),
        })

    return render_template("admin/bons_groupes.html", bons=bons, params=params,
                           externes=externes,
                           taux_tva=taux, produits_par_id=produits)


MOT_DE_PASSE_USINE = "ChangeMoi123!"


def mot_de_passe_usine():
    """Vrai si un proprietaire utilise encore le mot de passe livre d'origine.

    Il est ecrit dans le code et connu de quiconque a vu ce projet : en ligne,
    il vaut porte ouverte sur les commandes et les clients.
    """
    if not session.get("user_id"):
        return False
    try:
        for u in Utilisateur.query.filter_by(role="proprietaire", actif=True):
            if check_password_hash(u.mot_de_passe_hash, MOT_DE_PASSE_USINE):
                return True
    except Exception:
        return False
    return False


@app.template_filter("cotes_groupees")
def cotes_groupees(nom):
    """Rend le groupe de cotes insecable, pour qu'il tienne sur une ligne."""
    def souder(trouve):
        # L'espace qui precede le tiret suivant reste normal : la ligne peut
        # se couper la, entre les cotes et la reference.
        bloc = trouve.group(0)
        return bloc.rstrip().replace(" ", " ") + bloc[len(bloc.rstrip()):]
    # Du mot « queue » (ou « ساق ») jusqu'au tiret suivant.
    return re.sub(r"(?:queue|ساق)[^—]*", souder, nom or "")


@app.context_processor
def gabarit_du_panneau():
    """Choisit le gabarit parent des pages d'administration.

    Demandee avec « ?panneau=1 », une page d'edition se rend sans le cadre :
    elle est alors glissee dans le panneau lateral de la liste d'origine.
    """
    dans_panneau = bool(request.args.get("panneau"))
    return {"panneau": dans_panneau,
            "mot_de_passe_usine": mot_de_passe_usine(),
            "rubriques_droits": RUBRIQUES,
            "statuts_commande": STATUTS_COMMANDE,
            "gabarit_admin": "admin/base_panneau.html" if dans_panneau
                             else "admin/base_admin.html"}


@app.route("/admin/commandes/<int:commande_id>/modifier", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire", "commandes")
def admin_commande_modifier(commande_id):
    """Modifie une commande : client, articles, livraison, statut."""
    commande = Commande.query.get(commande_id)
    if commande is None:
        flash("Cette commande n'existe plus.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    if request.method == "POST":
        formulaire = request.form
        ancien_statut = commande.statut

        commande.nom_client = (formulaire.get("nom_client") or "").strip()[:150]
        commande.telephone = (formulaire.get("telephone") or "").strip()[:40]
        commande.telephone2 = (formulaire.get("telephone2") or "").strip()[:40] or None
        commande.email = (formulaire.get("email") or "").strip()[:150] or None
        commande.gouvernorat = (formulaire.get("gouvernorat") or "").strip()
        commande.ville = (formulaire.get("ville") or "").strip()
        commande.adresse = (formulaire.get("adresse") or "").strip()
        commande.commentaire = (formulaire.get("commentaire") or "").strip()
        commande.note_privee = (formulaire.get("note_privee") or "").strip() or None
        nouveau_transporteur = (formulaire.get("transporteur") or "").strip() or None
        suivi_saisi = (formulaire.get("numero_suivi") or "").strip() or None
        if nouveau_transporteur != commande.transporteur:
            # Le suivi affiche etait celui de l'ancien livreur : on ne le
            # reporte pas sur le nouveau, sauf si l'operateur l'a retape.
            reporte = suivi_saisi if suivi_saisi != commande.numero_suivi else None
            oublier_expedition(commande)
            suivi_saisi = reporte
        commande.transporteur = nouveau_transporteur
        commande.numero_suivi = suivi_saisi

        # --- Lignes existantes : quantite, prix, suppression ---
        for ligne in list(commande.lignes):
            if formulaire.get("retirer_%s" % ligne.id):
                # L'article revient en stock : il n'a jamais quitte le magasin.
                produit = db.session.get(Produit, ligne.produit_id)
                if produit is not None and commande.statut != "livree":
                    produit.stock = (produit.stock or 0) + (ligne.quantite or 0)
                db.session.delete(ligne)
                continue

            nouvelle = nombre_ou_defaut(formulaire.get("quantite_%s" % ligne.id), ligne.quantite)
            nouvelle = max(1, int(nouvelle))
            ecart = nouvelle - (ligne.quantite or 0)
            if ecart:
                produit = db.session.get(Produit, ligne.produit_id)
                if produit is not None and commande.statut != "livree":
                    # On ajoute au panier : autant de moins en stock, et l'inverse.
                    produit.stock = (produit.stock or 0) - ecart
            ligne.quantite = nouvelle
            ligne.prix_unitaire = nombre_ou_defaut(formulaire.get("prix_%s" % ligne.id),
                                                   ligne.prix_unitaire)

        # --- Ajout d'un article ---
        ajout = formulaire.get("ajouter_produit") or ""
        if ajout.isdigit():
            produit = db.session.get(Produit, int(ajout))
            if produit is not None:
                quantite = max(1, int(nombre_ou_defaut(formulaire.get("ajouter_quantite"), 1)))
                db.session.add(LigneCommande(
                    commande_id=commande.id, produit_id=produit.id,
                    nom_produit=produit.nom, prix_unitaire=produit.prix_affiche or 0,
                    cout_unitaire=produit.cout or 0, quantite=quantite))
                if commande.statut != "livree":
                    produit.stock = (produit.stock or 0) - quantite
                db.session.flush()

        # --- Livraison et total ---
        commande.frais_livraison = nombre_ou_defaut(formulaire.get("frais_livraison"),
                                                    commande.frais_livraison or 0)
        db.session.flush()
        # On relit les lignes en base : apres un ajout ou un retrait, la
        # collection « commande.lignes » garde l'etat precedent et le total
        # se retrouvait decale d'une modification.
        lignes = LigneCommande.query.filter_by(commande_id=commande.id).all()
        articles = sum((l.prix_unitaire or 0) * (l.quantite or 0) for l in lignes)
        commande.total = round(articles + (commande.frais_livraison or 0)
                               - (commande.montant_reduction or 0), 3)

        nouveau_statut = (formulaire.get("statut") or commande.statut).strip()
        if nouveau_statut and nouveau_statut != ancien_statut:
            commande.statut = nouveau_statut
            enregistrer_historique(commande, ancien_statut, nouveau_statut)

        db.session.commit()
        flash("Commande %s enregistree." % commande.numero, "succes")
        # On revient a la liste : c'est de la qu'on repart pour traiter la suivante.
        # « Enregistrer et continuer » reste possible via le bouton dedie.
        if request.form.get("rester"):
            return redirect(url_for("admin_commande_modifier", commande_id=commande.id))
        return redirect(retour_admin("admin_commandes"))

    return render_template("admin/commande_form.html",
                           commande=commande,
                           transporteurs_objets=transporteurs_actifs(),
                           gouvernorats_json=GOUVERNORATS_TUNISIE,
                           produits=Produit.query.filter_by(actif=True)
                                    .order_by(Produit.nom).all(),
                           produits_par_id={p.id: p for p in Produit.query.filter(
                               Produit.id.in_([l.produit_id for l in commande.lignes
                                               if l.produit_id])).all()}
                           if commande.lignes else {})


@app.route("/admin/commandes/<int:commande_id>/bon-livraison")
@connexion_requise
@roles_requis("proprietaire", "commandes", "livraison")
def admin_bon_livraison(commande_id):
    """Bon de livraison a imprimer et a coller sur le colis."""
    commande = Commande.query.get(commande_id)
    if commande is None:
        flash("Cette commande n'existe plus.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    params = ParametreBoutique.query.first()
    # Le numero du transporteur fait foi ; sinon on imprime notre propre numero.
    reference = commande.numero_suivi or commande.numero
    taux = (params.taux_tva or 0) if params else 0
    # Le total est TTC : on en extrait la part de TVA.
    tva = round((commande.total or 0) * taux / (100.0 + taux), 3) if taux else 0

    return render_template("admin/bon_livraison.html",
                           commande=commande, params=params,
                           reference=reference, tva=tva, taux_tva=taux,
                           code_barre=codebarres.svg(reference, hauteur=58),
                           code_barre_large=codebarres.svg(reference, hauteur=70,
                                                           largeur_module=3),
                           transporteur=transporteur_par_nom(commande.transporteur),
                           produits_par_id={p.id: p for p in Produit.query.filter(
                               Produit.id.in_([l.produit_id for l in commande.lignes
                                               if l.produit_id])).all()}
                           if commande.lignes else {})



def creer_expedition_first(commande):
    """Cree l'expedition chez First Delivery.

    Retourne None si tout s'est bien passe, sinon un message d'erreur.
    Ne valide pas la transaction : l'appelant decide quand enregistrer.
    """
    locality_id = trouver_locality_id(commande.gouvernorat, commande.ville)
    if not locality_id:
        proches = localites_proches(commande.gouvernorat)
        return ("localite introuvable pour %s, %s%s"
                % (commande.ville or "?", commande.gouvernorat or "?",
                   (" (chez eux : %s)" % ", ".join(proches)) if proches else ""))

    articles = sum(l.quantite or 0 for l in commande.lignes) or 1
    designation = " | ".join("%s x%s" % (l.nom_produit, l.quantite)
                             for l in commande.lignes)[:250] or "Commande"
    premier = commande.lignes[0].nom_produit if commande.lignes else "Article"

    charge = {
        "Client": {
            "nom": (commande.nom_client or "")[:80],
            "gouvernerat": commande.gouvernorat or "",
            "ville": commande.ville or "",
            "adresse": (commande.adresse or commande.ville or "-")[:200],
            "telephone": telephone_first_delivery(commande.telephone),
            "telephone2": "",
            "locality_id": locality_id,
        },
        "Produit": {
            "prix": round(min(commande.total or 0, 999), 2),
            "designation": designation,
            "nombreArticle": articles,
            "commentaire": (commande.commentaire or "")[:250],
            "article": (premier or "Article")[:80],
            "nombreEchange": 0,
            "estFragile": "non",
            "ouvrirColis": "non",
        },
    }

    try:
        reponse = requests.post(FIRST_DELIVERY_BASE_URL + "/create", json=charge,
                                headers=entetes_first_delivery(), timeout=30)
    except Exception as erreur:
        return "impossible de joindre First Delivery (%s)" % erreur

    resultat, souci = lire_reponse_first(reponse)
    if souci:
        return souci
    if reponse.status_code >= 400:
        return "refus de First Delivery (%s) : %s" % (reponse.status_code,
                                                      (resultat or {}).get("message", ""))

    contenu = resultat.get("result") or resultat.get("data") or resultat
    code_barre = (contenu.get("barCode") or contenu.get("code_barre")
                  or contenu.get("barcode"))
    if not code_barre:
        return "reponse sans code a barre : %s" % resultat

    ancien = commande.statut
    commande.transporteur = "First Delivery"
    commande.numero_suivi = code_barre
    lien = (contenu.get("link") or contenu.get("pdfUrl")
            or contenu.get("lien_bordereau") or "")
    if lien.startswith("/"):
        lien = FIRST_DELIVERY_BASE_URL.rsplit("/api/", 1)[0] + lien
    commande.lien_bordereau = lien
    commande.transporteur_bordereau = "First Delivery"
    commande.statut = "expediee"
    enregistrer_historique(commande, ancien, "expediee")
    return None


@app.route("/admin/commandes/expedier-groupe", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire", "livraison")
def admin_expedier_groupe():
    """Cree les expeditions manquantes chez First Delivery.

    Chaque envoi cree une vraie expedition, facturee par le transporteur :
    on ignore donc celles qui en ont deja une, pour ne pas faire de doublon.
    """
    demandes = [int(x) for x in request.form.getlist("ids") if x.isdigit()]
    if not demandes:
        flash("Aucune commande selectionnee.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    if not jeton_first_delivery():
        flash("Cle First Delivery absente : renseigne-la dans Transporteurs.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    faites, ignorees, echecs = 0, 0, []
    for commande in Commande.query.filter(Commande.id.in_(demandes),
                                          Commande.supprimee_le.is_(None)).all():
        if bordereau_valide(commande) or commande.numero_suivi:
            ignorees += 1
            continue
        if commande.transporteur not in TRANSPORTEURS_AVEC_API:
            ignorees += 1
            continue

        souci = creer_expedition_first(commande)
        if souci:
            echecs.append("%s : %s" % (commande.numero, souci))
        else:
            faites += 1

    db.session.commit()

    if faites:
        flash("%s expedition(s) creee(s) chez First Delivery.%s"
              % (faites, (" %s deja expediee(s), ignoree(s)." % ignorees) if ignorees else ""),
              "succes")
    elif ignorees and not echecs:
        flash("Rien a faire : ces commandes ont deja leur bordereau.", "succes")
    for message in echecs[:5]:
        flash(message, "erreur")
    return redirect(retour_admin("admin_commandes"))


@app.route("/admin/commandes/modifier-groupe", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire", "commandes")
def admin_commandes_modifier_groupe():
    """Applique un statut, un transporteur ou une note a plusieurs commandes."""
    demandes = [int(x) for x in request.form.getlist("ids") if x.isdigit()]
    if not demandes:
        flash("Aucune commande selectionnee.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    statut = (request.form.get("statut") or "").strip()
    transporteur = (request.form.get("transporteur") or "").strip()
    note = (request.form.get("note_privee") or "").strip()
    if not statut and not transporteur and not note:
        flash("Rien a modifier : choisis un statut, un transporteur ou une note.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    touchees = 0
    for commande in Commande.query.filter(Commande.id.in_(demandes),
                                          Commande.supprimee_le.is_(None)).all():
        if statut and statut != commande.statut:
            ancien = commande.statut
            commande.statut = statut
            enregistrer_historique(commande, ancien, statut)
        if transporteur:
            # « aucun » retire le transporteur au lieu d'en poser un.
            voulu = None if transporteur == "aucun" else transporteur
            if voulu != commande.transporteur:
                oublier_expedition(commande)
            commande.transporteur = voulu
        if note:
            # On ajoute a la suite plutot que d'ecraser une note existante.
            commande.note_privee = ((commande.note_privee or "") + "\n" + note).strip()
        touchees += 1
    db.session.commit()

    flash("%s commande(s) modifiee(s)." % touchees, "succes")
    return redirect(retour_admin("admin_commandes"))


@app.route("/admin/commandes/supprimer-groupe", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_commandes_supprimer_groupe():
    """Supprime plusieurs commandes d'un coup, en rendant les stocks."""
    demandes = [int(x) for x in request.form.getlist("ids") if x.isdigit()]
    if not demandes:
        flash("Aucune commande selectionnee.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    supprimees = rendus = 0
    for commande in Commande.query.filter(Commande.id.in_(demandes),
                                          Commande.supprimee_le.is_(None)).all():
        rendus += rendre_stock(commande)
        commande.supprimee_le = datetime.now()
        supprimees += 1
    db.session.commit()
    flash("%s commande(s) mise(s) a la corbeille.%s"
          % (supprimees, (" %s article(s) remis en stock." % rendus) if rendus else ""),
          "succes")
    return redirect(retour_admin("admin_commandes"))



def rendre_stock(commande):
    """Remet en stock les articles d'une commande non livree."""
    if commande.statut == "livree":
        return 0
    rendus = 0
    for ligne in commande.lignes:
        produit = db.session.get(Produit, ligne.produit_id)
        if produit is not None:
            produit.stock = (produit.stock or 0) + (ligne.quantite or 0)
            rendus += ligne.quantite or 0
    return rendus


def reprendre_stock(commande):
    """Retire de nouveau du stock les articles d'une commande restauree."""
    if commande.statut == "livree":
        return 0
    repris = 0
    for ligne in commande.lignes:
        produit = db.session.get(Produit, ligne.produit_id)
        if produit is not None:
            produit.stock = (produit.stock or 0) - (ligne.quantite or 0)
            repris += ligne.quantite or 0
    return repris


def effacer_definitivement(commande):
    for ligne in list(commande.lignes):
        db.session.delete(ligne)
    for evenement in list(commande.historique):
        db.session.delete(evenement)
    db.session.delete(commande)


@app.route("/admin/commandes/<int:commande_id>/restaurer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_commande_restaurer(commande_id):
    commande = Commande.query.get(commande_id)
    if commande is None or commande.supprimee_le is None:
        flash("Commande introuvable dans la corbeille.", "erreur")
        return redirect(url_for("admin_commandes", corbeille=1))
    repris = reprendre_stock(commande)
    commande.supprimee_le = None
    db.session.commit()
    flash("Commande %s restauree.%s" % (commande.numero,
          (" %s article(s) repris sur le stock." % repris) if repris else ""), "succes")
    return redirect(retour_admin("admin_commandes"))


@app.route("/admin/commandes/<int:commande_id>/effacer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_commande_effacer(commande_id):
    """Suppression definitive, possible seulement depuis la corbeille."""
    commande = Commande.query.get(commande_id)
    if commande is None or commande.supprimee_le is None:
        flash("Cette commande n'est pas dans la corbeille.", "erreur")
        return redirect(url_for("admin_commandes", corbeille=1))
    numero = commande.numero
    effacer_definitivement(commande)
    db.session.commit()
    flash("Commande %s effacee definitivement." % numero, "succes")
    return redirect(url_for("admin_commandes", corbeille=1))


@app.route("/admin/commandes/<int:commande_id>/supprimer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_commande_supprimer(commande_id):
    """Supprime une commande definitivement, en rendant le stock si besoin."""
    commande = Commande.query.get(commande_id)
    if commande is None:
        flash("Cette commande n'existe plus.", "erreur")
        return redirect(retour_admin("admin_commandes"))

    # Mise de cote plutot qu'effacement : une erreur reste rattrapable.
    rendus = rendre_stock(commande)
    commande.supprimee_le = datetime.now()
    db.session.commit()

    flash("Commande %s mise a la corbeille.%s Tu peux la restaurer."
          % (commande.numero,
             (" %s article(s) remis en stock." % rendus) if rendus else ""),
          "succes")
    return redirect(retour_admin("admin_commandes"))


@app.route("/admin/transporteurs", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_transporteurs():
    if request.method == "POST":
        # Cette page ne porte plus que l'interrupteur de chaque transporteur ;
        # identifiants, lien de suivi et logo se reglent sur sa page dediee.
        incomplets = []
        for t in Transporteur.query.all():
            etait_actif = t.actif
            t.actif = bool(request.form.get("actif_%s" % t.id))
            if t.actif and not etait_actif and not t.sait_etiqueter:
                incomplets.append(t)

        nouveau = (request.form.get("nouveau_nom") or "").strip()
        if nouveau and not transporteur_par_nom(nouveau):
            dernier = db.session.query(db.func.max(Transporteur.ordre)).scalar() or 0
            db.session.add(Transporteur(nom=nouveau[:80], actif=True, ordre=dernier + 1,
                                        url_suivi=(request.form.get("nouveau_url") or "").strip() or None))
        db.session.commit()
        flash("Transporteurs enregistres.", "succes")

        # Activer un transporteur incomplet le rend selectionnable sur les
        # commandes sans qu'il fournisse de bordereau : on le dit tout de
        # suite, plutot qu'au moment d'imprimer.
        for t in incomplets:
            if t.champs_manquants:
                flash("%s est actif mais incomplet : %s."
                      % (t.nom, ", ".join(t.champs_manquants)), "erreur")
            else:
                flash("%s est actif, mais son API n'est pas encore branchee : "
                      "l'impression sortira notre bon de livraison." % t.nom, "erreur")
        return redirect(retour_admin("admin_transporteurs"))

    return render_template("admin/transporteurs.html",
                           transporteurs=Transporteur.query.order_by(Transporteur.ordre,
                                                                     Transporteur.nom).all(),
                           avec_api=TRANSPORTEURS_AVEC_API,
                           masque=MASQUE_JETON)


@app.route("/admin/transporteurs/<int:transporteur_id>", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_transporteur_configurer(transporteur_id):
    """Les identifiants d'un transporteur, groupes comme sur son formulaire.

    Chaque societe demande autre chose : Aramex un compte complet, Navex une
    cle unique, Jetpack deux jetons. Le schema decrit ces champs, la page se
    construit toute seule a partir de lui.
    """
    transporteur = Transporteur.query.get_or_404(transporteur_id)

    if request.method == "POST":
        transporteur.actif = bool(request.form.get("actif"))
        transporteur.url_suivi = (request.form.get("url_suivi") or "").strip() or None

        valeurs = dict(transporteur.reglages)
        for groupe in transporteur.schema:
            for champ in groupe["champs"]:
                brut = (request.form.get(champ["nom"]) or "").strip()
                # Un secret affiche masque revient masque : le laisser tel quel
                # ne doit pas ecraser la vraie valeur enregistree.
                if champ.get("type") == "secret" and brut == MASQUE_JETON:
                    continue
                if champ["nom"] == "jeton_api":
                    transporteur.jeton_api = brut or None
                else:
                    valeurs[champ["nom"]] = brut
        transporteur.enregistrer_reglages(valeurs)

        fichier = request.files.get("logo")
        nom_logo = enregistrer_photo(fichier)
        if nom_logo:
            transporteur.logo = nom_logo
        if request.form.get("retirer_logo"):
            transporteur.logo = None

        db.session.commit()
        flash("%s enregistre." % transporteur.nom, "succes")

        manquants = transporteur.champs_manquants
        if transporteur.actif and manquants:
            flash("%s est actif mais incomplet : %s. Tant qu'il manque quelque "
                  "chose, l'expedition reste manuelle."
                  % (transporteur.nom, ", ".join(manquants)), "erreur")
        elif transporteur.actif and transporteur.nom not in TRANSPORTEURS_AVEC_API:
            flash("%s est configure, mais son API n'est pas encore branchee de "
                  "notre cote : l'impression sortira notre bon de livraison."
                  % transporteur.nom, "erreur")
        return redirect(retour_admin("admin_transporteurs"))

    return render_template("admin/transporteur_form.html",
                           t=transporteur,
                           avec_api=TRANSPORTEURS_AVEC_API,
                           masque=MASQUE_JETON,
                           gouvernorats=sorted(GOUVERNORATS_TUNISIE.keys()))


@app.route("/admin/transporteurs/tester-first-delivery")
@connexion_requise
@roles_requis("proprietaire")
def admin_tester_first_delivery():
    """Appel en lecture seule pour verifier le jeton et la joignabilite."""
    if not jeton_first_delivery():
        flash("Aucun jeton First Delivery enregistre.", "erreur")
        return redirect(retour_admin("admin_transporteurs"))
    try:
        reponse = requests.get(FIRST_DELIVERY_BASE_URL + "/localities",
                               headers=entetes_first_delivery(), timeout=30)
    except Exception as erreur:
        flash("Impossible de joindre First Delivery : %s" % erreur, "erreur")
        return redirect(retour_admin("admin_transporteurs"))

    donnees, souci = lire_reponse_first(reponse)
    if souci:
        flash(souci, "erreur")
    elif reponse.status_code >= 400:
        flash("First Delivery a refuse le jeton (%s) : %s"
              % (reponse.status_code, (donnees or {}).get("message", "")), "erreur")
    else:
        nombre = len(localites_first_delivery(forcer=True))
        flash("Connexion First Delivery correcte : %s localites recuperees." % nombre, "succes")
    return redirect(retour_admin("admin_transporteurs"))


@app.route("/admin/transporteurs/<int:transporteur_id>/supprimer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_transporteur_supprimer(transporteur_id):
    t = Transporteur.query.get_or_404(transporteur_id)
    utilise = Commande.query.filter_by(transporteur=t.nom).count()
    if utilise:
        flash("Impossible : %s commande(s) utilisent « %s ». Desactive-le plutot."
              % (utilise, t.nom), "erreur")
    else:
        db.session.delete(t)
        db.session.commit()
        flash("Transporteur supprime.", "succes")
    return redirect(retour_admin("admin_transporteurs"))


@app.route("/admin/pages")
@connexion_requise
@roles_requis("proprietaire")
def admin_pages():
    return render_template("admin/pages.html",
                           pages=PageStatique.query.order_by(PageStatique.ordre,
                                                             PageStatique.id).all())


@app.route("/admin/pages/<int:page_id>/modifier", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_page_modifier(page_id):
    page = PageStatique.query.get_or_404(page_id)

    if request.method == "POST":
        page.titre_fr = (request.form.get("titre_fr") or "").strip()[:160]
        page.titre_ar = (request.form.get("titre_ar") or "").strip()[:160]
        page.contenu_fr = nettoyer_description(request.form.get("contenu_fr"))
        page.contenu_ar = nettoyer_description(request.form.get("contenu_ar"))
        page.actif = bool(request.form.get("actif"))
        page.date_maj = datetime.utcnow()
        db.session.commit()
        flash("Page enregistree.", "succes")
        return redirect(retour_admin("admin_pages"))

    return render_template("admin/page_form.html", page=page)


@app.route("/admin/pages/<int:page_id>/basculer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_page_basculer(page_id):
    page = PageStatique.query.get_or_404(page_id)
    page.actif = not page.actif
    db.session.commit()
    return redirect(retour_admin("admin_pages"))


@app.route("/admin/categories", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_categories():
    if request.method == "POST":
        nom = (request.form.get("nom") or "").strip()
        if not nom:
            flash("Le nom est obligatoire.", "erreur")
            return redirect(retour_admin("admin_categories"))

        parent = request.form.get("parent_id") or ""
        categorie = Categorie(nom=nom[:120],
                              nom_ar=((request.form.get("nom_ar") or "").strip()[:120] or None),
                              slug=slug_categorie(nom), actif=True,
                              parent_id=parent_autorise(None, parent),
                              ordre=(db.session.query(db.func.max(Categorie.ordre)).scalar() or 0) + 1)
        banniere = enregistrer_photo(request.files.get("image"))
        if banniere:
            categorie.image = banniere

        db.session.add(categorie)
        db.session.commit()
        flash("Categorie ajoutee.", "succes")
        return redirect(retour_admin("admin_categories"))

    recherche = (request.args.get("q") or "").strip()
    dans = request.args.get("dans") or ""
    courante = db.session.get(Categorie, int(dans)) if dans.isdigit() else None
    arbre = request.args.get("vue") == "arbre"

    if arbre:
        # Tout l'arbre a plat, chaque enfant sous sa parente.
        lignes, produits = [], []

        def empiler(categorie):
            lignes.append(categorie)
            for enfant in sorted(categorie.enfants, key=lambda c: (c.ordre, c.nom)):
                empiler(enfant)

        for racine in (Categorie.query.filter_by(parent_id=None)
                       .order_by(Categorie.ordre, Categorie.nom).all()):
            empiler(racine)
    elif recherche:
        # Une recherche traverse les etages : on montre tout ce qui repond.
        lignes = (Categorie.query.filter(Categorie.nom.ilike("%%%s%%" % recherche))
                  .order_by(Categorie.ordre, Categorie.nom).all())
        produits = []
    elif courante is None:
        lignes = (Categorie.query.filter_by(parent_id=None)
                  .order_by(Categorie.ordre, Categorie.nom).all())
        produits = []
    else:
        lignes = sorted(courante.enfants, key=lambda c: (c.ordre, c.nom))
        # Plus de rayon en dessous : on affiche ce qu'elle contient.
        produits = ([] if lignes else
                    Produit.query.filter_by(categorie_id=courante.id)
                    .order_by(Produit.ordre, Produit.date_creation.desc()).all())

    params = ParametreBoutique.query.first()
    return render_template("admin/categories.html", lignes=lignes, recherche=recherche,
                           courante=courante, produits=produits, arbre=arbre,
                           fil=courante.chemin if courante else [],
                           racines=parents_possibles(),
                           pixel=(params.pixel_meta_id if params else ""))


@app.route("/admin/categories/<int:categorie_id>/modifier", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_categorie_modifier(categorie_id):
    categorie = Categorie.query.get_or_404(categorie_id)

    if request.method == "POST":
        if not (request.form.get("nom") or "").strip():
            flash("Le nom est obligatoire.", "erreur")
        else:
            appliquer_champs_categorie(categorie, request.form, request.files)
            db.session.commit()
            flash("Categorie mise a jour.", "succes")
            return redirect(retour_admin("admin_categories"))

    parents = parents_possibles(categorie)
    return render_template("admin/categorie_form.html", categorie=categorie, parents=parents)


@app.route("/admin/categories/<int:categorie_id>/basculer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_categorie_basculer(categorie_id):
    categorie = Categorie.query.get_or_404(categorie_id)
    categorie.actif = not categorie.actif
    db.session.commit()
    flash("Categorie %s." % ("affichee" if categorie.actif else "masquee"), "succes")
    return redirect(retour_admin("admin_categories"))


@app.route("/admin/categories/<int:categorie_id>/deplacer/<sens>", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_categorie_deplacer(categorie_id, sens):
    categorie = Categorie.query.get_or_404(categorie_id)
    # On ne reordonne qu'entre categories de meme niveau.
    voisines = Categorie.query.filter_by(parent_id=categorie.parent_id) \
                              .order_by(Categorie.ordre, Categorie.nom).all()
    for i, c in enumerate(voisines):
        c.ordre = i

    position = voisines.index(categorie)
    cible = position - 1 if sens == "haut" else position + 1
    if 0 <= cible < len(voisines):
        voisines[position].ordre, voisines[cible].ordre = voisines[cible].ordre, voisines[position].ordre
    db.session.commit()
    return redirect(retour_admin("admin_categories"))


@app.route("/admin/categories/<int:categorie_id>/supprimer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_categorie_supprimer(categorie_id):
    categorie = Categorie.query.get_or_404(categorie_id)
    db.session.delete(categorie)
    db.session.commit()
    flash("Catégorie supprimée.", "succes")
    return redirect(retour_admin("admin_categories"))
# ---------------------------------------------------------------------------
# ADMINISTRATION - COMMANDES (statut, historique, export)
# ---------------------------------------------------------------------------

STATUTS_SANS_STOCK = ("annulee", "retour")


def ajuster_stock(commande, sens):
    """sens = -1 retire du stock, +1 remet en stock."""
    for ligne in commande.lignes:
        if ligne.produit:
            ligne.produit.stock = (ligne.produit.stock or 0) + sens * ligne.quantite


def enregistrer_historique(commande, ancien, nouveau):
    u = utilisateur_courant()
    db.session.add(HistoriqueCommande(
        commande_id=commande.id,
        ancien_statut=ancien,
        nouveau_statut=nouveau,
        nom_utilisateur=u.nom if u else "Systeme",
    ))


@app.route("/admin/commandes/<int:commande_id>/statut", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire", "commandes", "livraison")
def admin_commande_statut(commande_id):
    commande = Commande.query.get_or_404(commande_id)
    ancien = commande.statut
    nouveau = request.form.get("statut", "").strip() or ancien

    transporteur = request.form.get("transporteur", "").strip()
    numero_suivi = request.form.get("numero_suivi", "").strip()
    if transporteur:
        commande.transporteur = transporteur
    if numero_suivi:
        commande.numero_suivi = numero_suivi

    if nouveau != ancien:
        # Le stock repart en rayon si la commande est annulee ou retournee,
        # et ressort du rayon si elle redevient active.
        if nouveau in STATUTS_SANS_STOCK and ancien not in STATUTS_SANS_STOCK:
            ajuster_stock(commande, +1)
        elif ancien in STATUTS_SANS_STOCK and nouveau not in STATUTS_SANS_STOCK:
            ajuster_stock(commande, -1)
        commande.statut = nouveau
        enregistrer_historique(commande, ancien, nouveau)
        flash("Statut mis a jour : %s." % nouveau, "succes")
    else:
        flash("Informations de livraison enregistrees.", "succes")

    db.session.commit()
    return redirect(url_for("admin_commande_detail", commande_id=commande.id))


@app.route("/admin/commandes/export")
@connexion_requise
@roles_requis("proprietaire", "commandes", "livraison")
def admin_commandes_export():
    sortie = io.StringIO()
    writeur = csv.writer(sortie, delimiter=";")
    writeur.writerow(["Numero", "Date", "Client", "Telephone", "Gouvernorat", "Ville",
                      "Adresse", "Articles", "Frais livraison", "Reduction", "Total",
                      "Statut", "Transporteur", "Numero de suivi"])
    for c in Commande.query.order_by(Commande.date_creation.desc()).all():
        articles = " | ".join("%s x%s" % (l.nom_produit, l.quantite) for l in c.lignes)
        writeur.writerow([
            c.numero,
            c.date_creation.strftime("%d/%m/%Y %H:%M") if c.date_creation else "",
            c.nom_client, c.telephone, c.gouvernorat or "", c.ville or "", c.adresse or "",
            articles,
            "%.2f" % (c.frais_livraison or 0),
            "%.2f" % (c.montant_reduction or 0),
            "%.2f" % (c.total or 0),
            c.statut, c.transporteur or "", c.numero_suivi or "",
        ])
    # BOM utf-8 pour qu'Excel affiche correctement les accents
    donnees = io.BytesIO(sortie.getvalue().encode("utf-8-sig"))
    nom_fichier = "commandes_%s.csv" % datetime.utcnow().strftime("%Y%m%d_%H%M")
    return send_file(donnees, mimetype="text/csv", as_attachment=True, download_name=nom_fichier)


# ---------------------------------------------------------------------------
# ADMINISTRATION - EXPEDITION FIRST DELIVERY
# ---------------------------------------------------------------------------

def jeton_first_delivery():
    """Jeton lu d'abord dans l'administration, sinon dans l'environnement."""
    t = transporteur_par_nom("First Delivery")
    return (t.jeton_api if t and t.jeton_api else "") or FIRST_DELIVERY_TOKEN


# Les localites changent rarement : on garde la liste en memoire pour ne pas
# rappeler First Delivery a chaque expedition.
_localites_first = {"chargee": False, "liste": []}


def localites_first_delivery(forcer=False):
    """Liste des localites First Delivery, avec leur locality_id."""
    if _localites_first["chargee"] and not forcer:
        return _localites_first["liste"]
    try:
        reponse = requests.get(FIRST_DELIVERY_BASE_URL + "/localities",
                               headers=entetes_first_delivery(), timeout=20)
        contenu = reponse.json() if reponse.content else {}
    except Exception:
        return _localites_first["liste"]
    if reponse.status_code >= 400:
        return _localites_first["liste"]
    liste = contenu.get("result") or contenu.get("data") or contenu
    if isinstance(liste, dict):
        liste = liste.get("localities") or []
    _localites_first["liste"] = liste if isinstance(liste, list) else []
    _localites_first["chargee"] = True
    return _localites_first["liste"]


def _cle_localite(texte):
    return sans_accents_simple(texte or "").replace("-", " ").replace("'", " ").strip()


# Mots qui ne distinguent pas deux localites : « Bab El Bhar » doit rejoindre
# « BAB BHAR », « Sfax Ville » doit rejoindre « Sfax ».
MOTS_VIDES_LOCALITE = {"el", "la", "le", "les", "de", "du", "des", "ville", "cite", "centre"}


def _mots_localite(texte):
    mots = [m for m in _cle_localite(texte).lower().split() if m and m not in MOTS_VIDES_LOCALITE]
    return set(mots)


def trouver_locality_id(gouvernorat, ville):
    """Fait correspondre notre gouvernorat/ville a une locality_id.

    Les deux listes ne s'ecrivent pas pareil : on compare les mots utiles
    plutot que les chaines entieres. Le gouvernorat sert de garde-fou, deux
    localites pouvant porter le meme nom dans deux gouvernorats differents.
    """
    liste = localites_first_delivery()
    if not liste:
        return None

    mots_gouv = _mots_localite(gouvernorat)
    mots_ville = _mots_localite(ville)
    if not mots_ville:
        mots_ville = mots_gouv

    candidats = [e for e in liste if isinstance(e, dict)
                 and (not mots_gouv or _mots_localite(e.get("governorate_name")) & mots_gouv)]
    if not candidats:
        candidats = [e for e in liste if isinstance(e, dict)]

    meilleur, meilleur_score = None, 0.0
    for entree in candidats:
        for champ, bonus in (("locality_name", 0.05), ("delegation_name", 0.0)):
            mots = _mots_localite(entree.get(champ))
            if not mots:
                continue
            communs = mots & mots_ville
            if not communs:
                continue
            # Proportion des mots retrouves de part et d'autre : « sfax » face a
            # « sfax ville » doit primer sur « sfax el jadida ».
            score = len(communs) / float(max(len(mots_ville), len(mots))) + bonus
            if score > meilleur_score:
                meilleur, meilleur_score = entree, score

    if meilleur is not None and meilleur_score >= 0.5:
        return meilleur.get("locality_id")

    # Repli : le chef-lieu du gouvernorat
    for entree in candidats:
        if _mots_localite(entree.get("locality_name")) == mots_gouv:
            return entree.get("locality_id")
    return None


def localites_proches(gouvernorat, limite=6):
    """Noms de localites du gouvernorat, pour guider quand rien ne correspond."""
    mots_gouv = _mots_localite(gouvernorat)
    noms = []
    for entree in localites_first_delivery():
        if not isinstance(entree, dict):
            continue
        if mots_gouv and not (_mots_localite(entree.get("governorate_name")) & mots_gouv):
            continue
        nom = (entree.get("locality_name") or "").strip()
        if nom and nom not in noms:
            noms.append(nom)
        if len(noms) >= limite:
            break
    return noms


def telephone_first_delivery(numero):
    """Numero au format attendu par First Delivery : chiffres seulement.

    Leurs exemples n'emploient jamais le « + » ; leur validateur plante quand
    il ne reconnait pas le format.
    """
    chiffres = "".join(c for c in (numero or "") if c.isdigit())
    if chiffres.startswith("00216"):
        chiffres = chiffres[5:]
    if len(chiffres) == 11 and chiffres.startswith("216"):
        chiffres = chiffres[3:]
    return chiffres


def lire_reponse_first(reponse):
    """Retourne (donnees, message_d_erreur).

    Leur API repond normalement en JSON. Quand ce n'est pas le cas (page
    Cloudflare, passerelle en panne, corps vide), on veut voir le code HTTP et
    le debut du corps plutot qu'un message de decodage incomprehensible.
    """
    try:
        return reponse.json(), None
    except ValueError:
        extrait = (reponse.text or "").strip()[:300] or "(corps vide)"
        return None, ("First Delivery a repondu %s (%s) sans JSON. Reponse : %s"
                      % (reponse.status_code,
                         reponse.headers.get("Content-Type") or "type inconnu",
                         extrait))


def entetes_first_delivery():
    return {"Authorization": "Bearer " + jeton_first_delivery(), "Content-Type": "application/json"}


@app.route("/admin/commandes/<int:commande_id>/first-delivery", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire", "livraison")
def admin_expedier_first_delivery(commande_id):
    commande = Commande.query.get_or_404(commande_id)

    if not jeton_first_delivery():
        flash("Cle First Delivery absente : renseigne-la dans Transporteurs.", "erreur")
        return redirect(url_for("admin_commande_detail", commande_id=commande.id))

    if bordereau_valide(commande) or commande.numero_suivi:
        flash("Cette commande a deja une expedition chez First Delivery : "
              "en creer une seconde ferait un doublon facture.", "erreur")
        return redirect(url_for("admin_commande_detail", commande_id=commande.id))

    souci = creer_expedition_first(commande)
    if souci:
        flash("First Delivery : %s" % souci, "erreur")
        return redirect(url_for("admin_commande_detail", commande_id=commande.id))

    db.session.commit()
    flash("Commande expediee. Code a barre : %s" % commande.numero_suivi, "succes")
    return redirect(url_for("admin_commande_detail", commande_id=commande.id))


@app.route("/admin/commandes/<int:commande_id>/first-delivery/statut")
@connexion_requise
@roles_requis("proprietaire", "livraison")
def admin_verifier_statut_first_delivery(commande_id):
    commande = Commande.query.get_or_404(commande_id)

    if not jeton_first_delivery() or not commande.numero_suivi:
        flash("Token First Delivery ou numero de suivi manquant.", "erreur")
        return redirect(url_for("admin_commande_detail", commande_id=commande.id))

    try:
        reponse = requests.post(FIRST_DELIVERY_BASE_URL + "/etat",
                                json={"barCode": str(commande.numero_suivi).strip()},
                                headers=entetes_first_delivery(), timeout=30)
        resultat, souci = lire_reponse_first(reponse)
        if souci:
            flash(souci, "erreur")
            return redirect(url_for("admin_commande_detail", commande_id=commande.id))
    except Exception as erreur:
        flash("Impossible de joindre First Delivery : %s" % erreur, "erreur")
        return redirect(url_for("admin_commande_detail", commande_id=commande.id))

    contenu = resultat.get("result") or resultat.get("data") or resultat
    etat = contenu.get("state") or contenu.get("etat") or "inconnu"
    lien = contenu.get("pdfUrl") or contenu.get("lien_bordereau")
    if lien:
        commande.lien_bordereau = lien
        db.session.commit()

    flash("Statut chez First Delivery : %s" % etat, "succes")
    return redirect(url_for("admin_commande_detail", commande_id=commande.id))


# ---------------------------------------------------------------------------
# ADMINISTRATION - IMPORT CSV DES PRODUITS
# ---------------------------------------------------------------------------

def trouver_ou_creer_categorie(nom):
    nom = (nom or "").strip()
    if not nom:
        return None
    slug = nom.lower().replace(" ", "-")
    categorie = Categorie.query.filter_by(slug=slug).first()
    if not categorie:
        categorie = Categorie(nom=nom, slug=slug)
        db.session.add(categorie)
        db.session.flush()
    return categorie


def nombre_ou_defaut(valeur, defaut=0.0):
    try:
        return float(str(valeur).replace(",", ".").strip())
    except (TypeError, ValueError):
        return defaut


# ---------------------------------------------------------------------------
# IMPORT UNIVERSEL DE PRODUITS (Converty, Shopify, Excel, CSV)
#
# Les exports varient d'une plateforme a l'autre : on reconnait les colonnes
# par leurs noms usuels (francais, anglais, arabe) au lieu d'imposer un format.
# ---------------------------------------------------------------------------

# Pour chaque champ, les intitules de colonne qu'on sait reconnaitre.
ALIAS_COLONNES = {
    "nom": ["nom", "name", "titre", "title", "produit", "product", "product name",
            "nom du produit", "product title", "designation", "libelle", "الاسم", "اسم المنتج"],
    "reference": ["reference", "ref", "sku", "code", "code produit", "barcode",
                  "code barre", "variant sku", "handle", "المرجع"],
    "categorie": ["categorie", "category", "catégorie", "collection", "type",
                  "product type", "product category", "rayon", "الفئة", "التصنيف"],
    "prix": ["prix", "price", "prix de vente", "regular price", "prix normal",
             "variant price", "selling price", "prix ttc", "السعر"],
    "cout": ["cout", "coût", "cost", "prix achat", "prix d achat", "buying price", "التكلفة"],
    "prix_promo": ["prix promo", "prix promotion", "sale price", "promo", "prix solde",
                   "prix soldé", "discount price", "prix remise", "prix barre",
                   "prix barré", "سعر التخفيض"],
    "stock": ["stock", "quantite", "quantité", "qte", "qty", "quantity", "inventory",
              "inventory quantity", "variant inventory qty", "الكمية", "المخزون"],
    "description": ["description", "desc", "détail", "detail", "body", "body (html)",
                    "contenu", "product description", "الوصف"],
    "couleur": ["couleur", "color", "colour", "اللون"],
    "dimensions": ["dimensions", "dimension", "taille", "size", "المقاس"],
    "image": ["image", "images", "image url", "image_link", "photo", "photos",
              "picture", "image src", "url image", "lien image", "الصورة"],
}

TAILLE_MAX_IMAGE = 5 * 1024 * 1024  # 5 Mo
EXTENSIONS_IMAGE = (".jpg", ".jpeg", ".png", ".webp", ".gif")


# Les descriptions importees peuvent contenir de la mise en forme (titres, gras,
# listes) : on la garde, mais on retire tout ce qui peut executer du code.
_BALISES_DANGEREUSES = re.compile(
    r"<\s*(script|style|iframe|object|embed|form|input)[^>]*>.*?<\s*/\s*\s*>", re.I | re.S)
_BALISE_ORPHELINE = re.compile(r"<\s*(script|style|iframe|object|embed|form|input)[^>]*/?>", re.I)
_ATTRIBUT_EVENEMENT = re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_LIEN_JAVASCRIPT = re.compile(r"(href|src)\s*=\s*([\"'])\s*javascript:[^\"']*", re.I)


def nombre_ou_vide(valeur):
    """Un champ laisse vide veut dire 'utiliser la valeur generale', pas zero."""
    valeur = (valeur or "").strip()
    if valeur == "":
        return None
    try:
        return float(valeur.replace(",", "."))
    except ValueError:
        return None


def slug_produit(nom, produit_id=None):
    base = re.sub(r"[^a-z0-9]+", "-", sans_accents_simple(nom)).strip("-")[:200] or "produit"
    candidat, n = base, 2
    while True:
        existant = Produit.query.filter_by(slug=candidat).first()
        if not existant or existant.id == produit_id:
            return candidat
        candidat = "%s-%s" % (base, n)
        n += 1


def sans_accents_simple(texte):
    import unicodedata
    decompose = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower()


def appliquer_champs_avances(produit, formulaire):
    """Champs communs a la creation et a la modification."""
    produit.prix_livraison = nombre_ou_vide(formulaire.get("prix_livraison"))
    produit.cout_livraison = nombre_ou_vide(formulaire.get("cout_livraison"))

    seuil = nombre_ou_vide(formulaire.get("seuil_alerte"))
    produit.seuil_alerte = int(seuil) if seuil is not None else None
    produit.stock_entrant = int(nombre_ou_defaut(formulaire.get("stock_entrant"), 0))
    produit.stock_abime = int(nombre_ou_defaut(formulaire.get("stock_abime"), 0))
    produit.vente_en_rupture = bool(formulaire.get("vente_en_rupture"))

    lot = nombre_ou_vide(formulaire.get("lot_quantite"))
    produit.lot_quantite = int(lot) if lot and lot >= 2 else None
    produit.lot_type = formulaire.get("lot_type", "pourcentage")
    produit.lot_valeur = nombre_ou_defaut(formulaire.get("lot_valeur"), 0)

    produit.meta_titre = (formulaire.get("meta_titre") or "").strip()[:200]
    produit.meta_description = (formulaire.get("meta_description") or "").strip()[:320]
    saisi = (formulaire.get("slug") or "").strip()
    produit.slug = slug_produit(saisi or produit.nom, produit.id)

    lies = [x for x in formulaire.getlist("produits_lies") if x.isdigit()]
    produit.produits_lies = json.dumps([int(x) for x in lies][:8])


def enregistrer_photo(fichier):
    """Enregistre une photo sous un nom unique et retourne ce nom."""
    if not fichier or not fichier.filename:
        return None
    extension = os.path.splitext(secure_filename(fichier.filename))[1].lower()
    if extension not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        return None
    nom = "%s%s" % (uuid.uuid4().hex, extension)
    fichier.save(os.path.join(app.config["UPLOAD_FOLDER"], nom))
    return nom


VIDEOS_ACCEPTEES = (".mp4", ".webm", ".mov", ".m4v")
TAILLE_VIDEO_MAX = 40 * 1024 * 1024   # 40 Mo : au-dela, mieux vaut un lien


def enregistrer_video(fichier):
    """Enregistre une video et retourne son nom, ou None si elle est refusee."""
    if not fichier or not fichier.filename:
        return None, None
    extension = os.path.splitext(secure_filename(fichier.filename))[1].lower()
    if extension not in VIDEOS_ACCEPTEES:
        return None, "Format video non accepte : utilise MP4, WebM ou MOV."
    fichier.seek(0, os.SEEK_END)
    taille = fichier.tell()
    fichier.seek(0)
    if taille > TAILLE_VIDEO_MAX:
        return None, ("Video trop lourde (%.0f Mo). Limite : 40 Mo. "
                      "Au-dela, mets-la sur YouTube et colle le lien."
                      % (taille / 1024.0 / 1024.0))
    nom = "%s%s" % (uuid.uuid4().hex, extension)
    fichier.save(os.path.join(app.config["UPLOAD_FOLDER"], nom))
    return nom, None


# Certains sites ne partagent qu'une adresse courte, illisible par leur propre
# lecteur. On la suit une fois, a l'enregistrement, pour garder l'adresse
# reelle : la boutique n'a alors plus aucun appel a faire a l'affichage.
LIENS_A_SUIVRE = ("/share/", "fb.watch", "youtu.be/", "vm.tiktok.com", "vt.tiktok.com")

NAVIGATEUR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def resoudre_lien_partage(url):
    """Adresse finale d'un lien de partage, ou le lien d'origine si echec."""
    if not url or not any(motif in url for motif in LIENS_A_SUIVRE):
        return url
    try:
        reponse = requests.get(url, allow_redirects=True, timeout=12,
                               stream=True, headers={"User-Agent": NAVIGATEUR})
        finale = reponse.url or url
        reponse.close()
    except Exception as erreur:
        app.logger.info("Lien de partage non resolu (%s) : %s", url, erreur)
        return url
    # Une redirection vers une page de connexion ne nous avance a rien.
    if "login" in finale or "checkpoint" in finale:
        return url
    return finale


def video_integree(url):
    """Transforme un lien de partage en adresse d'integration.

    On accepte ce que les gens copient reellement : youtu.be, watch?v=,
    /shorts/, TikTok, Facebook et Vimeo. Le site est reconnu en premier :
    plusieurs d'entre eux emploient un parametre « v= », et se fier au seul
    identifiant envoyait un lien Facebook vers le lecteur de YouTube.

    Les reglages du lecteur comptent autant que le lecteur lui-meme : sans
    eux, la video se termine sur des recommandations sans rapport et un
    bouton qui emmene l'acheteur hors de la boutique.
    """
    if not url:
        return None
    url = url.strip()
    hote = (re.sub(r"^https?://", "", url).split("/")[0] or "").lower()

    # ---------------------------------------------------------- YouTube
    if "youtube.com" in hote or "youtu.be" in hote:
        jeton = (re.search(r"youtu\.be/([A-Za-z0-9_-]{6,})", url)
                 or re.search(r"/shorts/([A-Za-z0-9_-]{6,})", url)
                 or re.search(r"/embed/([A-Za-z0-9_-]{6,})", url)
                 or re.search(r"[?&]v=([A-Za-z0-9_-]{6,})", url))
        if not jeton:
            return None
        code = jeton.group(1)
        # « loop » exige « playlist » pour une video seule, chez YouTube.
        return ("https://www.youtube.com/embed/%s"
                "?rel=0&modestbranding=1&playsinline=1&loop=1&playlist=%s"
                % (code, code))

    # ----------------------------------------------------------- TikTok
    if "tiktok.com" in hote:
        jeton = re.search(r"/(?:video|player/v1|embed(?:/v2)?)/(\d{6,})", url)
        if not jeton:
            return None
        return ("https://www.tiktok.com/player/v1/%s"
                "?rel=0&loop=1&description=0&music_info=0&native_context_menu=0"
                % jeton.group(1))

    # --------------------------------------------------------- Facebook
    if "facebook.com" in hote or "fb.watch" in hote:
        # « /share/... » est une redirection : le lecteur ne sait pas la suivre.
        if "/share/" in url:
            return None
        # Le module Facebook rend la video a la taille qu'on lui annonce :
        # sans largeur, il choisit la sienne et la video deborde du cadre.
        return ("https://www.facebook.com/plugins/video.php"
                "?show_text=false&autoplay=false&width=360&height=640&href="
                + quote(url, safe=""))

    # -------------------------------------------------------- Instagram
    if "instagram.com" in hote:
        # « /share/... » ne porte pas l'identifiant de la publication : il
        # faut l'adresse copiee depuis la publication elle-meme.
        if "/share/" in url:
            return None
        jeton = re.search(r"/(reels?|p|tv)/([A-Za-z0-9_-]{5,})", url)
        if not jeton:
            return None
        genre = "reel" if jeton.group(1).startswith("reel") else jeton.group(1)
        return "https://www.instagram.com/%s/%s/embed/" % (genre, jeton.group(2))

    # ------------------------------------------------------------ Vimeo
    if "vimeo.com" in hote:
        jeton = re.search(r"/(?:video/)?(\d{6,})", url)
        if jeton:
            return "https://player.vimeo.com/video/%s" % jeton.group(1)
        return None

    # Un lecteur deja pret passe tel quel.
    if hote.startswith("player."):
        return url
    return None


# Phrases par lesquelles un lecteur annonce qu'il refuse la video. On ne
# bloque que sur un refus constate : une verification impossible (site
# injoignable) laisse passer le lien plutot que d'empecher un enregistrement.
REFUS_LECTEUR = ("be embedded",                       # can't / cannot be embedded
                 "may no longer exist",
                 "don't have permission to view",
                 "n'est plus disponible")


def lecteur_refuse(adresse):
    """Motif du refus affiche par le lecteur, ou None si tout va bien."""
    if not adresse or "facebook.com/plugins" not in adresse:
        return None
    try:
        reponse = requests.get(adresse, timeout=12,
                               headers={"User-Agent": NAVIGATEUR})
        # Le message arrive avec des apostrophes encodees (« can&#39;t ») :
        # sans decodage, aucune de nos phrases ne correspondrait.
        page = html.unescape(reponse.text or "").lower()
    except Exception as erreur:
        app.logger.info("Verification du lecteur impossible : %s", erreur)
        return None
    for phrase in REFUS_LECTEUR:
        if phrase in page:
            return phrase
    return None


def appliquer_video(produit, formulaire, fichiers):
    """Range le lien et le fichier video envoyes par un formulaire admin.

    Partage par la creation et la modification : ecrite une seule fois dans
    la modification, la video saisie a la creation etait perdue en silence.
    """
    lien = (formulaire.get("video_url") or "").strip() or None
    if lien:
        lien = resoudre_lien_partage(lien)
    produit.video_url = lien
    produit.video_verticale = bool(formulaire.get("video_verticale"))
    lecteur = video_integree(produit.video_url) if produit.video_url else None
    if produit.video_url and not lecteur:
        flash("Ce lien video n'est pas lisible par la boutique. Ouvre la video "
              "chez son hebergeur et copie l'adresse de la barre d'adresse : un "
              "lien de partage court (facebook.com/share/..., "
              "instagram.com/share/...) ne fonctionne pas. Pour Instagram, "
              "l'adresse doit contenir /reel/ ou /p/.", "erreur")
        produit.video_url = None
    elif lecteur and lecteur_refuse(lecteur):
        flash("Facebook refuse d'afficher cette video en dehors de son site : "
              "elle contient de la musique ou un extrait appartenant a "
              "quelqu'un d'autre. Choisis une autre video, sinon la fiche "
              "montrerait un cadre noir.", "erreur")
        produit.video_url = None
    nouvelle_video, souci = enregistrer_video(fichiers.get("video"))
    if souci:
        flash(souci, "erreur")
    elif nouvelle_video:
        produit.video = nouvelle_video
    if formulaire.get("retirer_video"):
        produit.video = None


def enregistrer_photos_sup(produit, fichiers):
    """Ajoute les photos supplementaires a la suite de celles deja presentes."""
    depart = max([i.ordre for i in produit.images_sup] or [0])
    ajoutees = 0
    for fichier in fichiers or []:
        nom = enregistrer_photo(fichier)
        if nom:
            depart += 1
            db.session.add(ImageProduit(produit_id=produit.id, fichier=nom, ordre=depart))
            ajoutees += 1
    return ajoutees


def nettoyer_description(brut):
    texte = brut or ""
    if "<" not in texte:
        return texte.strip()
    texte = _BALISES_DANGEREUSES.sub("", texte)
    texte = _BALISE_ORPHELINE.sub("", texte)
    texte = _ATTRIBUT_EVENEMENT.sub("", texte)
    texte = _LIEN_JAVASCRIPT.sub("", texte)
    return texte.strip()


def normaliser_entete(texte):
    texte = (str(texte or "")).strip().lower()
    texte = texte.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", texte).strip()


def detecter_colonnes(entetes):
    """Associe chaque champ interne au nom de colonne trouve dans le fichier."""
    normalises = {normaliser_entete(e): e for e in entetes if e}
    correspondances = {}

    for champ, alias in ALIAS_COLONNES.items():
        # 1) correspondance exacte
        for a in alias:
            if a in normalises:
                correspondances[champ] = normalises[a]
                break
        if champ in correspondances:
            continue
        # 2) correspondance partielle (ex: "Prix de vente TTC" -> prix)
        for entete_norm, entete_brut in normalises.items():
            if any(entete_norm.startswith(a) or a in entete_norm for a in alias):
                correspondances[champ] = entete_brut
                break

    return correspondances


def lire_tableau(fichier):
    """Retourne (entetes, lignes) depuis un .xlsx, .xls ou .csv."""
    nom = (fichier.filename or "").lower()
    brut = fichier.read()

    if nom.endswith((".xlsx", ".xlsm")):
        classeur = openpyxl.load_workbook(io.BytesIO(brut), read_only=True, data_only=True)
        feuille = classeur.active
        iterateur = feuille.iter_rows(values_only=True)
        entetes = [str(c).strip() if c is not None else "" for c in next(iterateur, [])]
        lignes = [dict(zip(entetes, ["" if c is None else str(c).strip() for c in ligne]))
                  for ligne in iterateur]
        classeur.close()
        return entetes, lignes

    try:
        texte = brut.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = brut.decode("latin-1")

    premiere = texte.splitlines()[0] if texte.splitlines() else ""
    # Converty et Excel FR exportent souvent en point-virgule, Shopify en virgule.
    separateur = max([",", ";", "\t"], key=premiere.count)
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=separateur)
    lignes = [{(k or ""): (v or "").strip() for k, v in ligne.items()} for ligne in lecteur]
    return (lecteur.fieldnames or []), lignes


def telecharger_image(url):
    """Rapatrie l'image d'un export distant. Retourne le nom de fichier local ou None."""
    url = (url or "").split(",")[0].split("|")[0].strip()
    if not url.lower().startswith(("http://", "https://")):
        return None

    try:
        reponse = requests.get(url, timeout=15, stream=True)
        if reponse.status_code != 200:
            return None

        taille = int(reponse.headers.get("Content-Length") or 0)
        if taille > TAILLE_MAX_IMAGE:
            return None

        type_contenu = (reponse.headers.get("Content-Type") or "").lower()
        if not type_contenu.startswith("image/"):
            return None

        extension = os.path.splitext(url.split("?")[0])[1].lower()
        if extension not in EXTENSIONS_IMAGE:
            extension = {"image/png": ".png", "image/webp": ".webp",
                         "image/gif": ".gif"}.get(type_contenu, ".jpg")

        donnees = b""
        for morceau in reponse.iter_content(8192):
            donnees += morceau
            if len(donnees) > TAILLE_MAX_IMAGE:
                return None

        nom_fichier = secure_filename("%s%s" % (uuid.uuid4().hex, extension))
        with open(os.path.join(app.config["UPLOAD_FOLDER"], nom_fichier), "wb") as f:
            f.write(donnees)
        return nom_fichier
    except Exception:
        return None


@app.route("/admin/produits/import", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_produits_import():
    if request.method == "POST":
        fichier = request.files.get("fichier_csv")
        if not fichier or not fichier.filename:
            flash("Aucun fichier selectionne.", "erreur")
            return redirect(url_for("admin_produits_import"))

        try:
            entetes, lignes = lire_tableau(fichier)
        except Exception as erreur:
            flash("Fichier illisible : %s" % erreur, "erreur")
            return redirect(url_for("admin_produits_import"))

        colonnes = detecter_colonnes(entetes)
        if "nom" not in colonnes:
            flash("Impossible de trouver la colonne du nom de produit. Colonnes lues : %s"
                  % ", ".join(str(e) for e in entetes if e), "erreur")
            return redirect(url_for("admin_produits_import"))

        recuperer_images = bool(request.form.get("telecharger_images"))

        def valeur(ligne, champ):
            colonne = colonnes.get(champ)
            return (ligne.get(colonne, "") if colonne else "") or ""

        ajoutes, modifies, ignores, images_ok = 0, 0, 0, 0
        vus = set()

        for ligne in lignes:
            nom = valeur(ligne, "nom").strip()
            if not nom:
                ignores += 1
                continue

            reference = valeur(ligne, "reference").strip() or None
            # Les exports a variantes repetent le produit sur plusieurs lignes.
            cle_unicite = reference or nom.lower()
            if cle_unicite in vus:
                ignores += 1
                continue
            vus.add(cle_unicite)

            produit = Produit.query.filter_by(reference=reference).first() if reference else                       Produit.query.filter_by(nom=nom).first()
            nouveau = produit is None
            if nouveau:
                produit = Produit(nom=nom, reference=reference)
                db.session.add(produit)

            produit.nom = nom
            produit.description = nettoyer_description(valeur(ligne, "description"))
            produit.prix = nombre_ou_defaut(valeur(ligne, "prix"), 0.0)
            prix_promo = nombre_ou_defaut(valeur(ligne, "prix_promo"), 0.0)
            # Un "prix barre" superieur au prix de vente est l'ancien prix, pas une promo.
            produit.prix_promo = prix_promo if 0 < prix_promo < produit.prix else None
            produit.stock = int(nombre_ou_defaut(valeur(ligne, "stock"), 0))
            produit.cout = nombre_ou_defaut(valeur(ligne, "cout"), produit.cout or 0)
            produit.couleur = valeur(ligne, "couleur")
            produit.dimensions = valeur(ligne, "dimensions")

            categorie = trouver_ou_creer_categorie(valeur(ligne, "categorie"))
            if categorie:
                produit.categorie_id = categorie.id

            if recuperer_images and not produit.image:
                nom_image = telecharger_image(valeur(ligne, "image"))
                if nom_image:
                    produit.image = nom_image
                    images_ok += 1

            if nouveau:
                ajoutes += 1
            else:
                modifies += 1

        db.session.commit()

        reconnues = ", ".join("%s -> %s" % (champ, colonnes[champ]) for champ in colonnes)
        flash("Import termine : %s produit(s) ajoute(s), %s mis a jour, %s ligne(s) ignoree(s), %s image(s) recuperee(s)."
              % (ajoutes, modifies, ignores, images_ok), "succes")
        flash("Colonnes reconnues automatiquement : %s" % reconnues, "succes")
        return redirect(url_for("admin_produits"))

    return render_template("admin/produits_import.html")


# ---------------------------------------------------------------------------
# ADMINISTRATION - UTILISATEURS
# ---------------------------------------------------------------------------

ROLES_AUTORISES = ("proprietaire", "commandes", "livraison")


@app.route("/admin/utilisateurs")
@connexion_requise
@roles_requis("proprietaire")
def admin_utilisateurs():
    recherche = (request.args.get("q") or "").strip()
    requete = Utilisateur.query
    if recherche:
        motif = "%%%s%%" % recherche
        requete = requete.filter(db.or_(Utilisateur.nom.ilike(motif),
                                        Utilisateur.prenom.ilike(motif),
                                        Utilisateur.email.ilike(motif),
                                        Utilisateur.telephone.ilike(motif)))
    return render_template("admin/utilisateurs.html",
                           utilisateurs=requete.order_by(Utilisateur.date_creation).all(),
                           total=Utilisateur.query.count(),
                           recherche=recherche)


def enregistrer_utilisateur(cible):
    """Applique le formulaire a un utilisateur, ou renvoie le motif du refus."""
    formulaire = request.form
    email = (formulaire.get("email") or "").strip().lower()
    nom = (formulaire.get("nom") or "").strip()
    mot_de_passe = formulaire.get("mot_de_passe") or ""
    role = formulaire.get("role") or "commandes"

    if not email or not nom:
        return "Le nom et l'adresse e-mail sont obligatoires."
    if role not in ROLES_AUTORISES:
        return "Role inconnu."
    double = Utilisateur.query.filter(Utilisateur.email == email,
                                      Utilisateur.id != (cible.id or 0)).first()
    if double:
        return "Un utilisateur porte deja cette adresse e-mail."
    if cible.id is None and len(mot_de_passe) < 8:
        return "Le mot de passe doit faire au moins 8 caracteres."
    if mot_de_passe and len(mot_de_passe) < 8:
        return "Le mot de passe doit faire au moins 8 caracteres."

    cible.nom = nom[:120]
    cible.prenom = (formulaire.get("prenom") or "").strip()[:120] or None
    cible.email = email[:150]
    cible.telephone = (formulaire.get("telephone") or "").strip()[:40] or None
    cible.role = role
    cible.actif = bool(formulaire.get("actif"))
    if mot_de_passe:
        cible.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    # La grille l'emporte sur le role : c'est elle que l'ecran montre.
    droits = {}
    for cle, _, actions in RUBRIQUES:
        cochees = [a for a in actions if formulaire.get("droit_%s_%s" % (cle, a))]
        if cochees:
            droits[cle] = cochees
    cible.enregistrer_droits(droits)
    return None


@app.route("/admin/utilisateurs/nouveau", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_utilisateur_nouveau():
    cible = Utilisateur(nom="", email="", mot_de_passe_hash="", role="commandes", actif=True)
    if request.method == "POST":
        souci = enregistrer_utilisateur(cible)
        if souci:
            flash(souci, "erreur")
        else:
            db.session.add(cible)
            db.session.commit()
            flash("Utilisateur cree.", "succes")
            return redirect(retour_admin("admin_utilisateurs"))
    return render_template("admin/utilisateur_form.html", u=cible,
                           rubriques=RUBRIQUES, actions=ACTIONS,
                           droits_role=DROITS_PAR_ROLE)


@app.route("/admin/utilisateurs/<int:utilisateur_id>/modifier", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_utilisateur_modifier(utilisateur_id):
    cible = Utilisateur.query.get_or_404(utilisateur_id)
    if request.method == "POST":
        courant = utilisateur_courant()
        # On ne se retire pas soi-meme ses propres droits : le seul chemin
        # vers cette page serait alors ferme.
        if cible.id == courant.id and (not request.form.get("actif")
                                       or request.form.get("role") != "proprietaire"):
            flash("Tu ne peux pas retirer tes propres droits d'administrateur.", "erreur")
            return redirect(retour_admin("admin_utilisateurs"))

        souci = enregistrer_utilisateur(cible)
        if souci:
            flash(souci, "erreur")
        else:
            db.session.commit()
            flash("Utilisateur enregistre.", "succes")
            return redirect(retour_admin("admin_utilisateurs"))
    return render_template("admin/utilisateur_form.html", u=cible,
                           rubriques=RUBRIQUES, actions=ACTIONS,
                           droits_role=DROITS_PAR_ROLE)


@app.route("/admin/utilisateurs/<int:utilisateur_id>/reinitialiser", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_utilisateur_reinitialiser(utilisateur_id):
    """Mot de passe provisoire, affiche une seule fois au proprietaire.

    C'est la voie de secours quand l'e-mail ne repond pas : dans une boutique,
    un vendeur est joignable par WhatsApp bien plus vite que par courriel, et
    tous n'ont pas d'adresse qu'ils relevent. Le mot de passe n'est jamais mis
    dans l'adresse de la page : il passe par le message d'un seul affichage.
    """
    cible = Utilisateur.query.get_or_404(utilisateur_id)
    moi = utilisateur_courant()
    if cible.id == moi.id:
        flash("Pour ton propre compte, passe par « Changer mon mot de passe ».",
              "erreur")
        return redirect(retour_admin("admin_utilisateurs"))

    provisoire = mot_de_passe_provisoire()
    cible.mot_de_passe_hash = generate_password_hash(provisoire)
    cible.doit_changer_mdp = True
    perimer_les_codes(cible)
    db.session.commit()
    app.logger.info("Mot de passe reinitialise pour %s par %s",
                    cible.email, moi.email)
    flash("Mot de passe provisoire de %s : %s — transmets-le lui maintenant, "
          "il ne sera plus affiche. Il devra en choisir un autre des sa "
          "premiere connexion." % (cible.nom_affiche, provisoire), "succes")
    return redirect(retour_admin("admin_utilisateurs"))


@app.route("/admin/utilisateurs/<int:utilisateur_id>/desactiver", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_utilisateur_desactiver(utilisateur_id):
    cible = Utilisateur.query.get_or_404(utilisateur_id)
    courant = utilisateur_courant()

    if cible.id == courant.id:
        flash("Tu ne peux pas desactiver ton propre compte.", "erreur")
        return redirect(retour_admin("admin_utilisateurs"))

    # On garde toujours au moins un proprietaire actif pour ne pas se verrouiller dehors.
    if cible.actif and cible.role == "proprietaire":
        autres = Utilisateur.query.filter(Utilisateur.role == "proprietaire",
                                          Utilisateur.actif == True,
                                          Utilisateur.id != cible.id).count()
        if autres == 0:
            flash("Impossible : c'est le dernier administrateur actif.", "erreur")
            return redirect(retour_admin("admin_utilisateurs"))

    cible.actif = not cible.actif
    db.session.commit()
    flash("Utilisateur active." if cible.actif else "Utilisateur desactive.", "succes")
    return redirect(retour_admin("admin_utilisateurs"))


# ---------------------------------------------------------------------------
# ADMINISTRATION - PARAMETRES DE LA BOUTIQUE
# ---------------------------------------------------------------------------

@app.route("/admin/parametres", methods=["GET", "POST"])
@connexion_requise
@roles_requis("proprietaire")
def admin_parametres():
    params = ParametreBoutique.query.first()
    if not params:
        params = ParametreBoutique()
        db.session.add(params)
        db.session.commit()

    if request.method == "POST":
        for champ in ("nom_boutique", "telephone", "whatsapp", "adresse", "facebook",
                      "instagram", "tiktok", "email", "pixel_meta_id",
                      "meta_test_event_code", "texte_bandeau",
                      "google_analytics_id", "google_verification",
                      "meta_domain_verification", "clarity_id",
                      "modele_whatsapp_confirmation", "modele_whatsapp_expedition",
                      "modele_whatsapp_relance", "raison_sociale",
                      "matricule_fiscal", "registre_commerce"):
            # Un champ absent de la requete n'est pas un champ vide : sans
            # cette condition, un formulaire partiel effacait en silence tout
            # ce qu'il ne portait pas (coordonnees, mentions legales, modeles
            # de messages). Pour vider un champ, il faut l'envoyer vide.
            if champ in request.form:
                setattr(params, champ, request.form.get(champ, "").strip())

        # Le jeton CAPI n'est jamais renvoye au navigateur : le champ arrive
        # donc vide a chaque affichage, et « vide » signifie « ne change
        # rien ». Sans cette exception, le gestionnaire de mots de passe du
        # navigateur remplissait ce champ « password » avec l'identifiant de
        # l'administration, qui partait en base a l'enregistrement suivant.
        jeton = (request.form.get("meta_capi_token") or "").strip()
        if request.form.get("effacer_capi_token"):
            params.meta_capi_token = ""
        elif jeton:
            params.meta_capi_token = jeton

        params.frais_livraison_defaut = nombre_ou_defaut(request.form.get("frais_livraison_defaut"), 8.0)
        params.montant_livraison_gratuite = nombre_ou_defaut(request.form.get("montant_livraison_gratuite"), 150.0)
        params.taux_tva = nombre_ou_defaut(request.form.get("taux_tva"), 19.0)
        params.timbre_fiscal = nombre_ou_defaut(request.form.get("timbre_fiscal"), 1.0)
        params.seuil_alerte_stock = int(nombre_ou_defaut(request.form.get("seuil_alerte_stock"), 1))
        db.session.commit()
        flash("Parametres enregistres.", "succes")
        return redirect(retour_admin("admin_parametres"))

    return render_template("admin/parametres.html", params=params)


# ---------------------------------------------------------------------------
# PANIERS ABANDONNES ET RELANCE WHATSAPP
#
# En Tunisie le paiement se fait a la livraison : le vrai goulot n'est pas le
# paiement mais la confirmation par telephone. On capture donc le numero des
# le remplissage du formulaire, avant meme la validation de la commande.
# ---------------------------------------------------------------------------

MODELES_MESSAGES_DEFAUT = {
    "modele_whatsapp_confirmation": (
        "Bonjour {client}, ici {boutique}.\n"
        "Nous confirmons votre commande {numero} :\n{produits}\n"
        "Total : {total} TND (paiement a la livraison).\n"
        "Merci de confirmer pour que nous lancions la preparation."
    ),
    "modele_whatsapp_expedition": (
        "Bonjour {client}, votre commande {numero} vient d'etre expediee.\n"
        "Transporteur : {transporteur}\nNumero de suivi : {suivi}\n"
        "Vous serez contacte par le livreur. Merci de votre confiance, {boutique}."
    ),
    "modele_whatsapp_relance": (
        "Bonjour {client}, ici {boutique}.\n"
        "Vous avez laisse ces articles dans votre panier :\n{produits}\n"
        "Total : {total} TND, livraison partout en Tunisie, paiement a la livraison.\n"
        "Souhaitez-vous que nous finalisions la commande pour vous ?"
    ),
}


def remplir_modele(modele, valeurs):
    """Remplace les {champs} du modele, en laissant passer ceux qui manquent."""
    resultat = modele or ""
    for cle, valeur in valeurs.items():
        resultat = resultat.replace("{%s}" % cle, str(valeur if valeur is not None else ""))
    return resultat


def lien_whatsapp(telephone, message):
    """Lien click-to-chat : ouvre WhatsApp avec le message deja ecrit."""
    numero = telephone_e164(telephone)
    if not numero:
        return None
    return "https://wa.me/%s?text=%s" % (numero, quote(message))


def resume_articles(articles):
    """articles = [{"nom":..., "quantite":..., "prix":...}]"""
    return "\n".join("- %s x%s (%.2f TND)" % (a["nom"], a["quantite"], a["prix"])
                     for a in articles)


@app.route("/panier/memoriser", methods=["POST"])
def memoriser_panier_abandonne():
    """Appele en arriere-plan des que le client saisit son telephone au checkout."""
    telephone = (request.form.get("telephone") or "").strip()
    if not telephone_valide(telephone):
        return {"ok": False}, 200

    lignes, total, _ = detailler_panier()
    if not lignes:
        return {"ok": False}, 200
    articles = [{"nom": l["nom_affiche"], "quantite": l["quantite"],
                 "prix": round(l["unitaire"], 3)} for l in lignes]

    numero_normalise = telephone_e164(telephone)
    abandon = PanierAbandonne.query.filter_by(telephone_normalise=numero_normalise,
                                              statut="actif").first()
    if not abandon:
        abandon = PanierAbandonne(telephone_normalise=numero_normalise)
        db.session.add(abandon)

    abandon.telephone = telephone
    abandon.nom_client = (request.form.get("nom_client") or "").strip()
    abandon.gouvernorat = (request.form.get("gouvernorat") or "").strip()
    abandon.ville = (request.form.get("ville") or "").strip()
    abandon.contenu = json.dumps(articles, ensure_ascii=False)
    abandon.total = round(total, 3)
    abandon.date_maj = datetime.utcnow()
    db.session.commit()
    return {"ok": True}, 200


@app.route("/admin/paniers-abandonnes")
@connexion_requise
@roles_requis("proprietaire", "commandes")
def admin_paniers_abandonnes():
    params = ParametreBoutique.query.first()
    modele = (params.modele_whatsapp_relance if params else "") or MODELES_MESSAGES_DEFAUT["modele_whatsapp_relance"]
    nom_boutique = params.nom_boutique if params else "Maison des Garnitures"

    paniers = PanierAbandonne.query.order_by(PanierAbandonne.date_maj.desc()).all()
    lignes = []
    for panier in paniers:
        try:
            articles = json.loads(panier.contenu or "[]")
        except ValueError:
            articles = []
        message = remplir_modele(modele, {
            "client": panier.nom_client or "",
            "boutique": nom_boutique,
            "produits": resume_articles(articles),
            "total": "%.2f" % (panier.total or 0),
        })
        lignes.append({
            "panier": panier,
            "articles": articles,
            "lien_whatsapp": lien_whatsapp(panier.telephone, message),
        })

    return render_template("admin/paniers_abandonnes.html", lignes=lignes,
                           total_actifs=sum(1 for l in lignes if l["panier"].statut == "actif"))


@app.route("/admin/paniers-abandonnes/<int:panier_id>/marquer", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire", "commandes")
def admin_panier_abandonne_marquer(panier_id):
    panier = PanierAbandonne.query.get_or_404(panier_id)
    action = request.form.get("action", "")
    if action == "relance":
        panier.statut = "relance"
        panier.nb_relances = (panier.nb_relances or 0) + 1
        panier.date_relance = datetime.utcnow()
    elif action == "abandon":
        panier.statut = "perdu"
    elif action == "actif":
        panier.statut = "actif"
    db.session.commit()
    return redirect(retour_admin("admin_paniers_abandonnes"))


# ---------------------------------------------------------------------------
# AVIS PRODUITS
#
# Les avis sont moderes : rien ne s'affiche avant validation dans l'admin.
# Un avis laisse par un client dont le telephone correspond a une commande
# livree est marque "achat verifie", ce qui pese beaucoup plus lourd.
# ---------------------------------------------------------------------------

@app.route("/produit/<int:produit_id>/avis", methods=["POST"])
def deposer_avis(produit_id):
    produit = Produit.query.get_or_404(produit_id)
    langue = langue_courante()

    nom = (request.form.get("nom_client") or "").strip()
    telephone = (request.form.get("telephone") or "").strip()
    commentaire = (request.form.get("commentaire") or "").strip()
    try:
        note = int(request.form.get("note") or 0)
    except ValueError:
        note = 0

    if len(nom) < 2 or not 1 <= note <= 5:
        flash(traduire("avis_incomplet", langue), "erreur")
        return redirect(url_for("voir_produit", produit_id=produit.id))

    # Un achat reellement livre sur ce produit vaut certification.
    verifie = False
    if telephone_valide(telephone):
        numero = telephone_e164(telephone)
        for commande in Commande.query.filter_by(statut="livree").all():
            if telephone_e164(commande.telephone) == numero and \
               any(l.produit_id == produit.id for l in commande.lignes):
                verifie = True
                break

    db.session.add(AvisProduit(
        produit_id=produit.id, nom_client=nom[:150], telephone=telephone[:30],
        note=note, commentaire=commentaire[:2000], achat_verifie=verifie))
    db.session.commit()

    flash(traduire("avis_merci", langue), "succes")
    return redirect(url_for("voir_produit", produit_id=produit.id))


@app.route("/admin/avis")
@connexion_requise
@roles_requis("proprietaire", "commandes")
def admin_avis():
    return render_template("admin/avis.html",
                           en_attente=AvisProduit.query.filter_by(approuve=False)
                                      .order_by(AvisProduit.date_creation.desc()).all(),
                           publies=AvisProduit.query.filter_by(approuve=True)
                                   .order_by(AvisProduit.date_creation.desc()).limit(50).all())


@app.route("/admin/avis/<int:avis_id>/<action>", methods=["POST"])
@connexion_requise
@roles_requis("proprietaire", "commandes")
def admin_avis_action(avis_id, action):
    avis = AvisProduit.query.get_or_404(avis_id)
    if action == "approuver":
        avis.approuve = True
        flash("Avis publie.", "succes")
    elif action == "masquer":
        avis.approuve = False
        flash("Avis retire de la boutique.", "succes")
    elif action == "supprimer":
        db.session.delete(avis)
        flash("Avis supprime.", "succes")
    db.session.commit()
    return redirect(retour_admin("admin_avis"))


# ---------------------------------------------------------------------------
# FACTURATION
#
# Les prix affiches sont TTC (vente au detail, paiement a la livraison). La
# facture reconstitue donc le HT et la TVA a partir du montant encaisse, et
# isole le droit de timbre pour que le total de la facture corresponde
# exactement a ce que le client a paye.
# ---------------------------------------------------------------------------

def attribuer_numero_facture(commande):
    """Numerotation sequentielle par annee, sans trou : FACT-2026-0001."""
    if commande.numero_facture:
        return commande.numero_facture

    annee = datetime.utcnow().year
    prefixe = "FACT-%s-" % annee
    derniere = (Commande.query.filter(Commande.numero_facture.like(prefixe + "%"))
                .order_by(Commande.numero_facture.desc()).first())
    suivant = int(derniere.numero_facture.rsplit("-", 1)[1]) + 1 if derniere else 1

    commande.numero_facture = "%s%04d" % (prefixe, suivant)
    commande.date_facture = datetime.utcnow()
    db.session.commit()
    return commande.numero_facture


def detail_facture(commande, params):
    taux = (params.taux_tva if params and params.taux_tva is not None else 19.0)
    timbre = (params.timbre_fiscal if params and params.timbre_fiscal is not None else 1.0)

    total_paye = round(commande.total or 0, 3)
    timbre = min(timbre, total_paye)          # jamais plus que le montant encaisse
    base_ttc = round(total_paye - timbre, 3)  # part soumise a TVA
    base_ht = round(base_ttc / (1 + taux / 100.0), 3) if taux else base_ttc
    montant_tva = round(base_ttc - base_ht, 3)

    lignes = []
    for l in commande.lignes:
        ligne_ttc = round((l.prix_unitaire or 0) * l.quantite, 3)
        ligne_ht = round(ligne_ttc / (1 + taux / 100.0), 3) if taux else ligne_ttc
        lignes.append({"nom": l.nom_produit, "quantite": l.quantite,
                       "pu_ht": round(ligne_ht / l.quantite, 3) if l.quantite else 0,
                       "total_ht": ligne_ht, "total_ttc": ligne_ttc})

    livraison_ttc = round(commande.frais_livraison or 0, 3)
    livraison_ht = round(livraison_ttc / (1 + taux / 100.0), 3) if taux else livraison_ttc

    return {"taux_tva": taux, "timbre": timbre, "base_ht": base_ht,
            "montant_tva": montant_tva, "total_ttc": total_paye, "lignes": lignes,
            "livraison_ht": livraison_ht, "livraison_ttc": livraison_ttc,
            "remise": round(commande.montant_reduction or 0, 3)}


@app.route("/admin/commandes/<int:commande_id>/facture")
@connexion_requise
@roles_requis("proprietaire", "commandes")
def admin_facture(commande_id):
    commande = Commande.query.get_or_404(commande_id)
    params = ParametreBoutique.query.first()
    attribuer_numero_facture(commande)
    return render_template("admin/facture.html", commande=commande, params=params,
                           f=detail_facture(commande, params))


# ---------------------------------------------------------------------------
# FLUX CATALOGUE ET SEO TECHNIQUE
#
# /feed.xml alimente le catalogue Meta (Commerce Manager) : c'est ce qui rend
# possibles les publicites dynamiques, le retargeting produit et la boutique
# Instagram. Format Google Shopping, accepte tel quel par Meta.
# ---------------------------------------------------------------------------

def echapper_xml(texte):
    return (str(texte or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


@app.route("/feed.xml")
def flux_catalogue():
    params = ParametreBoutique.query.first()
    marque = params.nom_boutique if params else "Maison des Garnitures"

    lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">',
              '<channel>',
              '<title>%s</title>' % echapper_xml(marque),
              '<link>%s</link>' % echapper_xml(url_for("accueil", _external=True)),
              '<description>Catalogue produits</description>']

    for p in Produit.query.filter_by(actif=True).all():
        if not p.prix_affiche or p.prix_affiche <= 0:
            continue  # Meta refuse les produits sans prix
        image = url_for("static", filename="img/produits/" + p.image, _external=True) if p.image else ""
        lignes += [
            "<item>",
            "<g:id>%s</g:id>" % echapper_xml(p.reference or p.id),
            "<g:title>%s</g:title>" % echapper_xml(p.nom),
            "<g:description>%s</g:description>" % echapper_xml(p.description or p.nom),
            "<g:link>%s</g:link>" % echapper_xml(url_for("voir_produit", produit_id=p.id, _external=True)),
            "<g:image_link>%s</g:image_link>" % echapper_xml(image),
            "<g:availability>%s</g:availability>" % ("in stock" if (p.stock or 0) > 0 else "out of stock"),
            "<g:condition>new</g:condition>",
            "<g:price>%.3f TND</g:price>" % p.prix,
            "<g:brand>%s</g:brand>" % echapper_xml(marque),
            "<g:inventory>%s</g:inventory>" % (p.stock or 0),
        ]
        for photo in p.galerie[1:11]:   # Meta accepte jusqu'a 10 photos additionnelles
            lignes.append("<g:additional_image_link>%s</g:additional_image_link>"
                          % echapper_xml(url_for("static", filename="img/produits/" + photo, _external=True)))
        if p.en_promo:
            lignes.append("<g:sale_price>%.3f TND</g:sale_price>" % p.prix_promo)
        if p.categorie:
            lignes.append("<g:product_type>%s</g:product_type>" % echapper_xml(p.categorie.nom))
        lignes.append("</item>")

    lignes += ["</channel>", "</rss>"]
    return app.response_class("\n".join(lignes), mimetype="application/xml")


@app.route("/sitemap.xml")
def plan_du_site():
    urls = [url_for("accueil", _external=True), url_for("suivi_commande", _external=True)]
    urls += [url_for("voir_categorie", slug=c.slug, _external=True)
             for c in Categorie.query.filter_by(actif=True).all()]
    urls += [url_for("voir_page", slug=p.slug, _external=True)
             for p in PageStatique.query.filter_by(actif=True).all()]
    urls += [url_for("voir_produit", produit_id=p.id, _external=True)
             for p in Produit.query.filter_by(actif=True).all()]

    corps = "".join("<url><loc>%s</loc></url>" % echapper_xml(u) for u in urls)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>' % corps)
    return app.response_class(xml, mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    contenu = "\n".join([
        "User-agent: *",
        "Disallow: /admin",
        "Disallow: /panier",
        "Disallow: /commander",
        "Sitemap: " + url_for("plan_du_site", _external=True),
        "",
    ])
    return app.response_class(contenu, mimetype="text/plain")


def migrer_colonnes_manquantes():
    """SQLite ne gere pas les migrations : on ajoute les colonnes absentes a la main."""
    nouvelles = {
        "parametre_boutique": [
            ("meta_capi_token", "TEXT DEFAULT ''"),
            ("meta_test_event_code", "VARCHAR(50) DEFAULT ''"),
            ("google_analytics_id", "VARCHAR(40) DEFAULT ''"),
            ("google_verification", "VARCHAR(120) DEFAULT ''"),
            ("meta_domain_verification", "VARCHAR(120) DEFAULT ''"),
            ("clarity_id", "VARCHAR(40) DEFAULT ''"),
            ("modele_whatsapp_confirmation", "TEXT DEFAULT ''"),
            ("modele_whatsapp_expedition", "TEXT DEFAULT ''"),
            ("modele_whatsapp_relance", "TEXT DEFAULT ''"),
            ("raison_sociale", "VARCHAR(200) DEFAULT ''"),
            ("matricule_fiscal", "VARCHAR(60) DEFAULT ''"),
            ("registre_commerce", "VARCHAR(60) DEFAULT ''"),
            ("taux_tva", "FLOAT DEFAULT 19.0"),
            ("timbre_fiscal", "FLOAT DEFAULT 1.0"),
            ("seuil_alerte_stock", "INTEGER DEFAULT 1"),
            ("email", "VARCHAR(150) DEFAULT ''"),
        ],
        "commande": [("telephone2", "VARCHAR(40)"), ("email", "VARCHAR(150)"),
                     ("note_privee", "TEXT"), ("supprimee_le", "DATETIME"),
                     ("imprimee_le", "DATETIME"),
                     ("transporteur_bordereau", "VARCHAR(80)"),
            ("event_id_purchase", "VARCHAR(60)"),
            ("numero_facture", "VARCHAR(40)"),
            ("utm_source", "VARCHAR(120)"),
            ("utm_medium", "VARCHAR(120)"),
            ("utm_campagne", "VARCHAR(200)"),
            ("utm_adset", "VARCHAR(200)"),
            ("utm_annonce", "VARCHAR(200)"),
            ("date_facture", "DATETIME"),
        ],
        "produit": [("offre_panier", "BOOLEAN DEFAULT 0"),
                    ("cout", "FLOAT DEFAULT 0"),
                    ("date_maj_stock", "DATETIME"), ("ordre", "INTEGER DEFAULT 0"),
                    ("prix_livraison", "FLOAT"), ("cout_livraison", "FLOAT"),
                    ("seuil_alerte", "INTEGER"), ("stock_entrant", "INTEGER DEFAULT 0"),
                    ("stock_abime", "INTEGER DEFAULT 0"),
                    ("vente_en_rupture", "BOOLEAN DEFAULT 0"),
                    ("lot_quantite", "INTEGER"), ("lot_type", "VARCHAR(20) DEFAULT 'pourcentage'"),
                    ("lot_valeur", "FLOAT DEFAULT 0"),
                    ("slug", "VARCHAR(220)"), ("meta_titre", "VARCHAR(200)"),
                    ("meta_description", "VARCHAR(320)"), ("produits_lies", "TEXT"),
                    ("nom_ar", "VARCHAR(200)"),
                    ("queue_mm", "FLOAT"), ("coupe_mm", "FLOAT"),
                    ("longueur_mm", "FLOAT"),
                    ("video", "VARCHAR(255)"), ("video_url", "VARCHAR(500)"),
                    ("video_verticale", "BOOLEAN DEFAULT 0")],
        "utilisateur": [("alertes_lues_le", "DATETIME"),
                        ("prenom", "VARCHAR(120)"), ("telephone", "VARCHAR(40)"),
                        ("permissions", "TEXT"),
                        ("doit_changer_mdp", "BOOLEAN DEFAULT 0")],
        "categorie": [("nom_ar", "VARCHAR(120)"),
                      ("actif", "BOOLEAN DEFAULT 1"), ("description", "TEXT"),
                      ("meta_titre", "VARCHAR(200)"), ("meta_description", "VARCHAR(320)"),
                      ("parent_id", "INTEGER")],
        "ligne_commande": [("cout_unitaire", "FLOAT DEFAULT 0")],
        "transporteur": [("config", "TEXT")],
    }
    # Bordereaux orphelins : un changement de transporteur anterieur a la
    # colonne « transporteur_bordereau » a pu laisser l'etiquette du livreur
    # precedent. On l'efface une fois pour toutes ; la condition ne se
    # represente plus ensuite.
    def nettoyer_bordereaux_perimes():
        try:
            perimees = Commande.query.filter(
                Commande.lien_bordereau.isnot(None),
                db.func.coalesce(Commande.transporteur_bordereau,
                                 "First Delivery") != Commande.transporteur).all()
        except Exception:
            return
        for commande in perimees:
            oublier_expedition(commande)
            app.logger.info("Bordereau perime efface : %s", commande.numero)
        if perimees:
            db.session.commit()

    # Le rattrapage vaut pour les DEUX moteurs. Il avait ete reserve a SQLite
    # parce qu'il interrogeait « PRAGMA table_info », propre a SQLite ; mais
    # db.create_all() ne cree que les TABLES manquantes, jamais les COLONNES
    # d'une table qui existe deja. Sur PostgreSQL, une colonne ajoutee au
    # modele apres la migration faisait donc tomber le demarrage :
    # « column parametre_boutique.meta_domain_verification does not exist ».
    inspecteur = db.inspect(db.engine)
    postgres = db.engine.dialect.name == "postgresql"

    def definition_adaptee(definition):
        """Les types SQLite ci-dessus n'ont pas tous cours sur PostgreSQL."""
        if not postgres:
            return definition
        return (definition.replace("DATETIME", "TIMESTAMP")
                          .replace("BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT TRUE")
                          .replace("BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT FALSE"))

    def ajouter(table, nom, definition):
        db.session.execute(db.text(
            "ALTER TABLE %s ADD COLUMN %s %s" % (table, nom, definition)))
        app.logger.info("Colonne ajoutee : %s.%s", table, nom)

    for table, colonnes in nouvelles.items():
        if not inspecteur.has_table(table):
            continue
        existantes = {c["name"] for c in inspecteur.get_columns(table)}
        for nom, definition in colonnes:
            if nom not in existantes:
                ajouter(table, nom, definition_adaptee(definition))

    # Filet de securite : la liste ci-dessus se tient a la main, et un oubli
    # ne se voit pas en local (le fichier SQLite porte deja la colonne). On
    # compare donc aussi chaque modele a sa table reelle. Ajout en NULL
    # autorise : une colonne obligatoire ne peut pas s'ajouter a des lignes
    # existantes sans valeur.
    for modele in db.Model.registry.mappers:
        table = modele.local_table
        if table is None or not inspecteur.has_table(table.name):
            continue
        existantes = {c["name"] for c in inspecteur.get_columns(table.name)}
        for colonne in table.columns:
            if colonne.name in existantes:
                continue
            ajouter(table.name, colonne.name,
                    colonne.type.compile(db.engine.dialect))

    db.session.commit()
    nettoyer_bordereaux_perimes()


def initialiser_donnees():
    db.create_all()
    migrer_colonnes_manquantes()
    if not ParametreBoutique.query.first(): db.session.add(ParametreBoutique(**MODELES_MESSAGES_DEFAUT))
    params_existants = ParametreBoutique.query.first()
    if params_existants:
        for champ, defaut in MODELES_MESSAGES_DEFAUT.items():
            if not getattr(params_existants, champ, ""):
                setattr(params_existants, champ, defaut)
    if not Utilisateur.query.filter_by(role="proprietaire").first(): db.session.add(Utilisateur(nom="Administrateur", email="admin@maisondesgarnitures.tn", mot_de_passe_hash=generate_password_hash("ChangeMoi123!"), role="proprietaire"))
    if Categorie.query.count() == 0:
        for i, nom in enumerate(["Poignees et boutons", "Charnieres", "Coulisses de tiroir", "Serrures et verrous", "Accessoires cuisine", "Accessoires dressing", "Pieds de meubles", "Quincaillerie generale", "Outils et accessoires", "Lames et consommables"]): db.session.add(Categorie(nom=nom, slug=nom.lower().replace(" ", "-"), ordre=i))
        db.session.commit()
    db.session.commit()

with app.app_context(): initialiser_donnees()

if __name__ == "__main__":
    # Le debogueur de Flask permet d'executer du code depuis une page d'erreur :
    # il ne doit jamais tourner sur une machine joignable depuis Internet.
    # Pour servir la boutique en vrai, lance « python servir.py ».
    app.run(debug=not EN_PRODUCTION, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
