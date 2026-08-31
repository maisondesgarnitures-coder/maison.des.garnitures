/*
 * Reordonnancement par glisser-deposer.
 *
 * S'active sur toute table portant data-reordonner="produits" ou "categories".
 * Chaque ligne doit porter data-id. Le nouvel ordre part au serveur des que
 * la ligne est relachee : pas de bouton "enregistrer" a oublier.
 */
(function () {
  var table = document.querySelector('[data-reordonner]');
  if (!table) return;

  var quoi = table.dataset.reordonner;
  var corps = table.tBodies[0] || table;
  var lignes = corps.querySelectorAll('tr[data-id]');
  if (!lignes.length) return;

  var enCours = null;
  var indicateur = creerIndicateur();

  lignes.forEach(function (ligne) {
    var poignee = ligne.querySelector('.poignee');
    if (!poignee) return;

    // On ne rend la ligne deplacable qu'au contact de la poignee : sinon
    // impossible de selectionner du texte dans le tableau.
    poignee.addEventListener('mousedown', function () { ligne.draggable = true; });
    poignee.addEventListener('touchstart', function () { ligne.draggable = true; }, { passive: true });
    document.addEventListener('mouseup', function () { ligne.draggable = false; });

    ligne.addEventListener('dragstart', function (e) {
      enCours = ligne;
      ligne.classList.add('en-deplacement');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', ligne.dataset.id);
    });

    ligne.addEventListener('dragend', function () {
      ligne.classList.remove('en-deplacement');
      ligne.draggable = false;
      corps.querySelectorAll('.cible-survol').forEach(function (x) {
        x.classList.remove('cible-survol');
      });
      enregistrer(ligne.dataset.rayon);
    });

    ligne.addEventListener('dragover', function (e) {
      if (!enCours || enCours === ligne) return;
      // La liste est groupee par rayon : deplacer un article d'un rayon a
      // l'autre le rangerait ailleurs sans le dire. On refuse la sortie.
      if (ligne.dataset.rayon !== enCours.dataset.rayon) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';

      var cadre = ligne.getBoundingClientRect();
      var apres = (e.clientY - cadre.top) > cadre.height / 2;
      corps.insertBefore(enCours, apres ? ligne.nextSibling : ligne);

      corps.querySelectorAll('.cible-survol').forEach(function (x) {
        x.classList.remove('cible-survol');
      });
      ligne.classList.add('cible-survol');
    });

    ligne.addEventListener('drop', function (e) { e.preventDefault(); });
  });

  function enregistrer(rayon) {
    // On n'envoie que le rayon touche : le serveur redistribue les positions
    // deja occupees par ces lignes-la, sans deranger les autres rayons.
    var toutes = corps.querySelectorAll('tr[data-id]');
    var ordre = Array.prototype.filter.call(toutes, function (l) {
      return rayon === undefined || l.dataset.rayon === rayon;
    }).map(function (l) { return l.dataset.id; });
    if (!ordre.length) return;

    indicateur.textContent = 'Enregistrement...';
    indicateur.className = 'indicateur-ordre visible';

    fetch('/admin/reordonner/' + quoi, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ordre: ordre })
    }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function () {
      indicateur.textContent = 'Ordre enregistre';
      indicateur.className = 'indicateur-ordre visible succes';
      setTimeout(function () { indicateur.className = 'indicateur-ordre'; }, 1800);
    }).catch(function () {
      indicateur.textContent = 'Echec : recharge la page';
      indicateur.className = 'indicateur-ordre visible echec';
    });
  }

  function creerIndicateur() {
    var e = document.createElement('div');
    e.className = 'indicateur-ordre';
    document.body.appendChild(e);
    return e;
  }
})();
