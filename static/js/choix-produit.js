/* Choix d'un produit avec sa photo, son identifiant et son prix.

   Un <select> natif n'affiche pas d'images, et parcourir 84 lignes sans
   recherche est penible : on construit donc notre propre liste filtrable.
   Le select d'origine reste le champ envoye au serveur. */
(function () {
  'use strict';

  function sansAccents(texte) {
    return (texte || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  function construire(select) {
    if (select.dataset.habille === '1') return;
    select.dataset.habille = '1';

    var boite = document.createElement('div');
    boite.className = 'choix-produit';

    var bouton = document.createElement('button');
    bouton.type = 'button';
    bouton.className = 'declencheur-produit';
    bouton.setAttribute('aria-haspopup', 'listbox');

    var panneau = document.createElement('div');
    panneau.className = 'panneau-produit';
    panneau.hidden = true;

    var recherche = document.createElement('input');
    recherche.type = 'text';
    recherche.className = 'recherche-produit';
    recherche.placeholder = 'Chercher par nom, reference ou ID...';

    var liste = document.createElement('div');
    liste.className = 'liste-produit';
    liste.setAttribute('role', 'listbox');

    function ligne(option) {
      var bloc = document.createElement('span');
      bloc.className = 'ligne-produit';

      var vignette = document.createElement('span');
      vignette.className = 'vignette-produit';
      if (option.dataset.photo) {
        var img = document.createElement('img');
        img.src = option.dataset.photo;
        img.alt = '';
        vignette.appendChild(img);
      } else {
        vignette.textContent = '—';
      }
      bloc.appendChild(vignette);

      var texte = document.createElement('span');
      texte.className = 'texte-produit';
      var titre = document.createElement('strong');
      titre.textContent = (option.textContent || '').trim();
      texte.appendChild(titre);

      if (option.value) {
        var detail = document.createElement('small');
        var morceaux = ['ID ' + option.value];
        if (option.dataset.ref) morceaux.push(option.dataset.ref);
        if (option.dataset.prix) morceaux.push(option.dataset.prix + ' TND');
        if (option.dataset.stock !== undefined) morceaux.push('stock ' + option.dataset.stock);
        detail.textContent = morceaux.join(' · ');
        texte.appendChild(detail);
      }
      bloc.appendChild(texte);
      return bloc;
    }

    function rafraichir() {
      var choisie = select.options[select.selectedIndex];
      bouton.innerHTML = '';
      bouton.appendChild(ligne(choisie));
    }

    var entrees = [];
    Array.prototype.forEach.call(select.options, function (option, index) {
      var element = document.createElement('button');
      element.type = 'button';
      element.className = 'option-produit';
      element.setAttribute('role', 'option');
      element.appendChild(ligne(option));
      // Texte servant au filtrage : accents et casse ignores.
      element.dataset.cherche = sansAccents(
        (option.textContent || '') + ' ' + (option.dataset.ref || '') + ' ' + option.value);
      element.addEventListener('click', function () {
        select.selectedIndex = index;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        rafraichir();
        fermer();
        bouton.focus();
      });
      liste.appendChild(element);
      entrees.push(element);
    });

    recherche.addEventListener('input', function () {
      var terme = sansAccents(recherche.value).trim();
      entrees.forEach(function (e) {
        e.hidden = terme !== '' && e.dataset.cherche.indexOf(terme) === -1;
      });
    });

    function ouvrir() {
      panneau.hidden = false;
      recherche.value = '';
      entrees.forEach(function (e) { e.hidden = false; });
      recherche.focus();
    }
    function fermer() { panneau.hidden = true; }

    bouton.addEventListener('click', function () {
      if (panneau.hidden) { ouvrir(); } else { fermer(); }
    });
    document.addEventListener('click', function (e) {
      if (!boite.contains(e.target)) fermer();
    });
    boite.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { fermer(); bouton.focus(); }
    });

    select.parentNode.insertBefore(boite, select);
    boite.appendChild(bouton);
    panneau.appendChild(recherche);
    panneau.appendChild(liste);
    boite.appendChild(panneau);
    boite.appendChild(select);
    select.classList.add('select-cache');
    rafraichir();
  }

  function lancer() {
    document.querySelectorAll('select[data-choix-produit]').forEach(construire);
  }
  window.habillerChoixProduit = lancer;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', lancer);
  } else {
    lancer();
  }
})();
