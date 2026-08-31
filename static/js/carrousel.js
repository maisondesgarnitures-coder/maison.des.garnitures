/* Carrousel des categories : defilement automatique, fleches, et arret des
   que le visiteur s'en occupe lui-meme. */
(function () {
  'use strict';

  var SANS_ANIMATION = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function initialiser(carrousel) {
    var piste = carrousel.querySelector('.piste-carrousel');
    var precedent = carrousel.querySelector('.fleche-carrousel.precedent');
    var suivant = carrousel.querySelector('.fleche-carrousel.suivant');
    if (!piste) return;

    // En arabe la lecture va de droite a gauche : le defilement doit suivre.
    var versLaDroite = getComputedStyle(carrousel).direction === 'rtl' ? -1 : 1;
    var intervalle = parseInt(carrousel.dataset.intervalle, 10) || 4500;
    var minuteur = null;
    var enPause = false;

    function pas() {
      var carte = piste.firstElementChild;
      if (!carte) return piste.clientWidth;
      var ecart = parseFloat(getComputedStyle(piste).columnGap || 0) || 0;
      return carte.getBoundingClientRect().width + ecart;
    }

    function debordement() {
      return piste.scrollWidth - piste.clientWidth;
    }

    // Position lue toujours dans le sens de lecture, quel que soit le navigateur.
    function position() {
      return Math.abs(piste.scrollLeft);
    }

    function auBout() {
      return position() >= debordement() - 2;
    }

    function auDebut() {
      return position() <= 2;
    }

    function aller(sens, boucler) {
      if (boucler && sens > 0 && auBout()) {
        piste.scrollTo({ left: 0, behavior: 'smooth' });
        return;
      }
      if (boucler && sens < 0 && auDebut()) {
        piste.scrollTo({ left: debordement() * versLaDroite, behavior: 'smooth' });
        return;
      }
      piste.scrollBy({ left: pas() * sens * versLaDroite, behavior: 'smooth' });
    }

    function majFleches() {
      var utile = debordement() > 4;
      carrousel.classList.toggle('sans-defilement', !utile);
      if (precedent) precedent.disabled = !utile || auDebut();
      if (suivant) suivant.disabled = !utile || auBout();
    }

    function demarrer() {
      if (SANS_ANIMATION || minuteur || debordement() <= 4) return;
      minuteur = setInterval(function () {
        // Onglet en arriere-plan : inutile de faire tourner le carrousel.
        if (enPause || document.hidden) return;
        aller(1, true);
      }, intervalle);
    }

    function arreter() {
      if (minuteur) { clearInterval(minuteur); minuteur = null; }
    }

    if (precedent) precedent.addEventListener('click', function () { aller(-1, true); });
    if (suivant) suivant.addEventListener('click', function () { aller(1, true); });

    // On ne bouge pas sous le curseur ni pendant une navigation au clavier.
    ['mouseenter', 'focusin', 'touchstart', 'pointerdown'].forEach(function (evt) {
      carrousel.addEventListener(evt, function () { enPause = true; }, { passive: true });
    });
    ['mouseleave', 'focusout'].forEach(function (evt) {
      carrousel.addEventListener(evt, function () { enPause = false; }, { passive: true });
    });

    piste.addEventListener('scroll', majFleches, { passive: true });
    window.addEventListener('resize', majFleches);

    majFleches();
    demarrer();
    window.addEventListener('pagehide', arreter);
  }

  function lancer() {
    document.querySelectorAll('[data-carrousel]').forEach(initialiser);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', lancer);
  } else {
    lancer();
  }
})();
