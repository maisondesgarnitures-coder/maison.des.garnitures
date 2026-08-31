/* Mesure la barre du haut et publie ses hauteurs en variables CSS.
   Elles changent avec la langue, la largeur et le nombre de lignes de
   l'en-tete : les figer dans le CSS decalerait le panneau d'achat. */
(function () {
  'use strict';

  var barre = document.querySelector('.entete-collant');
  if (!barre) return;

  var bandeau = barre.querySelector('.bandeau-haut');
  var racine = document.documentElement;
  var memoire = '';

  function mesurer() {
    var total = Math.round(barre.getBoundingClientRect().height);
    var hautBandeau = bandeau ? Math.round(bandeau.getBoundingClientRect().height) : 0;

    // Sur telephone le bandeau defilant sort de l'ecran : la partie qui reste
    // collee, et donc la hauteur a compenser, se limite a l'en-tete.
    var colle = window.innerWidth <= 900 ? total - hautBandeau : total;

    var signature = total + '|' + hautBandeau + '|' + colle;
    if (signature === memoire) return;
    memoire = signature;

    racine.style.setProperty('--haut-bandeau', hautBandeau + 'px');
    racine.style.setProperty('--haut-entete', colle + 'px');
  }

  mesurer();
  window.addEventListener('resize', mesurer);
  window.addEventListener('orientationchange', mesurer);

  // Les polices arrivent apres le premier rendu et modifient la hauteur.
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(mesurer);
  if (window.ResizeObserver) new ResizeObserver(mesurer).observe(barre);
})();
