/*
 * Fiche produit : galerie, variantes, offres, quantite, totaux en direct
 * et achat en une etape.
 *
 * Les variables GOUVERNORATS, PRIX_BASE, FRAIS_LIVRAISON... sont definies
 * dans le gabarit juste avant le chargement de ce fichier.
 */
(function () {
  var form = document.getElementById('formAchat');
  var champQuantite = document.getElementById('champQuantite');

  // ---------- Galerie ----------
  var cadreVideo = document.getElementById('cadreVideo');
  var cadrePhoto = document.querySelector('.galerie-produit .image-principale');

  function arreterVideo() {
    if (!cadreVideo) return;
    var lecteur = cadreVideo.querySelector('video');
    if (lecteur) lecteur.pause();
    // Un iframe continue de jouer meme cache : on le recharge pour le couper.
    var cadre = cadreVideo.querySelector('iframe');
    if (cadre) cadre.src = cadre.src;
  }

  document.querySelectorAll('.vignette').forEach(function (v) {
    v.addEventListener('click', function () {
      document.querySelectorAll('.vignette').forEach(function (x) { x.classList.remove('active'); });
      this.classList.add('active');

      if (this.dataset.video) {
        if (cadreVideo) cadreVideo.hidden = false;
        if (cadrePhoto) cadrePhoto.hidden = true;
        return;
      }

      arreterVideo();
      if (cadreVideo) cadreVideo.hidden = true;
      if (cadrePhoto) cadrePhoto.hidden = false;
      var principale = document.getElementById('photoPrincipale');
      if (principale && this.dataset.photo) principale.src = this.dataset.photo;
    });
  });

  // ---------- Gouvernorats et delegations ----------
  var selectGouv = document.getElementById('selectGouvernorat');
  // La ville a ete retiree du formulaire : une delegation absente de la base
  // du transporteur empechait d'imprimer son bordereau. Le gouvernorat suffit
  // a router le colis, l'adresse libre porte le detail.
  if (selectGouv && typeof GOUVERNORATS === 'object') {
    Object.keys(GOUVERNORATS).sort().forEach(function (g) {
      var o = document.createElement('option');
      o.value = g; o.textContent = g;
      selectGouv.appendChild(o);
    });
  }

  // ---------- Variantes ----------
  var variantePrix = null;
  var source = document.getElementById('donneesVariantes');
  if (source) {
    var variantes = JSON.parse(source.textContent);
    var champVariante = document.getElementById('varianteChoisie');
    var etat = document.getElementById('etatVariante');
    var choix = {};

    document.querySelectorAll('.groupe-option').forEach(function (groupe) {
      groupe.querySelectorAll('.valeur-option').forEach(function (b) {
        b.addEventListener('click', function () {
          groupe.querySelectorAll('.valeur-option').forEach(function (x) { x.classList.remove('choisie'); });
          this.classList.add('choisie');
          choix[groupe.dataset.option] = this.dataset.valeur;
          majVariante();
        });
      });
    });

    function majVariante() {
      var groupes = document.querySelectorAll('.groupe-option');
      var selection = [];
      groupes.forEach(function (g) { if (choix[g.dataset.option]) selection.push(choix[g.dataset.option]); });
      if (selection.length < groupes.length) { champVariante.value = ''; return; }

      var trouvee = variantes.find(function (v) {
        return v.valeurs.length === selection.length
            && v.valeurs.every(function (x, i) { return x === selection[i]; });
      });
      if (!trouvee) { champVariante.value = ''; return; }

      champVariante.value = trouvee.id;
      variantePrix = trouvee.prix;

      // Le prix barre appartient a la variante : sans cela, la fiche gardait
      // celui du produit et annoncait une remise qui ne correspondait a rien.
      var barre = document.getElementById('prixBarre');
      var badge = document.getElementById('badgeRemise');
      var enPromo = trouvee.barre > trouvee.prix;
      if (barre) {
        barre.hidden = !enPromo;
        if (enPromo) barre.textContent = trouvee.barre.toFixed(2) + ' TND';
      }
      if (badge) {
        badge.hidden = !enPromo;
        if (enPromo) {
          var remise = Math.round((trouvee.barre - trouvee.prix) / trouvee.barre * 100);
          badge.textContent = '-' + remise + ' % ' + (badge.dataset.mot || 'remise');
        }
      }

      if (trouvee.image) {
        var principale = document.getElementById('photoPrincipale');
        if (principale) principale.src = '/static/img/produits/' + trouvee.image;
      }
      // On indique seulement si la combinaison est disponible, jamais la quantite.
      if (trouvee.stock <= 0 && !PRECOMMANDE) {
        etat.textContent = ETIQUETTE_EPUISE;
        etat.className = 'etat-variante indisponible';
      } else {
        etat.textContent = ETIQUETTE_STOCK;
        etat.className = 'etat-variante disponible';
      }
      majTotaux();
    }

    document.querySelectorAll('.groupe-option').forEach(function (g) {
      var premier = g.querySelector('.valeur-option');
      if (premier) premier.click();
    });
  }

  // ---------- Offres ----------
  document.querySelectorAll('.carte-offre input[name="lot_id"]').forEach(function (r) {
    r.addEventListener('change', function () {
      document.querySelectorAll('.carte-offre').forEach(function (x) { x.classList.remove('choisie'); });
      this.closest('.carte-offre').classList.add('choisie');
      majTotaux();
    });
  });

  // ---------- Quantite ----------
  if (champQuantite) {
    var moins = document.querySelector('.compteur-quantite .moins');
    var plus = document.querySelector('.compteur-quantite .plus');
    if (moins) moins.addEventListener('click', function () {
      champQuantite.value = Math.max(1, parseInt(champQuantite.value, 10) - 1);
      majTotaux();
    });
    if (plus) plus.addEventListener('click', function () {
      champQuantite.value = (parseInt(champQuantite.value, 10) || 0) + 1;
      majTotaux();
    });

    // Le client peut aussi taper directement la quantite : plus besoin de
    // cliquer 500 fois pour commander 500 pieces.
    champQuantite.addEventListener('input', function () {
      var valeur = this.value.replace(/[^0-9]/g, '');
      this.value = valeur;
      majTotaux();
    });
    champQuantite.addEventListener('blur', function () {
      if (!this.value || parseInt(this.value, 10) < 1) {
        this.value = 1;
        majTotaux();
      }
    });
  }

  // ---------- Totaux et jauge de livraison gratuite ----------
  function prixUnitaire() {
    var offre = document.querySelector('.carte-offre input[name="lot_id"]:checked');
    if (offre) return parseFloat(offre.dataset.prix);

    var base = variantePrix !== null ? variantePrix : PRIX_BASE;
    // Prix degressif : on retient le dernier palier atteint par la quantite.
    if (typeof PALIERS !== 'undefined' && PALIERS.length) {
      var q = champQuantite ? (parseInt(champQuantite.value, 10) || 1) : 1;
      PALIERS.forEach(function (p) { if (q >= p.min) base = p.prix; });
    }
    return base;
  }

  function surlignerPalier() {
    var lignes = document.querySelectorAll('.grille-paliers tr');
    if (!lignes.length) return;
    var q = champQuantite ? (parseInt(champQuantite.value, 10) || 1) : 1;

    var actif = lignes[0];
    lignes.forEach(function (l) {
      var min = parseInt(l.dataset.min || '1', 10);
      if (q >= min) actif = l;
    });
    lignes.forEach(function (l) { l.classList.toggle('palier-actif', l === actif); });
  }

  function majTotaux() {
    var quantite = champQuantite ? (parseInt(champQuantite.value, 10) || 1) : 1;
    var sous = prixUnitaire() * quantite;

    // Au-dessus du seuil, la livraison est offerte, sauf port impose par produit.
    var port = FRAIS_LIVRAISON;
    if (!PORT_FIXE && SEUIL_GRATUIT > 0 && sous >= SEUIL_GRATUIT) port = 0;

    ecrire('sousTotal', sous);
    ecrire('fraisLivraison', port);
    ecrire('totalAchat', sous + port);

    var prixAffiche = document.getElementById('prixAffiche');
    if (prixAffiche) prixAffiche.textContent = prixUnitaire().toFixed(2) + ' TND';

    majJauge(sous, port);
    surlignerPalier();
  }

  function ecrire(id, valeur) {
    var e = document.getElementById(id);
    if (e) e.textContent = valeur.toFixed(2) + ' TND';
  }

  function majJauge(sous, port) {
    var jauge = document.getElementById('jaugeLivraison');
    if (!jauge || SEUIL_GRATUIT <= 0) return;
    var barre = document.getElementById('barreLivraison');
    var texte = document.getElementById('texteLivraison');

    if (port === 0) {
      barre.style.width = '100%';
      jauge.classList.add('atteint');
      texte.textContent = TXT_GRATUIT;
    } else {
      var reste = SEUIL_GRATUIT - sous;
      barre.style.width = Math.min(100, (sous / SEUIL_GRATUIT) * 100) + '%';
      jauge.classList.remove('atteint');
      texte.textContent = TXT_RESTE.replace('{montant}', reste.toFixed(2));
    }
  }

  // ---------- Ajout au panier, sans quitter la page ----------
  var boutonPanier = document.getElementById('boutonPanier');
  if (boutonPanier && form) {
    boutonPanier.addEventListener('click', function () {
      // On rejoue le formulaire vers l'adresse du panier : meme variante,
      // meme offre, meme quantite, mais sans les coordonnees.
      var donnees = new FormData();
      donnees.append('quantite', champQuantite ? champQuantite.value : 1);
      var v = document.getElementById('varianteChoisie');
      if (v && v.value) donnees.append('variante_id', v.value);
      var offre = document.querySelector('.carte-offre input[name="lot_id"]:checked');
      if (offre) donnees.append('lot_id', offre.value);

      var identifiant = (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID().replace(/-/g, '')
        : String(Date.now()) + Math.random().toString(16).slice(2);
      donnees.append('event_id', identifiant);

      if (window.fbq) {
        var q = parseInt(champQuantite ? champQuantite.value : 1, 10) || 1;
        fbq('track', 'AddToCart', {
          currency: 'TND', value: prixUnitaire() * q, content_type: 'product',
          content_name: form.dataset.nom || '', content_ids: [form.dataset.ref || '']
        }, { eventID: identifiant });
      }

      fetch(form.dataset.panier, { method: 'POST', body: donnees })
        .then(function () { window.location.href = '/panier'; })
        .catch(function () { window.location.href = '/panier'; });
    });
  }

  // ---------- Sur telephone, la barre du bas amene au formulaire ----------
  var lien = document.getElementById('allerAuFormulaire');
  if (lien && form) {
    lien.addEventListener('click', function () {
      form.scrollIntoView({ behavior: 'smooth', block: 'center' });
      var premier = form.querySelector('input[name="nom_client"]');
      if (premier) setTimeout(function () { premier.focus(); }, 400);
    });
  }

  majTotaux();
})();
