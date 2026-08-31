/* Edition d'une commande dans un panneau lateral.

   Le crayon de la liste ouvre le formulaire par-dessus le tableau plutot que
   de changer de page : on garde sa selection, ses filtres et sa position. Le
   formulaire arrive tel quel du serveur, on n'en duplique pas le balisage. */
(function () {
  'use strict';

  var panneau = document.getElementById('panneauEdition');
  var voile = document.getElementById('voilePanneau');
  if (!panneau || !voile) return;
  var corps = panneau.querySelector('.corps-panneau');
  var tete = panneau.querySelector('.tete-panneau');

  function ouvrir() {
    panneau.hidden = false;
    voile.hidden = false;
    // Le fond ne defile plus : c'est le panneau qui a le focus.
    document.body.classList.add('panneau-ouvert');
    // L'animation ne part qu'une fois l'element affiche.
    requestAnimationFrame(function () { panneau.classList.add('visible'); });
  }

  function fermer() {
    panneau.classList.remove('visible');
    voile.hidden = true;
    document.body.classList.remove('panneau-ouvert');
    panneau.hidden = true;
    corps.innerHTML = '';
    if (tete) tete.innerHTML = '';
  }

  function habiller() {
    // Les champs injectes n'ont pas vu le DOMContentLoaded : on rejoue leur
    // habillage. Chaque fonction ignore ce qu'elle a deja traite.
    if (typeof window.remplirGouvernorats === 'function') window.remplirGouvernorats(corps);
    if (typeof window.habillerStatuts === 'function') window.habillerStatuts();
    if (typeof window.habillerChoixProduit === 'function') window.habillerChoixProduit();
    if (typeof window.preparerDroits === 'function') window.preparerDroits();

    // La barre quitte la zone qui defile pour rester fixe en haut.
    var entete = corps.querySelector('.entete-panneau');
    if (entete && tete) tete.appendChild(entete);

    // « Enregistrer » de la barre du haut envoie le formulaire principal de la
    // page chargee, meme si son propre bouton est tout en bas.
    var bouton = panneau.querySelector('#enregistrerPanneau');
    var formulaire = corps.querySelector('form[data-formulaire-principal]');
    if (!bouton) return;
    if (!formulaire) { bouton.hidden = true; return; }
    bouton.addEventListener('click', function () {
      // requestSubmit declenche la validation du navigateur et l'evenement
      // « submit » : la demande de confirmation reste donc active.
      if (typeof formulaire.requestSubmit === 'function') { formulaire.requestSubmit(); }
      else { formulaire.submit(); }
    });
  }

  function charger(adresse) {
    corps.innerHTML = '<p class="attente-panneau">Chargement...</p>';
    ouvrir();
    fetch(adresse + (adresse.indexOf('?') === -1 ? '?' : '&') + 'panneau=1',
          { credentials: 'same-origin' })
      .then(function (reponse) {
        if (!reponse.ok) throw new Error(reponse.status);
        return reponse.text();
      })
      .then(function (html) {
        corps.innerHTML = html;
        // Un formulaire sans « action » part vers l'adresse de la page
        // affichee, c'est-a-dire la liste : l'enregistrement echouerait avec
        // une erreur de methode. On lui donne l'adresse qu'il vient d'ouvrir.
        corps.querySelectorAll('form:not([action])').forEach(function (f) {
          f.setAttribute('action', adresse);
        });
        // Les <script> arrives par innerHTML ne s'executent pas : on les
        // rejoue, sinon GOUVERNORATS et les valeurs actuelles manquent.
        corps.querySelectorAll('script').forEach(function (ancien) {
          var neuf = document.createElement('script');
          if (ancien.src) { neuf.src = ancien.src; } else { neuf.textContent = ancien.textContent; }
          document.head.appendChild(neuf);
          document.head.removeChild(neuf);
        });
        habiller();
        corps.scrollTop = 0;
      })
      .catch(function () {
        // En cas d'echec, on retombe sur la page complete plutot que de
        // laisser l'utilisateur devant un panneau vide.
        window.location.href = adresse;
      });
  }

  document.addEventListener('click', function (evenement) {
    var lien = evenement.target.closest ? evenement.target.closest('a[data-ouvre-panneau]') : null;
    if (lien) {
      // Ctrl/Cmd-clic et clic du milieu gardent leur sens : ouvrir un onglet.
      if (evenement.metaKey || evenement.ctrlKey || evenement.shiftKey || evenement.button !== 0) return;
      evenement.preventDefault();
      // On marque la ligne ouverte : en refermant le panneau, meme sans
      // avoir rien change, on retrouve ou on en etait.
      var ligne = lien.closest ? lien.closest('tr[data-id]') : null;
      if (ligne) {
        Array.prototype.forEach.call(
          document.querySelectorAll('tr.ligne-consultee'),
          function (autre) { autre.classList.remove('ligne-consultee'); });
        ligne.classList.add('ligne-consultee');
      }
      charger(lien.getAttribute('href'));
      return;
    }
    if (evenement.target.closest && evenement.target.closest('.fermer-panneau')) {
      evenement.preventDefault();
      fermer();
    }
  });

  voile.addEventListener('click', fermer);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !panneau.hidden) fermer();
  });
})();
