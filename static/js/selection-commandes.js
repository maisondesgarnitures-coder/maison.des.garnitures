/* Selection multiple dans la liste des commandes.

   Les cases cochees alimentent une barre flottante, puis deux fenetres :
   impression des bordereaux et modification groupee. */
(function () {
  'use strict';

  var cases = Array.prototype.slice.call(document.querySelectorAll('.case-commande'));
  if (!cases.length) return;

  var barre = document.getElementById('barreSelection');
  var toutCocher = document.getElementById('toutCocher');
  var vider = document.getElementById('viderSelection');
  var formSuppression = document.getElementById('formSuppressionGroupe');
  var formEdition = document.getElementById('formEditionGroupe');
  var fenetreImpression = document.getElementById('fenetreImpression');
  var fenetreEdition = document.getElementById('fenetreEdition');
  var formImpression = document.getElementById('formImpression');
  if (!barre) return;

  function choisies() {
    return cases.filter(function (c) { return c.checked; });
  }
  function identifiants() {
    return choisies().map(function (c) { return c.value; });
  }

  function champsCaches(formulaire, ids) {
    if (!formulaire) return;
    formulaire.querySelectorAll('input[name="ids"]').forEach(function (e) { e.remove(); });
    ids.forEach(function (id) {
      var champ = document.createElement('input');
      champ.type = 'hidden';
      champ.name = 'ids';
      champ.value = id;
      formulaire.appendChild(champ);
    });
  }

  function rafraichir() {
    var ids = identifiants();
    barre.hidden = ids.length === 0;

    document.querySelectorAll('.nb-choisies').forEach(function (e) {
      e.textContent = ids.length;
    });
    // Rappel visuel des numeros retenus, comme sur la fenetre de Converty.
    document.querySelectorAll('.pastilles-selection').forEach(function (zone) {
      zone.innerHTML = '';
      choisies().slice(0, 40).forEach(function (c) {
        var ligne = c.closest('tr');
        var pastille = document.createElement('span');
        pastille.className = 'pastille-choisie';
        pastille.textContent = ligne ? ligne.children[1].textContent.trim() : c.value;
        zone.appendChild(pastille);
      });
    });

    champsCaches(formSuppression, ids);
    champsCaches(formEdition, ids);

    champsCaches(formImpression, ids);

    if (toutCocher) {
      toutCocher.checked = ids.length === cases.length && cases.length > 0;
      toutCocher.indeterminate = ids.length > 0 && ids.length < cases.length;
    }
  }

  cases.forEach(function (c) { c.addEventListener('change', rafraichir); });
  if (toutCocher) {
    toutCocher.addEventListener('change', function () {
      cases.forEach(function (c) { c.checked = toutCocher.checked; });
      rafraichir();
    });
  }
  if (vider) {
    vider.addEventListener('click', function () {
      cases.forEach(function (c) { c.checked = false; });
      rafraichir();
    });
  }

  function ouvrir(fenetre) {
    if (!fenetre) return;
    rafraichir();
    if (typeof fenetre.showModal === 'function') fenetre.showModal();
    else fenetre.setAttribute('open', '');
  }
  var boutonImpression = document.getElementById('ouvrirImpression');
  var boutonEdition = document.getElementById('ouvrirEdition');
  if (boutonImpression) boutonImpression.addEventListener('click', function () { ouvrir(fenetreImpression); });
  if (boutonEdition) boutonEdition.addEventListener('click', function () { ouvrir(fenetreEdition); });
  document.querySelectorAll('.fermer-fenetre').forEach(function (b) {
    b.addEventListener('click', function () {
      var f = b.closest('dialog');
      if (f) { if (typeof f.close === 'function') f.close(); else f.removeAttribute('open'); }
    });
  });
  var choixParPage = document.getElementById('choixParPage');
  if (choixParPage) {
    choixParPage.addEventListener('change', function () {
      var url = new URL(window.location.href);
      url.searchParams.set('par_page', choixParPage.value);
      url.searchParams.delete('page');
      window.location.href = url.toString();
    });
  }

  rafraichir();
})();
