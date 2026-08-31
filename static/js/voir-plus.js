/*
 * Bouton « voir plus » : charge la page suivante et l'ajoute a la grille,
 * sans recharger la page ni perdre la position de lecture.
 *
 * Le bouton reste un vrai lien : sans JavaScript, il mene simplement a la
 * page suivante.
 */
(function () {
  var bouton = document.getElementById('boutonVoirPlus');
  var grille = document.getElementById('grilleProduits');
  if (!bouton || !grille) return;

  var enCours = false;

  bouton.addEventListener('click', function (e) {
    e.preventDefault();
    if (enCours) return;
    enCours = true;

    var libelle = bouton.innerHTML;
    bouton.textContent = (typeof TXT_CHARGEMENT !== 'undefined') ? TXT_CHARGEMENT : '...';
    bouton.classList.add('occupe');

    var url = new URL(bouton.href, window.location.origin);
    url.searchParams.set('fragment', '1');

    fetch(url.toString())
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      })
      .then(function (html) {
        var provisoire = document.createElement('div');
        provisoire.innerHTML = html;

        var ajoutes = provisoire.querySelectorAll('.carte-produit');
        ajoutes.forEach(function (carte) { grille.appendChild(carte); });

        var page = parseInt(bouton.dataset.page, 10) + 1;
        bouton.dataset.page = page;
        url.searchParams.set('page', page);
        url.searchParams.delete('fragment');
        bouton.href = url.pathname + '?' + url.searchParams.toString();

        // Plus rien a charger : le bouton disparait.
        if (!ajoutes.length) {
          bouton.parentElement.remove();
          return;
        }
        bouton.innerHTML = libelle;
        var reste = bouton.querySelector('.reste-produits');
        if (reste) {
          var restant = parseInt(reste.textContent.replace(/\D/g, ''), 10) - ajoutes.length;
          if (restant > 0) {
            reste.textContent = '(' + restant + ')';
          } else {
            bouton.parentElement.remove();
          }
        }
      })
      .catch(function () {
        // En cas d'echec, on rend au bouton son role de lien classique.
        bouton.innerHTML = libelle;
        window.location.href = bouton.href;
      })
      .finally(function () {
        bouton.classList.remove('occupe');
        enCours = false;
      });
  });
})();
