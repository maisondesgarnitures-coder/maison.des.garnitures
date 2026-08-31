/*
 * Bande de photos d'un produit : ajouter, supprimer, reordonner.
 * La premiere photo de la bande est la photo principale.
 * Chaque action est enregistree immediatement.
 */
(function () {
  var bande = document.getElementById('bandePhotos');
  if (!bande) return;

  var produit = bande.dataset.produit;
  var carteAjout = document.getElementById('carteAjout');
  var champ = document.getElementById('champPhotos');
  var enCours = null;
  var indicateur = creerIndicateur();

  activer();

  // ---------- Ajout ----------
  if (champ) {
    champ.addEventListener('change', function () {
      if (!this.files.length) return;
      var donnees = new FormData();
      Array.prototype.forEach.call(this.files, function (f) { donnees.append('photos', f); });

      signaler('Envoi des photos...');
      fetch('/admin/produits/' + produit + '/photos/ajouter', {
        method: 'POST', body: donnees
      }).then(reponseJson).then(function (j) {
        redessiner(j.photos);
        signaler(j.ajoutees + ' photo(s) ajoutee(s)', 'succes');
      }).catch(function () {
        signaler('Echec de l envoi', 'echec');
      });
      this.value = '';
    });
  }

  // ---------- Suppression ----------
  bande.addEventListener('click', function (e) {
    if (!e.target.classList.contains('supprimer-photo')) return;
    var carte = e.target.closest('.carte-photo');
    if (!carte) return;
    if (!window.confirm('Supprimer cette photo ?')) return;

    signaler('Suppression...');
    fetch('/admin/produits/' + produit + '/photos/supprimer', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fichier: carte.dataset.fichier })
    }).then(reponseJson).then(function () {
      carte.remove();
      marquerPrincipale();
      signaler('Photo supprimee', 'succes');
    }).catch(function () {
      signaler('Echec de la suppression', 'echec');
    });
  });

  // ---------- Reordonnancement ----------
  function activer() {
    bande.querySelectorAll('.carte-photo').forEach(function (carte) {
      var poignee = carte.querySelector('.poignee-photo');
      if (!poignee) return;

      poignee.addEventListener('mousedown', function () { carte.draggable = true; });
      poignee.addEventListener('touchstart', function () { carte.draggable = true; }, { passive: true });
      document.addEventListener('mouseup', function () { carte.draggable = false; });

      carte.addEventListener('dragstart', function (e) {
        enCours = carte;
        carte.classList.add('en-deplacement');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', carte.dataset.fichier);
      });

      carte.addEventListener('dragend', function () {
        carte.classList.remove('en-deplacement');
        carte.draggable = false;
        marquerPrincipale();
        enregistrerOrdre();
      });

      carte.addEventListener('dragover', function (e) {
        if (!enCours || enCours === carte) return;
        e.preventDefault();
        var cadre = carte.getBoundingClientRect();
        var apres = (e.clientX - cadre.left) > cadre.width / 2;
        bande.insertBefore(enCours, apres ? carte.nextSibling : carte);
      });

      carte.addEventListener('drop', function (e) { e.preventDefault(); });
    });
    marquerPrincipale();
  }

  function enregistrerOrdre() {
    var ordre = Array.prototype.map.call(
      bande.querySelectorAll('.carte-photo'), function (c) { return c.dataset.fichier; });

    signaler('Enregistrement...');
    fetch('/admin/produits/' + produit + '/photos/ordre', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ordre: ordre })
    }).then(reponseJson).then(function () {
      signaler('Ordre enregistre', 'succes');
    }).catch(function () {
      signaler('Echec : recharge la page', 'echec');
    });
  }

  // ---------- Rendu ----------
  function redessiner(photos) {
    bande.querySelectorAll('.carte-photo').forEach(function (c) { c.remove(); });
    photos.forEach(function (p) {
      var carte = document.createElement('div');
      carte.className = 'carte-photo';
      carte.dataset.fichier = p.fichier;
      carte.innerHTML =
        '<span class="poignee-photo" title="Glisser pour deplacer">&#10495;</span>' +
        '<button type="button" class="supprimer-photo" title="Supprimer">&times;</button>' +
        '<img src="' + p.url + '" alt="">' +
        '<span class="etiquette-principale">Principale</span>';
      bande.insertBefore(carte, carteAjout);
    });
    activer();
  }

  function marquerPrincipale() {
    var cartes = bande.querySelectorAll('.carte-photo');
    cartes.forEach(function (c, i) { c.classList.toggle('principale', i === 0); });
  }

  function reponseJson(r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }

  function creerIndicateur() {
    var e = document.createElement('div');
    e.className = 'indicateur-ordre';
    document.body.appendChild(e);
    return e;
  }

  function signaler(texte, etat) {
    indicateur.textContent = texte;
    indicateur.className = 'indicateur-ordre visible ' + (etat || '');
    if (etat === 'succes') {
      setTimeout(function () { indicateur.className = 'indicateur-ordre'; }, 1800);
    }
  }
})();
