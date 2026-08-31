/* Remplit gouvernorat et ville dans l'editeur de commande, en conservant
   la valeur deja enregistree meme si elle ne figure pas dans la liste
   (une commande ancienne peut porter une orthographe differente).

   L'editeur s'ouvre aussi en panneau lateral : le remplissage est donc une
   fonction rejouable, et non un bloc qui ne tourne qu'au chargement. */
(function () {
  'use strict';

  function ajouter(select, valeur, choisie) {
    var o = document.createElement('option');
    o.value = valeur;
    o.textContent = valeur;
    if (choisie) o.selected = true;
    select.appendChild(o);
  }

  function remplir(racine) {
    var portee = racine || document;
    var selGouv = portee.querySelector('#selectGouvernorat');
    var selVille = portee.querySelector('#selectVille');
    if (!selGouv || !selVille || typeof GOUVERNORATS !== 'object') return;
    if (selGouv.dataset.rempli === '1') return;
    selGouv.dataset.rempli = '1';

    Object.keys(GOUVERNORATS).sort().forEach(function (g) {
      ajouter(selGouv, g, g === GOUV_ACTUEL);
    });
    // Valeur enregistree absente de la liste : on la garde plutot que de l'effacer.
    if (GOUV_ACTUEL && !GOUVERNORATS[GOUV_ACTUEL]) ajouter(selGouv, GOUV_ACTUEL, true);

    function remplirVilles(villeChoisie) {
      selVille.innerHTML = '';
      var villes = GOUVERNORATS[selGouv.value] || [];
      villes.forEach(function (v) { ajouter(selVille, v, v === villeChoisie); });
      if (villeChoisie && villes.indexOf(villeChoisie) === -1) ajouter(selVille, villeChoisie, true);
      if (!villes.length && !villeChoisie) ajouter(selVille, '', true);
    }

    remplirVilles(VILLE_ACTUELLE);
    selGouv.addEventListener('change', function () { remplirVilles(null); });
  }

  window.remplirGouvernorats = remplir;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { remplir(); });
  } else {
    remplir();
  }
})();
