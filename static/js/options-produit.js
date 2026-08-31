/* Options et variantes d'un produit, sans quitter la page.

   Deux choses ici : les valeurs se saisissent en etiquettes (on tape, on
   appuie sur Entree), et le tableau des variantes se redessine des qu'une
   valeur change. Rien n'est envoye au serveur en chemin : tout part avec le
   bouton « Enregistrer » de la fiche, comme le reste du formulaire. */
(function () {
  'use strict';

  var zone = document.getElementById('zoneVariantes');
  var liste = document.getElementById('listeOptions');
  if (!zone || !liste) return;

  var dossier = zone.dataset.dossier || '';
  var prixProduit = zone.dataset.prixProduit || '';
  var coutProduit = zone.dataset.coutProduit || '';

  // Ce qui est deja enregistre : on le reprend au lieu de repartir a vide.
  var connues = {};
  var source = document.getElementById('donneesVariantes');
  try {
    JSON.parse((source && source.textContent) || '[]')
      .forEach(function (v) { connues[v.cle] = v; });
  } catch (e) { /* rien d'enregistre */ }

  // ----------------------------------------------------------- etiquettes
  function construireEtiquettes(boite) {
    if (boite.dataset.pret === '1') return;
    boite.dataset.pret = '1';

    var champCache = boite.querySelector('input[type="hidden"]');
    var saisie = document.createElement('input');
    saisie.type = 'text';
    saisie.className = 'saisie-etiquette';
    saisie.placeholder = 'Valeur puis Entree';

    function valeurs() {
      return (champCache.value || '').split(',')
        .map(function (v) { return v.trim(); })
        .filter(Boolean);
    }
    function ecrire(liste) {
      champCache.value = liste.join(', ');
      dessiner();
      redessinerVariantes();
    }
    function ajouter(texte) {
      var propres = texte.split(',').map(function (v) { return v.trim(); }).filter(Boolean);
      if (!propres.length) return;
      var actuelles = valeurs();
      propres.forEach(function (v) {
        if (actuelles.indexOf(v) === -1) actuelles.push(v);
      });
      ecrire(actuelles);
    }

    function dessiner() {
      boite.querySelectorAll('.etiquette').forEach(function (e) { e.remove(); });
      valeurs().forEach(function (v) {
        var puce = document.createElement('span');
        puce.className = 'etiquette';
        puce.textContent = v;
        var croix = document.createElement('button');
        croix.type = 'button';
        croix.className = 'retirer-etiquette';
        croix.setAttribute('aria-label', 'Retirer ' + v);
        croix.textContent = '×';
        croix.addEventListener('click', function () {
          ecrire(valeurs().filter(function (x) { return x !== v; }));
        });
        puce.appendChild(croix);
        boite.insertBefore(puce, saisie);
      });
    }

    saisie.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ',') {
        // Entree valide l'etiquette : elle ne doit pas envoyer le formulaire.
        e.preventDefault();
        ajouter(saisie.value);
        saisie.value = '';
      } else if (e.key === 'Backspace' && saisie.value === '') {
        var actuelles = valeurs();
        actuelles.pop();
        ecrire(actuelles);
      }
    });
    // Quitter le champ vaut validation : sinon la valeur tapee serait perdue.
    saisie.addEventListener('blur', function () {
      ajouter(saisie.value);
      saisie.value = '';
    });
    boite.addEventListener('click', function (e) {
      if (e.target === boite) saisie.focus();
    });

    boite.appendChild(saisie);
    dessiner();
  }

  // ------------------------------------------------------------ variantes
  function optionsSaisies() {
    var resultat = [];
    liste.querySelectorAll('.ligne-option').forEach(function (ligne) {
      var nom = (ligne.querySelector('[name="option_nom"]') || {}).value || '';
      var cache = ligne.querySelector('[name="option_valeurs"]');
      var vals = ((cache && cache.value) || '').split(',')
        .map(function (v) { return v.trim(); }).filter(Boolean);
      if (nom.trim() && vals.length) resultat.push(vals);
    });
    return resultat;
  }

  function combinaisons(groupes) {
    if (!groupes.length) return [];
    return groupes.reduce(function (acc, vals) {
      var suite = [];
      acc.forEach(function (debut) {
        vals.forEach(function (v) { suite.push(debut.concat([v])); });
      });
      return suite;
    }, [[]]);
  }

  function champ(nom, valeur, type, largeur) {
    var e = document.createElement('input');
    e.type = type || 'text';
    e.name = nom;
    e.value = valeur === undefined || valeur === null ? '' : valeur;
    if (type === 'number') e.step = '0.001';
    if (largeur) e.style.width = largeur;
    return e;
  }

  function redessinerVariantes() {
    // On garde ce qui est deja tape a l'ecran avant de tout reconstruire.
    zone.querySelectorAll('tr[data-cle]').forEach(function (tr) {
      var cle = tr.dataset.cle;
      connues[cle] = {
        cle: cle,
        reference: (tr.querySelector('[name="var_reference"]') || {}).value || '',
        prix: (tr.querySelector('[name="var_prix"]') || {}).value || '',
        prix_promo: (tr.querySelector('[name="var_prix_promo"]') || {}).value || '',
        cout: (tr.querySelector('[name="var_cout"]') || {}).value || '',
        stock: (tr.querySelector('[name="var_stock"]') || {}).value || 0,
        image: tr.dataset.image || '',
        defaut: (tr.querySelector('[name="var_defaut"]') || {}).checked || false
      };
    });

    var lignes = combinaisons(optionsSaisies());
    zone.innerHTML = '';
    if (!lignes.length) return;

    var titre = document.createElement('h4');
    titre.textContent = 'Variantes (' + lignes.length + ')';
    titre.style.marginTop = '24px';
    zone.appendChild(titre);

    var aide = document.createElement('p');
    aide.className = 'aide';
    aide.textContent = 'Un prix laisse vide reprend celui du produit. Le stock est propre '
                     + 'a chaque variante. Tout part avec le bouton Enregistrer de la fiche.';
    zone.appendChild(aide);

    var cadre = document.createElement('div');
    cadre.className = 'tableau-variantes';
    var table = document.createElement('table');
    table.className = 'table-admin';

    var entete = document.createElement('tr');
    ['Defaut', 'Variante', 'Reference', 'Prix barre', 'Prix de vente',
     "Prix d'achat", 'Stock', 'Photo'].forEach(function (texte) {
      var th = document.createElement('th');
      th.textContent = texte;
      entete.appendChild(th);
    });
    table.appendChild(entete);

    var unDefaut = false;
    lignes.forEach(function (valeurs, rang) {
      var cle = valeurs.join(' / ');
      var v = connues[cle] || {};
      var tr = document.createElement('tr');
      tr.dataset.cle = cle;
      tr.dataset.image = v.image || '';

      function cellule(contenu) {
        var td = document.createElement('td');
        if (contenu) td.appendChild(contenu);
        tr.appendChild(td);
        return td;
      }

      var radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'var_defaut';
      radio.value = cle;
      if (v.defaut) { radio.checked = true; unDefaut = true; }
      cellule(radio);

      var nom = document.createElement('strong');
      nom.textContent = cle;
      cellule(nom).appendChild(champ('var_cle', cle, 'hidden'));

      cellule(champ('var_reference', v.reference, 'text', '130px'));

      // « Prix barre » est le prix normal, « Prix de vente » le prix promotionnel
      // quand il y en a un : c'est ce dernier qui est facture au client.
      var cBarre = champ('var_prix', v.prix, 'number', '95px');
      cBarre.placeholder = prixProduit;
      cellule(cBarre);
      cellule(champ('var_prix_promo', v.prix_promo, 'number', '95px'));

      var cCout = champ('var_cout', v.cout, 'number', '95px');
      cCout.placeholder = coutProduit;
      cellule(cCout);
      cellule(champ('var_stock', v.stock, 'number', '75px'));

      var tdPhoto = cellule(null);
      if (v.image) {
        var vignette = document.createElement('img');
        vignette.src = dossier + v.image;
        vignette.className = 'mini-photo';
        vignette.alt = '';
        tdPhoto.appendChild(vignette);
      }
      var fichier = document.createElement('input');
      fichier.type = 'file';
      fichier.name = 'var_image';
      fichier.accept = 'image/*';
      fichier.style.width = '130px';
      tdPhoto.appendChild(fichier);

      if (rang === 0) tr.dataset.premiere = '1';
      table.appendChild(tr);
    });

    if (!unDefaut) {
      var premier = table.querySelector('tr[data-premiere] [name="var_defaut"]');
      if (premier) premier.checked = true;
    }

    cadre.appendChild(table);
    zone.appendChild(cadre);
  }

  // ------------------------------------------------------------- mise en route
  function preparer() {
    liste.querySelectorAll('[data-etiquettes]').forEach(construireEtiquettes);
  }

  liste.addEventListener('input', function (e) {
    if (e.target.name === 'option_nom') redessinerVariantes();
  });
  // Une option ajoutee ou retiree change la liste des combinaisons.
  new MutationObserver(function () {
    preparer();
    redessinerVariantes();
  }).observe(liste, { childList: true });

  preparer();
  redessinerVariantes();
})();
