# -*- coding: utf-8 -*-
"""
Traductions de l'interface boutique (francais / arabe).

Seuls les textes de l'interface sont traduits ici. Les noms et descriptions
des produits viennent du catalogue : beaucoup sont deja rediges dans les deux
langues dans la meme fiche.
"""

LANGUES = {
    "fr": {"nom": "Francais", "etiquette": "FR", "direction": "ltr"},
    "ar": {"nom": "العربية", "etiquette": "ع", "direction": "rtl"},
}

LANGUE_DEFAUT = "fr"

TEXTES = {
    # --- En-tete et pied de page ---
    "rechercher_produit": ("Rechercher un produit...", "ابحث عن منتج..."),
    "rechercher": ("Rechercher", "بحث"),
    "panier": ("Panier", "السلة"),
    "contact": ("Contact", "اتصل بنا"),
    "telephone_court": ("Tel", "الهاتف"),
    "suivi": ("Suivi", "التتبع"),
    "suivre_commande": ("Suivre ma commande", "تتبع طلبيتي"),
    "accroche_logo": (u"Quincaillerie & outillage bois", u"خردوات ومعدات الخشب"),
    "tous_droits": (u"Tous droits réservés", u"جميع الحقوق محفوظة"),
    "hero_etiquette": (u"Livraison 24-48 h partout en Tunisie", u"توصيل خلال 24-48 ساعة في كامل تونس"),
    "hero_titre_1": (u"Tout pour vos meubles,", u"كل ما يلزم أثاثك،"),
    "hero_titre_2": (u"au juste prix", u"بأفضل سعر"),
    "hero_accroche": (u"Charnières, coulisses, machines et outillage professionnel. Vous commandez, vous payez à la réception — sans avance.",
                      u"مفصلات، سكك، آلات ومعدات احترافية. تطلب وتدفع عند الاستلام — دون تسبقة."),
    "voir_catalogue_court": (u"Voir le catalogue", u"تصفّح المنتجات"),
    "commander_whatsapp": (u"Commander sur WhatsApp", u"اطلب عبر واتساب"),
    "chiffre_references": (u"références en stock", u"مرجع متوفر"),
    "chiffre_categories": (u"catégories", u"أصناف"),
    "avance_montant": (u"0 TND", u"0 د.ت"),
    "avance_libelle": (u"D'AVANCE", u"بدون تسبقة"),
    "chiffre_avance": (u"d'avance à payer", u"تسبقة"),
    "atout_livraison_t": (u"Livraison 24-48 h", u"توصيل 24-48 ساعة"),
    "atout_livraison_d": (u"Partout en Tunisie", u"في كامل تونس"),
    "atout_cod_t": (u"Paiement à la livraison", u"الدفع عند الاستلام"),
    "atout_cod_d": (u"Vous payez au livreur", u"تدفع لعامل التوصيل"),
    "atout_pro_t": (u"Matériel professionnel", u"معدات احترافية"),
    "atout_pro_d": (u"CMT, Bosch et grandes marques", u"CMT، Bosch وعلامات كبرى"),
    "atout_conseil_t": (u"Conseil au téléphone", u"نصائح عبر الهاتف"),
    "atout_conseil_d": (u"Un doute ? Appelez-nous", u"عندك سؤال؟ اتصل بنا"),
    "precedent": (u"Précédent", u"السابق"),
    "suivant": (u"Suivant", u"التالي"),
    "sous_titre_categories": (u"Trouvez votre rayon en un clic", u"اعثر على قسمك بنقرة واحدة"),
    "sous_titre_vedettes": (u"Nos best-sellers du moment", u"الأكثر مبيعا حاليا"),
    "sous_titre_nouveautes": (u"Les derniers articles arrivés", u"آخر المنتجات الواردة"),
    "sous_titre_tous": (u"Un aperçu de tout notre stock", u"لمحة عن كامل مخزوننا"),
    "tout_voir": (u"Tout voir", u"عرض الكل"),
    "produits_court": (u"produits", u"منتوج"),
    # Accord apres le nombre : « 1 produit » / « 6 produits », idem en arabe.
    "article_un": (u"produit", u"منتج"),
    "article_plusieurs": (u"produits", u"منتجات"),
    "pages": ("Pages", "الصفحات"),
    "contactez_nous": ("Contactez-nous", "تواصل معنا"),
    "suivez_nous": ("Suivez-nous", "تابعنا"),
    "email": ("E-mail", "البريد الإلكتروني"),
    "derniere_maj": ("Dernière mise à jour :", "آخر تحديث:"),
    "slogan_pied": ("Quincaillerie, garnitures et accessoires pour meubles.",
                    "خردوات ولوازم وإكسسوارات الأثاث."),

    # --- Accueil ---
    "titre_accueil": ("Toutes vos garnitures et quincailleries au meilleur prix",
                      "كل لوازم وخردوات الأثاث بأفضل الأسعار"),
    "livraison_cod": ("Livraison partout en Tunisie — Paiement à la livraison",
                      "التوصيل لكامل تراب الجمهورية - الدفع عند الاستلام"),
    "voir_produits": ("Voir les produits", "تصفح المنتجات"),
    "nos_categories": ("Nos catégories", "أقسامنا"),
    "produits_vedettes": ("Produits vedettes", "منتجات مميزة"),
    "nouveautes": ("Nouveautés", "أحدث المنتجات"),

    # --- Carte produit et fiche produit ---
    "promo": ("PROMO", "تخفيض"),
    "nouveau": ("NOUVEAU", "جديد"),
    "ajouter_panier": ("Ajouter au panier", "أضف إلى السلة"),
    "photo_produit": ("Photo produit", "صورة المنتج"),
    "reference": ("Référence", "المرجع"),
    "en_stock": ("En stock", "متوفر"),
    "disponibles": ("disponibles", "قطعة متوفرة"),
    "rupture_stock": ("Rupture de stock", "نفدت الكمية"),
    "couleur": ("Couleur", "اللون"),
    "dimensions": ("Dimensions", "المقاسات"),
    "produits_similaires": ("Produits similaires", "منتجات مشابهة"),
    "quantite": ("Quantité", "الكمية"),

    "voir_photo": ("Voir la photo", "عرض الصورة"),
    "indisponible": ("Produit indisponible", "المنتج غير متوفر"),
    "choisir_option": ("Merci de choisir une option avant d'ajouter au panier.",
                       "يرجى اختيار خيار قبل الإضافة إلى السلة."),
    "choisir_offre": ("Choisissez votre offre", "اختر عرضك"),
    "acheter_maintenant": ("Acheter maintenant", "شراء"),
    "vos_coordonnees": ("Vos coordonnées", "معلوماتك"),
    "livraison_gratuite_a": ("Ajoutez {montant} TND pour la livraison gratuite",
                             "أضف {montant} د.ت للحصول على توصيل مجاني"),
    "livraison_gratuite_atteinte": ("Livraison gratuite obtenue", "تحصلت على التوصيل المجاني"),
    "remise": ("remise", "تخفيض"),
    "caracteristiques": ("Caractéristiques et détails", "المواصفات والتفاصيل"),
    "achat_rapide_note": ("Remplissez ce formulaire et validez : pas de compte à créer, vous payez à la réception.",
                          "املأ هذا النموذج وأكّد: لا حاجة لإنشاء حساب، تدفع عند الاستلام."),
    "economisez": ("Économisez", "وفّر"),
    "prix_degressif": ("Plus vous en prenez, moins c'est cher",
                       "كلما زادت الكمية، انخفض السعر"),
    "et_plus": ("et plus", "فما فوق"),
    "prix_palier_actif": ("Prix appliqué : {prix} TND l'unité",
                          "السعر المطبق: {prix} د.ت للوحدة"),
    "le_plus_choisi": ("Le plus choisi", "الأكثر طلباً"),
    "epuise": ("Épuisé", "نفد"),
    "precommande": ("Sur commande", "بالطلب"),
    "precommande_detail": ("Ce produit n'est pas en stock mais reste commandable : nous vous indiquerons le délai par téléphone.",
                           "هذا المنتج غير متوفر حالياً لكن يمكنك طلبه: سنعلمك بالمدة عبر الهاتف."),
    "prevenir_dispo": ("Ce produit sera de nouveau disponible prochainement.",
                       "سيتوفر هذا المنتج من جديد قريباً."),

    # --- Panier ---
    "mon_panier": ("Mon panier", "سلتي"),
    "maj": ("Maj", "تحديث"),
    "supprimer": ("Suppr.", "حذف"),
    "code_applique": ("Code appliqué", "تم تطبيق الكود"),
    "retirer_code": ("Retirer le code", "إزالة الكود"),
    "avez_code_promo": ("Vous avez un code promo ?", "هل لديك كود تخفيض؟"),
    "appliquer": ("Appliquer", "تطبيق"),
    "sous_total": ("Sous-total", "المجموع الفرعي"),
    "reduction": ("Réduction", "التخفيض"),
    "total": ("Total", "المجموع"),
    "passer_commande": ("Passer la commande", "إتمام الطلب"),
    "panier_vide": ("Votre panier est vide.", "سلتك فارغة."),

    # --- Suggestions / upsell ---
    "completez_commande": ("Complétez votre commande", "أكمل طلبيتك"),
    "souvent_achete": ("Souvent acheté avec vos articles", "غالباً ما يُشترى مع منتجاتك"),
    "ajouter": ("Ajouter", "أضف"),
    "ajoute": ("Ajouté", "تمت الإضافة"),

    # --- Avis produits ---
    "avis": ("Avis clients", "آراء الحرفاء"),
    "aucun_avis": ("Aucun avis pour le moment. Soyez le premier !",
                   "لا توجد آراء حالياً. كن أول من يشارك رأيه!"),
    "laisser_avis": ("Laisser un avis", "أضف رأيك"),
    "votre_note": ("Votre note", "تقييمك"),
    "votre_nom": ("Votre nom", "اسمك"),
    "telephone_facultatif": ("Téléphone (facultatif, pour vérifier votre achat)",
                             "رقم الهاتف (اختياري، للتثبت من شرائك)"),
    "votre_commentaire": ("Votre commentaire", "تعليقك"),
    "envoyer_avis": ("Envoyer mon avis", "إرسال رأيي"),
    "achat_verifie": ("Achat vérifié", "شراء موثق"),
    "avis_merci": ("Merci ! Votre avis sera publié après vérification.",
                   "شكراً! سيتم نشر رأيك بعد المراجعة."),
    "avis_incomplet": ("Merci d'indiquer votre nom et une note entre 1 et 5 étoiles.",
                       "يرجى إدخال اسمك وتقييم بين 1 و5 نجوم."),
    "sur_5": ("sur 5", "من 5"),
    "un_avis": ("avis", "رأي"),
    "des_avis": ("avis", "آراء"),

    # --- Categorie et recherche ---
    "categorie_vide": ("Aucun produit dans cette catégorie pour le moment.",
                       "لا توجد منتجات في هذا القسم حالياً."),
    "resultats_pour": ("Résultats pour", "نتائج البحث عن"),
    "aucun_resultat": ("Aucun produit trouvé.", "لم يتم العثور على أي منتج."),
    "voir_produit": (u"Voir le produit", u"عرض المنتج"),
    "voir_video": (u"Voir la vidéo de démonstration", u"شاهد فيديو الاستعمال"),
    "video_demo": (u"Vidéo de démonstration", u"فيديو الاستعمال"),
    "voir_plus": ("Voir plus de produits", "عرض المزيد"),
    "tous_produits": ("Tous nos produits", "كل منتجاتنا"),
    "voir_catalogue": ("Voir les {n} produits", "عرض كل المنتجات ({n})"),
    "produit_trouve": ("produit", "منتج"),
    "produits_trouves": ("produits", "منتج"),
    "trier_par": ("Trier par", "ترتيب حسب"),
    "tri_defaut": ("Nos suggestions", "اقتراحاتنا"),
    "tri_recent": ("Nouveautés", "الأحدث"),
    "tri_prix_bas": ("Prix croissant", "السعر تصاعدياً"),
    "tri_prix_haut": ("Prix décroissant", "السعر تنازلياً"),
    "tri_promo": ("Promotions d'abord", "التخفيضات أولاً"),
    "chargement": ("Chargement...", "جاري التحميل..."),

    # --- Commande ---
    "finaliser_commande": ("Finaliser ma commande", "إتمام الطلبية"),
    "nom_complet": ("Nom complet", "الاسم الكامل"),
    "telephone": ("Téléphone", "رقم الهاتف"),
    "gouvernorat": ("Gouvernorat", "الولاية"),
    "ville_delegation": ("Ville / Délégation", "المدينة / المعتمدية"),
    "choisir_gouvernorat": ("-- Choisir un gouvernorat --", "-- اختر الولاية --"),
    "choisir_ville": ("-- Choisir d'abord un gouvernorat --", "-- اختر الولاية أولاً --"),
    "adresse_complete": ("Adresse complète", "العنوان الكامل"),
    "adresse_exemple": ("Rue, numéro, immeuble...", "الشارع، الرقم، العمارة..."),
    "commentaire_optionnel": ("Commentaire (optionnel)", "ملاحظة (اختياري)"),
    "frais_livraison": ("Frais de livraison", "معاليم التوصيل"),
    "total_a_payer": ("Total à payer à la livraison", "المبلغ الجملي عند الاستلام"),
    "confirmer_commande": ("Confirmer ma commande", "تأكيد الطلبية"),
    "livraison_offerte": ("Livraison offerte", "التوصيل مجاني"),

    # --- Confirmation ---
    "commande_recue_titre": (u"Merci {nom}, votre commande est enregistrée", u"شكرا {nom}، تم تسجيل طلبك"),
    "detail_commande": (u"Détail de la commande", u"تفاصيل الطلب"),
    "un_article": (u"1 article", u"منتج واحد"),
    "n_articles": (u"{n} articles", u"{n} منتجات"),
    "suivi_livraison": (u"Suivi de la livraison", u"تتبع التوصيل"),
    "etape_recue": (u"Commande reçue", u"تم استلام الطلب"),
    "etape_recue_note": (u"Nous vous appelons pour confirmer.", u"سنتصل بك للتأكيد."),
    "etape_preparation": (u"Préparation du colis", u"تجهيز الطرد"),
    "etape_preparation_note": (u"Votre colis est en cours de préparation.", u"يتم تجهيز طردك."),
    "etape_route": (u"En route", u"في الطريق"),
    "etape_route_note": (u"Le livreur vous contactera avant de passer.", u"سيتصل بك عامل التوصيل قبل مروره."),
    "etape_livree": (u"Livrée", u"تم التسليم"),
    "etape_livree_note": (u"Merci pour votre confiance.", u"شكرا على ثقتك."),
    "infos_livraison": (u"Informations de livraison", u"معلومات التوصيل"),
    "infos_livraison_note": (u"Vérifiez que tout est correct.", u"تأكد من صحة المعلومات"),
    "continuer_achats": (u"Continuer mes achats", u"متابعة التسوق"),
    "une_question": (u"Une question ? Écrivez-nous à", u"لديك سؤال؟ راسلنا على"),
    "ou": (u"ou", u"أو"),
    "a_payer_livreur": (u"À payer au livreur", u"يُدفع لعامل التوصيل"),
    "merci": ("Merci", "شكراً"),
    "commande_enregistree": ("Votre commande {numero} a bien été enregistrée.",
                             "تم تسجيل طلبيتك {numero} بنجاح."),
    "paiement_livraison": ("paiement à la livraison", "الدفع عند الاستلام"),
    "nous_contacterons": ("Nous vous contacterons au {telephone} pour confirmer votre commande.",
                          "سنتصل بك على الرقم {telephone} لتأكيد طلبيتك."),
    "retour_boutique": ("Retour à la boutique", "العودة إلى المتجر"),

    # --- Suivi ---
    "numero_commande": ("Numéro de commande", "رقم الطلبية"),
    "telephone_commande": ("Téléphone utilisé lors de la commande", "رقم الهاتف المستعمل في الطلبية"),
    "verifier": ("Vérifier", "تحقق"),
    "commande": ("Commande", "الطلبية"),
    "statut": ("Statut", "الحالة"),
    "numero_suivi_transporteur": ("Numéro de suivi transporteur", "رقم التتبع لدى شركة التوصيل"),
    "commande_introuvable": ("Commande introuvable.", "لم يتم العثور على الطلبية."),

    # --- Statuts de commande, vus par le client ---
    "statut_nouvelle": ("Nouvelle", "جديدة"),
    "statut_a_confirmer": ("À confirmer", "في انتظار التأكيد"),
    "statut_confirmee": ("Confirmée", "مؤكدة"),
    "statut_preparation": ("En préparation", "قيد التحضير"),
    "statut_expediee": ("Expédiée", "تم الإرسال"),
    "statut_livree": ("Livrée", "تم التسليم"),
    "statut_annulee": ("Annulée", "ملغاة"),
    "statut_retour": ("Retour", "مرتجعة"),
    "statut_injoignable": ("Client injoignable", "تعذر الاتصال بالحريف"),

    # --- Messages du serveur ---
    "code_invalide": ("Code promo invalide.", "كود التخفيض غير صالح."),
    "code_applique_ok": ("Code {code} appliqué.", "تم تطبيق الكود {code}."),
    "nom_requis": ("Merci d'indiquer ton nom complet.", "يرجى إدخال اسمك الكامل."),
    "telephone_invalide": ("Numéro de téléphone invalide : 8 chiffres attendus (ex : 20 123 456).",
                           "رقم الهاتف غير صحيح: المطلوب 8 أرقام (مثال: 456 123 20)."),
    "stock_insuffisant": ("Stock insuffisant pour {produit} : il en reste {stock}.",
                          "الكمية غير كافية لـ {produit}: يتبقى {stock} فقط."),
}


def traduire(cle, langue=LANGUE_DEFAUT, **variables):
    """Retourne le texte traduit. Si la cle est inconnue, on la renvoie telle
    quelle plutot que de casser la page."""
    paire = TEXTES.get(cle)
    if not paire:
        return cle
    index = 1 if langue == "ar" else 0
    texte = paire[index] or paire[0]
    for nom, valeur in variables.items():
        texte = texte.replace("{%s}" % nom, str(valeur))
    return texte
