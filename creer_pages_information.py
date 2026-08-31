# -*- coding: utf-8 -*-
"""
Cree les pages d'information de la boutique, en francais et en arabe.

Textes rediges pour Maison des Garnitures et le contexte tunisien
(paiement a la livraison, transporteurs locaux). A relire et adapter :
ce sont des documents qui engagent la boutique.

    python creer_pages_information.py
"""

import app as boutique

PAGES = [
    {
        "slug": "a-propos",
        "ordre": 1,
        "titre_fr": "À propos",
        "titre_ar": "من نحن",
        "contenu_fr": """
<p><strong>Maison des Garnitures</strong> est un spécialiste tunisien de la quincaillerie
d'ameublement et de l'outillage pour le travail du bois.</p>

<p>Nous fournissons les menuisiers, les ateliers et les particuliers en charnières,
coulisses, gabarits de perçage, fraises, disques de scie et machines. Nous travaillons
avec des marques reconnues comme CMT Orange Tools, Bosch et Femi, ainsi qu'avec des
fabricants locaux pour les consommables du quotidien.</p>

<h3>Notre façon de travailler</h3>
<ul>
  <li><strong>Des produits que nous connaissons.</strong> Nous vendons ce que nous utilisons
      et ce que nos clients professionnels nous redemandent.</li>
  <li><strong>Des prix dégressifs.</strong> Sur les consommables, le prix baisse à la quantité :
      les ateliers ne paient pas le tarif du particulier.</li>
  <li><strong>Le paiement à la livraison.</strong> Vous ne payez qu'au moment où vous recevez
      votre commande, partout en Tunisie.</li>
  <li><strong>Un conseil avant l'achat.</strong> Un doute sur un diamètre, une compatibilité,
      une épaisseur de panneau ? Écrivez-nous sur WhatsApp avant de commander.</li>
</ul>

<p>Pour toute question sur un produit ou une commande, nos coordonnées sont en bas de page.</p>
""",
        "contenu_ar": """
<p><strong>Maison des Garnitures</strong> مختصة في خردوات الأثاث ومعدات النجارة في تونس.</p>

<p>نوفّر للنجارين والورشات والأفراد مفصلات، مجاري أدراج، قوالب حفر، رؤوس قطع، أقراص
منشار وآلات. نتعامل مع علامات معروفة مثل CMT Orange Tools وBosch وFemi، إضافة إلى
مزوّدين محليين للمواد الاستهلاكية.</p>

<h3>طريقة عملنا</h3>
<ul>
  <li><strong>منتجات نعرفها جيداً.</strong> نبيع ما نستعمله وما يطلبه حرفاؤنا المحترفون.</li>
  <li><strong>أسعار تنخفض مع الكمية.</strong> الورشات لا تدفع سعر الأفراد.</li>
  <li><strong>الدفع عند الاستلام.</strong> لا تدفع إلا عند استلام طلبيتك، في كامل تراب الجمهورية.</li>
  <li><strong>نصيحة قبل الشراء.</strong> عندك شك في قطر أو توافق أو سماكة لوح؟ راسلنا على واتساب قبل الطلب.</li>
</ul>
""",
    },
    {
        "slug": "conditions-generales",
        "ordre": 2,
        "titre_fr": "Conditions générales de vente",
        "titre_ar": "الشروط والأحكام",
        "contenu_fr": """
<p>Les présentes conditions régissent les ventes réalisées sur ce site. Passer une commande
vaut acceptation de ces conditions.</p>

<h3>1. Produits et prix</h3>
<p>Les prix sont indiqués en dinars tunisiens, toutes taxes comprises. Les frais de livraison
sont affichés avant la validation de la commande. Certains produits bénéficient de prix
dégressifs selon la quantité : la grille est affichée sur la fiche du produit.</p>
<p>Nous nous efforçons de décrire nos produits avec exactitude. En cas d'erreur manifeste
de prix ou de description, nous vous contactons avant de préparer la commande.</p>

<h3>2. Commande</h3>
<p>La commande est enregistrée dès validation du formulaire. Elle n'est <strong>confirmée
qu'après un appel téléphonique</strong> de notre part. Sans réponse de votre part après
plusieurs tentatives, la commande est annulée et le stock remis en vente.</p>

<h3>3. Paiement</h3>
<p>Le paiement se fait <strong>en espèces, à la livraison</strong>, directement au livreur.
Aucun paiement n'est demandé au moment de la commande.</p>

<h3>4. Livraison</h3>
<p>Nous livrons dans les 24 gouvernorats via nos transporteurs partenaires. Les délais
habituels sont de 2 à 5 jours ouvrables selon la région. Ces délais sont indicatifs et
peuvent varier selon la disponibilité du produit et la charge du transporteur.</p>
<p>Il vous appartient de fournir une adresse et un numéro de téléphone exacts. Les frais
d'une seconde présentation, causée par une adresse erronée ou une absence répétée,
peuvent vous être facturés.</p>

<h3>5. Vérification à la réception</h3>
<p>Vérifiez l'état du colis devant le livreur. En cas de dommage visible, refusez la
livraison et prévenez-nous le jour même.</p>

<h3>6. Garantie</h3>
<p>Les machines et l'outillage électroportatif bénéficient de la garantie du fabricant.
Conservez votre facture : elle en est la preuve. La garantie ne couvre pas l'usure normale,
les consommables, ni les dommages dus à un usage non conforme.</p>

<h3>7. Responsabilité</h3>
<p>Nos produits sont destinés à un usage professionnel ou averti. Respectez les consignes
de sécurité du fabricant et portez les équipements de protection adaptés. Notre
responsabilité ne saurait être engagée en cas d'usage non conforme.</p>

<h3>8. Droit applicable</h3>
<p>Ces conditions sont soumises au droit tunisien. En cas de litige, nous privilégions
une solution amiable avant toute action.</p>
""",
        "contenu_ar": """
<p>تحكم هذه الشروط عمليات البيع عبر هذا الموقع. إتمام الطلب يعني قبول هذه الشروط.</p>

<h3>1. المنتجات والأسعار</h3>
<p>الأسعار بالدينار التونسي وتشمل جميع الأداءات. تُعرض معاليم التوصيل قبل تأكيد الطلب.
بعض المنتجات لها أسعار تنخفض مع الكمية، والجدول معروض في صفحة المنتج.</p>

<h3>2. الطلب</h3>
<p>يُسجّل الطلب فور إرسال النموذج، ولا يُعتبر <strong>مؤكداً إلا بعد اتصال هاتفي</strong> من
طرفنا. في حال تعذّر الاتصال بعد عدة محاولات، يُلغى الطلب وتعود الكمية إلى البيع.</p>

<h3>3. الدفع</h3>
<p>الدفع <strong>نقداً عند الاستلام</strong>، مباشرة لدى عامل التوصيل. لا يُطلب أي دفع عند الطلب.</p>

<h3>4. التوصيل</h3>
<p>نوصّل إلى 24 ولاية عبر شركات التوصيل الشريكة. الآجال المعتادة من 2 إلى 5 أيام عمل حسب
الجهة، وهي آجال تقريبية.</p>
<p>يجب تقديم عنوان ورقم هاتف صحيحين. قد تُحتسب معاليم إضافية في حال إعادة التوصيل بسبب
عنوان خاطئ أو غياب متكرر.</p>

<h3>5. التثبّت عند الاستلام</h3>
<p>تحقّق من حالة الطرد أمام عامل التوصيل. في حال وجود ضرر ظاهر، ارفض الاستلام وأعلمنا في نفس اليوم.</p>

<h3>6. الضمان</h3>
<p>الآلات والعدد الكهربائية مشمولة بضمان الصانع. احتفظ بفاتورتك فهي دليل الشراء. لا يشمل
الضمان الاستعمال العادي ولا المواد الاستهلاكية ولا الأضرار الناتجة عن سوء الاستعمال.</p>

<h3>7. المسؤولية</h3>
<p>منتجاتنا موجّهة للاستعمال المهني أو المتمرّس. يُرجى احترام تعليمات السلامة واستعمال
وسائل الحماية المناسبة.</p>

<h3>8. القانون المطبّق</h3>
<p>تخضع هذه الشروط للقانون التونسي. في حال نزاع، نفضّل الحل الودّي قبل أي إجراء آخر.</p>
""",
    },
    {
        "slug": "politique-de-retour",
        "ordre": 3,
        "titre_fr": "Politique de retour et d'échange",
        "titre_ar": "سياسة الاسترجاع والتبديل",
        "contenu_fr": """
<h3>Vous pouvez refuser à la livraison</h3>
<p>Le moyen le plus simple : ouvrez le colis devant le livreur. Si le produit ne correspond
pas ou s'il est endommagé, <strong>refusez-le</strong>. Vous ne payez rien.</p>

<h3>Après réception</h3>
<p>Vous disposez de <strong>7 jours</strong> à compter de la réception pour demander un
échange ou un retour. Contactez-nous par téléphone ou WhatsApp avec votre numéro de
commande avant de renvoyer quoi que ce soit.</p>

<h4>Conditions</h4>
<ul>
  <li>Le produit doit être <strong>neuf, non utilisé</strong> et dans son emballage d'origine.</li>
  <li>Les accessoires, notices et protections doivent être présents.</li>
  <li>Le numéro de commande doit être communiqué.</li>
</ul>

<h4>Ce qui ne peut pas être repris</h4>
<ul>
  <li>Les consommables entamés (colle, clous, crayons de cire).</li>
  <li>Les fraises, mèches et disques ayant servi : une seule utilisation laisse des traces.</li>
  <li>Les produits commandés spécialement à votre demande.</li>
</ul>

<h3>Erreur de notre part</h3>
<p>Produit non conforme, référence erronée, article manquant ou cassé à l'arrivée :
<strong>nous prenons en charge la totalité des frais de retour</strong> et nous vous
envoyons le bon produit ou vous remboursons, à votre choix.</p>

<h3>Changement d'avis</h3>
<p>Si le retour vient d'un changement d'avis de votre part, les frais de retour restent
à votre charge.</p>

<h3>Remboursement</h3>
<p>Une fois le produit reçu et vérifié, le remboursement est effectué sous 7 jours
ouvrables, par le moyen convenu ensemble.</p>
""",
        "contenu_ar": """
<h3>يمكنك الرفض عند التوصيل</h3>
<p>أسهل طريقة: افتح الطرد أمام عامل التوصيل. إذا كان المنتج غير مطابق أو متضرّراً،
<strong>ارفضه</strong> ولن تدفع شيئاً.</p>

<h3>بعد الاستلام</h3>
<p>لديك <strong>7 أيام</strong> من تاريخ الاستلام لطلب التبديل أو الإرجاع. اتصل بنا هاتفياً أو
عبر واتساب مع رقم طلبيتك قبل إرجاع أي شيء.</p>

<h4>الشروط</h4>
<ul>
  <li>أن يكون المنتج <strong>جديداً وغير مستعمل</strong> وفي علبته الأصلية.</li>
  <li>وجود جميع الملحقات والكتيّبات والواقيات.</li>
  <li>تقديم رقم الطلبية.</li>
</ul>

<h4>ما لا يمكن إرجاعه</h4>
<ul>
  <li>المواد الاستهلاكية المفتوحة (غراء، مسامير، أقلام شمع).</li>
  <li>رؤوس القطع والريش والأقراص التي استُعملت، فحتى استعمال واحد يترك أثراً.</li>
  <li>المنتجات المطلوبة خصيصاً بطلب منك.</li>
</ul>

<h3>في حال الخطأ من طرفنا</h3>
<p>منتج غير مطابق أو مرجع خاطئ أو قطعة ناقصة أو مكسورة عند الوصول:
<strong>نتكفّل بكامل معاليم الإرجاع</strong> ونرسل لك المنتج الصحيح أو نعيد لك المبلغ، حسب اختيارك.</p>

<h3>تغيير الرأي</h3>
<p>إذا كان الإرجاع بسبب تغيير رأيك، تبقى معاليم الإرجاع على عاتقك.</p>

<h3>إرجاع المبلغ</h3>
<p>بعد استلام المنتج والتثبّت منه، يتم إرجاع المبلغ في أجل 7 أيام عمل بالطريقة المتفق عليها.</p>
""",
    },
    {
        "slug": "politique-de-confidentialite",
        "ordre": 4,
        "titre_fr": "Politique de confidentialité",
        "titre_ar": "سياسة الخصوصية",
        "contenu_fr": """
<p>Cette page explique quelles informations nous recueillons, pourquoi, et ce que vous
pouvez demander à leur sujet.</p>

<h3>Ce que nous collectons</h3>
<ul>
  <li><strong>Pour votre commande :</strong> nom, numéro de téléphone, gouvernorat, ville
      et adresse de livraison. Ces informations sont indispensables pour vous appeler,
      confirmer, préparer et livrer.</li>
  <li><strong>Si vous laissez un avis :</strong> le nom affiché et, si vous le fournissez,
      un numéro de téléphone servant uniquement à vérifier que l'achat a bien eu lieu.
      Ce numéro n'est jamais publié.</li>
  <li><strong>Si vous remplissez le formulaire sans valider :</strong> nous conservons votre
      nom, votre téléphone et le contenu de votre panier afin de vous rappeler. Demandez-nous
      de les supprimer et nous le ferons.</li>
</ul>

<h3>Mesure d'audience et publicité</h3>
<p>Ce site utilise le <strong>Pixel Meta</strong> et l'API de conversions de Meta pour mesurer
l'efficacité de nos publicités sur Facebook et Instagram. Ces outils reçoivent des
informations sur les pages consultées et les commandes passées.</p>
<p>Les données personnelles transmises à Meta (téléphone, prénom, nom, ville) le sont
<strong>uniquement sous forme chiffrée et irréversible</strong> : Meta ne peut pas les lire,
elles servent seulement à rapprocher une commande d'une publicité. Nous n'envoyons jamais
votre numéro ni votre nom en clair.</p>

<h3>Ce que nous ne faisons pas</h3>
<ul>
  <li>Nous ne vendons ni ne louons vos informations.</li>
  <li>Nous ne les transmettons à personne d'autre que le transporteur chargé de votre colis.</li>
  <li>Nous ne vous demandons jamais de coordonnées bancaires : le paiement se fait
      en espèces au livreur.</li>
</ul>

<h3>Durée de conservation</h3>
<p>Les commandes sont conservées pour nos obligations comptables et pour le suivi du
service après-vente. Les paniers non validés sont supprimés lorsqu'ils ne sont plus utiles.</p>

<h3>Vos droits</h3>
<p>Vous pouvez nous demander à tout moment quelles informations nous détenons sur vous,
les faire corriger ou les faire supprimer. Écrivez-nous à l'adresse indiquée en bas de page,
en précisant votre nom et le numéro de téléphone utilisé lors de la commande.</p>
""",
        "contenu_ar": """
<p>تشرح هذه الصفحة ما نجمعه من معلومات ولماذا، وما يمكنك طلبه بشأنها.</p>

<h3>ما نجمعه</h3>
<ul>
  <li><strong>من أجل طلبيتك:</strong> الاسم، رقم الهاتف، الولاية، المدينة وعنوان التوصيل.
      هذه المعلومات ضرورية للاتصال بك وتأكيد الطلب وتحضيره وتوصيله.</li>
  <li><strong>إذا تركت رأياً:</strong> الاسم المعروض، ورقم الهاتف إن قدّمته، ويُستعمل فقط
      للتثبّت من أنك اشتريت المنتج فعلاً. لا يُنشر هذا الرقم أبداً.</li>
  <li><strong>إذا ملأت النموذج دون تأكيد:</strong> نحتفظ باسمك ورقمك ومحتوى سلتك حتى نتصل بك.
      يمكنك أن تطلب منا حذفها وسنفعل.</li>
</ul>

<h3>قياس الأداء والإشهار</h3>
<p>يستعمل هذا الموقع <strong>Meta Pixel</strong> وواجهة التحويلات لقياس نجاعة إشهاراتنا على
فيسبوك وإنستغرام.</p>
<p>المعطيات الشخصية المرسلة إلى Meta (الهاتف، الاسم، اللقب، المدينة) تُرسل
<strong>مشفّرة بشكل لا رجعة فيه</strong>: لا يمكن لـ Meta قراءتها، وتُستعمل فقط لربط طلبية
بإشهار. لا نرسل رقمك ولا اسمك بشكل واضح أبداً.</p>

<h3>ما لا نقوم به</h3>
<ul>
  <li>لا نبيع معلوماتك ولا نؤجّرها.</li>
  <li>لا نمرّرها لأي طرف عدا شركة التوصيل المكلّفة بطردك.</li>
  <li>لا نطلب منك أبداً معطيات بنكية: الدفع نقداً عند الاستلام.</li>
</ul>

<h3>مدة الحفظ</h3>
<p>تُحفظ الطلبيات لأغراض محاسبية ولمتابعة خدمة ما بعد البيع. تُحذف السلال غير المؤكدة
عندما تصبح غير ذات فائدة.</p>

<h3>حقوقك</h3>
<p>يمكنك في أي وقت أن تطلب معرفة ما نحتفظ به عنك، أو تصحيحه، أو حذفه. راسلنا على العنوان
المذكور أسفل الصفحة مع ذكر اسمك ورقم الهاتف المستعمل في الطلبية.</p>
""",
    },
    {
        "slug": "contact",
        "ordre": 5,
        "titre_fr": "Nous contacter",
        "titre_ar": "اتصل بنا",
        "contenu_fr": """
<p>Une question sur un produit, une compatibilité, un devis pour votre atelier, ou le suivi
d'une commande ? Nous répondons.</p>

<h3>Le plus rapide : WhatsApp</h3>
<p>C'est le moyen le plus direct. Envoyez-nous une photo de la pièce ou la référence
recherchée, nous vous répondons avec le produit correspondant et son prix.</p>

<h3>Par téléphone</h3>
<p>Appelez-nous pour un conseil avant achat ou pour le suivi d'une commande en cours.
Gardez votre numéro de commande sous la main.</p>

<h3>Par e-mail</h3>
<p>Pour les demandes détaillées, les devis en quantité ou les documents administratifs.</p>

<h3>Suivre une commande</h3>
<p>Vous pouvez consulter l'état de votre commande à tout moment depuis la page
<a href="/suivi">Suivre ma commande</a>, avec votre numéro de commande et le téléphone
utilisé lors de l'achat.</p>

<h3>Professionnels et ateliers</h3>
<p>Vous achetez en quantité ? Beaucoup de nos consommables bénéficient de prix dégressifs
affichés directement sur la fiche produit. Pour un besoin régulier ou une référence que
vous ne trouvez pas, contactez-nous : nous pouvons commander pour vous.</p>

<p>Nos coordonnées complètes figurent en bas de chaque page.</p>
""",
        "contenu_ar": """
<p>عندك سؤال حول منتج أو توافق قطعة أو تسعيرة لورشتك أو متابعة طلبية؟ نحن نجيب.</p>

<h3>الأسرع: واتساب</h3>
<p>هذه أسرع وسيلة. أرسل لنا صورة القطعة أو المرجع المطلوب، ونجيبك بالمنتج المناسب وسعره.</p>

<h3>عبر الهاتف</h3>
<p>اتصل بنا للاستشارة قبل الشراء أو لمتابعة طلبية جارية. احتفظ برقم طلبيتك.</p>

<h3>عبر البريد الإلكتروني</h3>
<p>للطلبات المفصّلة أو التسعيرات بالجملة أو الوثائق الإدارية.</p>

<h3>متابعة طلبية</h3>
<p>يمكنك معرفة حالة طلبيتك في أي وقت من صفحة <a href="/suivi">تتبع طلبيتي</a>، برقم الطلبية
ورقم الهاتف المستعمل عند الشراء.</p>

<h3>للمحترفين والورشات</h3>
<p>تشتري بالكمية؟ العديد من موادنا الاستهلاكية لها أسعار تنخفض مع الكمية، معروضة مباشرة في
صفحة المنتج. لحاجة دورية أو مرجع لا تجده، اتصل بنا: يمكننا طلبه من أجلك.</p>

<p>معلومات الاتصال الكاملة موجودة أسفل كل صفحة.</p>
""",
    },
]


def main():
    with boutique.app.app_context():
        crees, mises_a_jour = 0, 0
        for donnees in PAGES:
            page = boutique.PageStatique.query.filter_by(slug=donnees["slug"]).first()
            if page:
                mises_a_jour += 1
            else:
                page = boutique.PageStatique(slug=donnees["slug"])
                boutique.db.session.add(page)
                crees += 1

            page.titre_fr = donnees["titre_fr"]
            page.titre_ar = donnees["titre_ar"]
            page.contenu_fr = donnees["contenu_fr"].strip()
            page.contenu_ar = donnees["contenu_ar"].strip()
            page.ordre = donnees["ordre"]
            page.actif = True
            page.date_maj = boutique.datetime.utcnow()

        boutique.db.session.commit()
        print("%s page(s) creee(s), %s mise(s) a jour." % (crees, mises_a_jour))
        for p in boutique.PageStatique.query.order_by(boutique.PageStatique.ordre).all():
            print("   /page/%-28s %-34s %s caracteres"
                  % (p.slug, p.titre_fr, len(p.contenu_fr or "")))


if __name__ == "__main__":
    main()
