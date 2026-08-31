/* Confirmation avant une action irreversible.

   Le message vit dans des attributs data-* plutot que dans « onsubmit » :
   ecrit directement dans l'attribut, il se cassait des qu'il contenait une
   apostrophe ou un retour a la ligne, et le formulaire partait sans rien
   demander. Ici, aucune chaine n'est interpretee comme du code. */
(function () {
  'use strict';

  document.addEventListener('submit', function (evenement) {
    var formulaire = evenement.target;
    if (!formulaire || !formulaire.dataset) return;

    // Un bouton « formaction » envoie le formulaire vers une autre adresse :
    // c'est lui qui porte alors le message de confirmation.
    var source = evenement.submitter && evenement.submitter.dataset
                 && evenement.submitter.dataset.confirmer
                 ? evenement.submitter : formulaire;

    var message = source.dataset.confirmer;
    if (!message) return;

    var suite = source.dataset.confirmerSuite;
    if (suite) message += '\n' + suite;

    if (!window.confirm(message)) {
      evenement.preventDefault();
      evenement.stopPropagation();
    }
  }, true);
})();
