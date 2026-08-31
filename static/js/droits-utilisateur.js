/* Grille des droits d'un utilisateur.

   Trois commodites : la case « Tout » d'une ligne, celle de tout le tableau,
   et le remplissage automatique quand on change de role. Rien n'est impose :
   la grille reste modifiable case par case apres coup. */
(function () {
  'use strict';

  function lancer() {
    var tableau = document.querySelector('.tableau-droits');
    if (!tableau || tableau.dataset.pret === '1') return;
    tableau.dataset.pret = '1';

    var lignes = Array.prototype.slice.call(tableau.querySelectorAll('tr[data-rubrique]'));
    var toutCocher = document.getElementById('toutCocherDroits');

    function casesDe(ligne) {
      return Array.prototype.slice.call(ligne.querySelectorAll('input[data-action]'));
    }
    function toutesLesCases() {
      return lignes.reduce(function (liste, l) { return liste.concat(casesDe(l)); }, []);
    }

    function rafraichir() {
      lignes.forEach(function (ligne) {
        var cases = casesDe(ligne);
        var tout = ligne.querySelector('.tout-la-ligne');
        if (!tout) return;
        tout.checked = cases.length > 0 && cases.every(function (c) { return c.checked; });
        tout.indeterminate = !tout.checked && cases.some(function (c) { return c.checked; });
      });
      if (toutCocher) {
        var cases = toutesLesCases();
        toutCocher.checked = cases.length > 0 && cases.every(function (c) { return c.checked; });
        toutCocher.indeterminate = !toutCocher.checked
                                   && cases.some(function (c) { return c.checked; });
      }
    }

    lignes.forEach(function (ligne) {
      var tout = ligne.querySelector('.tout-la-ligne');
      if (tout) {
        tout.addEventListener('change', function () {
          casesDe(ligne).forEach(function (c) { c.checked = tout.checked; });
          rafraichir();
        });
      }
      casesDe(ligne).forEach(function (c) { c.addEventListener('change', rafraichir); });
    });

    if (toutCocher) {
      toutCocher.addEventListener('change', function () {
        toutesLesCases().forEach(function (c) { c.checked = toutCocher.checked; });
        rafraichir();
      });
    }

    // Changer de role repositionne la grille sur ce que ce role donne d'office.
    var choixRole = document.querySelector('select[data-droits-role]');
    if (choixRole && typeof DROITS_PAR_ROLE === 'object') {
      choixRole.addEventListener('change', function () {
        var modele = DROITS_PAR_ROLE[choixRole.value] || {};
        lignes.forEach(function (ligne) {
          var permises = modele[ligne.dataset.rubrique] || [];
          casesDe(ligne).forEach(function (c) {
            c.checked = permises.indexOf(c.dataset.action) !== -1;
          });
        });
        rafraichir();
      });
    }

    // L'oeil qui montre le mot de passe le temps de le relire.
    document.querySelectorAll('.oeil-secret').forEach(function (bouton) {
      bouton.addEventListener('click', function () {
        var champ = document.getElementById(bouton.dataset.voir);
        if (!champ) return;
        champ.type = champ.type === 'password' ? 'text' : 'password';
      });
    });

    rafraichir();
  }

  window.preparerDroits = lancer;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', lancer);
  } else {
    lancer();
  }
})();
