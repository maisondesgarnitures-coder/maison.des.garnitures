/* Remplace un <select> par une liste a pastilles colorees.

   Un <select> natif n'affiche pas de couleur de facon fiable d'un navigateur
   a l'autre. On construit donc notre propre liste, tout en gardant le select
   d'origine : sans JavaScript, le formulaire reste utilisable tel quel. */
(function () {
  'use strict';

  function libelle(option) {
    return (option.textContent || '').trim();
  }

  function construire(select) {
    if (select.dataset.habille === '1') return;
    select.dataset.habille = '1';

    var boite = document.createElement('div');
    boite.className = 'select-statut';

    var bouton = document.createElement('button');
    bouton.type = 'button';
    bouton.className = 'declencheur-statut';
    bouton.setAttribute('aria-haspopup', 'listbox');
    bouton.setAttribute('aria-expanded', 'false');

    var liste = document.createElement('div');
    liste.className = 'liste-statut';
    liste.setAttribute('role', 'listbox');
    liste.hidden = true;

    var avecLogo = select.hasAttribute('data-avec-logo');

    function pastille(option) {
      if (!avecLogo) {
        var p = document.createElement('span');
        p.className = 'badge-statut statut-' + option.value;
        p.textContent = libelle(option);
        return p;
      }
      // Transporteur : logo televerse, sinon pastille aux initiales.
      var bloc = document.createElement('span');
      bloc.className = 'choix-livreur';
      if (option.dataset.logo) {
        var img = document.createElement('img');
        img.src = option.dataset.logo;
        img.alt = '';
        img.className = 'logo-transporteur';
        bloc.appendChild(img);
      } else if (option.value) {
        var init = document.createElement('span');
        init.className = 'pastille-livreur';
        init.style.background = option.dataset.couleur || '#5C6573';
        init.textContent = option.dataset.initiales || '?';
        bloc.appendChild(init);
      }
      var texte = document.createElement('span');
      texte.textContent = libelle(option);
      bloc.appendChild(texte);
      return bloc;
    }

    function rafraichir() {
      var choisie = select.options[select.selectedIndex];
      bouton.innerHTML = '';
      if (choisie) bouton.appendChild(pastille(choisie));
      var fleche = document.createElement('span');
      fleche.className = 'fleche-statut';
      fleche.setAttribute('aria-hidden', 'true');
      fleche.textContent = '\u25BE';
      bouton.appendChild(fleche);
    }

    Array.prototype.forEach.call(select.options, function (option, index) {
      var element = document.createElement('button');
      element.type = 'button';
      element.className = 'option-statut';
      element.setAttribute('role', 'option');
      element.appendChild(pastille(option));
      element.addEventListener('click', function () {
        select.selectedIndex = index;
        // On previent le reste de la page, comme le ferait un vrai changement.
        select.dispatchEvent(new Event('change', { bubbles: true }));
        rafraichir();
        fermer();
        bouton.focus();
      });
      liste.appendChild(element);
    });

    function ouvrir() {
      liste.hidden = false;
      bouton.setAttribute('aria-expanded', 'true');
    }
    function fermer() {
      liste.hidden = true;
      bouton.setAttribute('aria-expanded', 'false');
    }

    bouton.addEventListener('click', function () {
      liste.hidden ? ouvrir() : fermer();
    });
    document.addEventListener('click', function (e) {
      if (!boite.contains(e.target)) fermer();
    });
    boite.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { fermer(); bouton.focus(); }
    });

    select.parentNode.insertBefore(boite, select);
    boite.appendChild(bouton);
    boite.appendChild(liste);
    // Le select reste dans le formulaire : c'est lui qui est envoye.
    boite.appendChild(select);
    select.classList.add('select-cache');
    rafraichir();
  }

  function lancer() {
    document.querySelectorAll('select[data-statut-colore], select[data-avec-logo]')
      .forEach(construire);
  }
  // Le panneau lateral injecte de nouveaux champs : il rejoue cet habillage.
  window.habillerStatuts = lancer;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', lancer);
  } else {
    lancer();
  }
})();
