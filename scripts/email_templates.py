"""Templates d'emails pour les différentes catégories d'adhérents."""

EMAIL_TEMPLATES = {
    "Adherent 2025": {
        "subject": "Renouvellement adhésion 2026 - La Coop des Communs",
        "body_text": """Chère amie, cher ami,

Petit message de précision :
le mail que tu as reçu récemment concernant le renouvellement de l'adhésion à La Coop des Communs a été envoyé par erreur depuis une mauvaise adresse mail.

👉 Ce message n'est pas un spam : il s'agit bien d'une communication officielle de l'association.
Toutes nos excuses pour cette confusion.

Je me permets donc de te renvoyer ci-dessous le message initial depuis la bonne adresse.

👉 Lien d'adhésion 2026 : https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026

Merci pour ta compréhension et pour ton soutien fidèle à La Coop des Communs 🌱

Bien cordialement,

@@SIG_NAME@@
@@SIG_ROLE@@
@@SIG_PHONE@@
@@SIG_EMAIL@@
coopdescommuns.org

---

Chère amie, cher ami,

Merci encore d'avoir marqué ton attachement à La Coop des Communs en ayant adhéré en 2025.

D'avance, je te remercie de poursuivre ton engagement en renouvelant ton adhésion pour 2026.

La cotisation de base est de 25 €, inchangée par rapport à 2025. Si tu peux, une cotisation de soutien de 100 € est la bienvenue ; dans ce cas, un reçu fiscal te sera délivré.

Voici le lien pour payer via Hello Asso :
https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026

En cas d'impossibilité, tu peux aussi envoyer un chèque à La Coop des Communs,
20 rue du Cdt Mouchotte – 75014 PARIS
(merci d'éviter si tu peux).

Notre dernière Newsletter (https://coopdescommuns.org/fr/newsletter-29/) te donne nos actualités et celles des groupes de travail. Ces groupes constituent notre richesse, là où s'exercent les regards croisés entre communs et ESS, d'horizons et de disciplines diversifiés, et où naissent nos projets et programmes d'action-recherche associant praticiens et chercheurs.

Retrouve la description des groupes de travail sur https://coopdescommuns.org/, à la rubrique « Nos groupes de travail en action », et les dernières actualités des groupes ici :
https://coopdescommuns.org/fr/actus-groupes-travail/

Nous prévoyons une première assemblée générale le 12 juin prochain après-midi et une petite fête pour nos 10 ans le 13 juin. Prévoyez votre journée ! Et d'autres événements à venir.

L'entretien et l'animation de notre communauté décloisonnée sont l'un de nos enjeux essentiels. À cette fin, la manifestation d'intérêt que représente l'adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.

Merci d'avance. Comme tu le sais, le collectif dépend aussi de chacun de nous.

Bien cordialement
""",
        "body_html": """<html>
<head></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="padding: 15px; margin-bottom: 25px;">
        <p style="margin: 0 0 10px 0;"><strong>Chère amie, cher ami,</strong></p>
        <p style="margin: 0 0 10px 0;"><strong>Petit message de précision :</strong><br>
        le mail que tu as reçu récemment concernant le renouvellement de l'adhésion à La Coop des Communs a été envoyé par erreur depuis une mauvaise adresse mail.</p>
        <p style="margin: 0 0 10px 0;">👉 <strong>Ce message n'est pas un spam</strong> : il s'agit bien d'une communication officielle de l'association.<br>
        Toutes nos excuses pour cette confusion.</p>
        <p style="margin: 0 0 10px 0;">Je me permets donc de te renvoyer ci-dessous le message initial depuis la bonne adresse.</p>
        <p style="margin: 0 0 10px 0;">👉 <strong>Lien d'adhésion 2026 :</strong> <a href="https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026">https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026</a></p>
        <p style="margin: 15px 0 0 0;">Merci pour ta compréhension et pour ton soutien fidèle à La Coop des Communs 🌱</p>
    </div>
    
    <p style="margin-bottom: 15px;">Bien cordialement,</p>
    <table width="400" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 25px;">
        <tr>
            <td width="124" valign="top" style="padding:0cm 7.5pt 0cm 0cm">
                <img width="85" height="69" src="cid:logo" style="width:.8854in;height:.7187in">
            </td>
            <td style="padding:0cm 0cm 0cm 0cm">
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <b><span style="font-size:9pt;font-family:Poppins;color:#4B4B4D">@@SIG_NAME@@</span></b>
                    <span style="font-size:9pt;font-family:Poppins"><br>
                    <span style="color:#3CB1D4">@@SIG_ROLE@@</span></span>
                </p>
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <span style="font-size:9pt;font-family:Poppins">@@SIG_PHONE@@<br>
                    <a href="mailto:@@SIG_EMAIL@@"><span style="color:#4B4B4D">@@SIG_EMAIL@@</span></a><br>
                    <a href="https://coopdescommuns.org/"><span style="color:#4B4B4D">coopdescommuns.org</span></a></span>
                </p>
            </td>
        </tr>
    </table>
    
    <hr style="border: none; border-top: 2px solid #ddd; margin: 30px 0;">
    
    <p>Chère amie, cher ami,</p>
    <p>Merci encore d'avoir marqué ton attachement à La Coop des Communs en ayant adhéré en 2025.</p>
    <p>D'avance, je te remercie de poursuivre ton engagement en renouvelant ton adhésion pour 2026.</p>
    <p>La cotisation de base est de <strong>25 €</strong>, inchangée par rapport à 2025. Si tu peux, une cotisation de soutien de <strong>100 €</strong> est la bienvenue ; dans ce cas, un reçu fiscal te sera délivré.</p>
    <p style="margin-top: 25px;">
        <a href="https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026" 
           style="background-color: #2c5aa0; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
            Adhérer pour 2026 via Hello Asso
        </a>
    </p>
    <p style="font-size: 0.9em; color: #666;">En cas d'impossibilité, tu peux aussi envoyer un chèque à La Coop des Communs,<br>
    20 rue du Cdt Mouchotte – 75014 PARIS<br>
    (merci d'éviter si tu peux).</p>
    
    <p>Notre <a href="https://coopdescommuns.org/fr/newsletter-29/">dernière Newsletter</a> te donne nos actualités et celles des groupes de travail. Ces groupes constituent notre richesse, là où s'exercent les regards croisés entre communs et ESS, d'horizons et de disciplines diversifiés, et où naissent nos projets et programmes d'action-recherche associant praticiens et chercheurs.</p>
    
    <p>Retrouve la description des groupes de travail sur <a href="https://coopdescommuns.org/">https://coopdescommuns.org/</a>, à la rubrique « Nos groupes de travail en action », et les dernières actualités des groupes ici :<br>
    <a href="https://coopdescommuns.org/fr/actus-groupes-travail/">https://coopdescommuns.org/fr/actus-groupes-travail/</a></p>
    
    <p>Nous prévoyons une première <strong>assemblée générale le 12 juin prochain après-midi</strong> et une petite fête pour nos <strong>10 ans le 13 juin</strong>. Prévoyez votre journée ! Et d'autres événements à venir.</p>
    
    <p>L'entretien et l'animation de notre communauté décloisonnée sont l'un de nos enjeux essentiels. À cette fin, la manifestation d'intérêt que représente l'adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.</p>
    
    <p>Merci d'avance. Comme tu le sais, le collectif dépend aussi de chacun de nous.</p>
    
    <p style="margin-top: 30px;">Bien cordialement,</p>
    
    <table width="400" cellspacing="0" cellpadding="0" border="0" style="margin-top: 20px;">
        <tr>
            <td width="124" valign="top" style="padding:0cm 7.5pt 0cm 0cm">
                <img width="85" height="69" src="cid:logo" style="width:.8854in;height:.7187in">
            </td>
            <td style="padding:0cm 0cm 0cm 0cm">
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <b><span style="font-size:9pt;font-family:Poppins;color:#4B4B4D">@@SIG_NAME@@</span></b>
                    <span style="font-size:9pt;font-family:Poppins"><br>
                    <span style="color:#3CB1D4">@@SIG_ROLE@@</span></span>
                </p>
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <span style="font-size:9pt;font-family:Poppins">@@SIG_PHONE@@<br>
                    <a href="mailto:@@SIG_EMAIL@@"><span style="color:#4B4B4D">@@SIG_EMAIL@@</span></a><br>
                    <a href="https://coopdescommuns.org/"><span style="color:#4B4B4D">coopdescommuns.org</span></a></span>
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },
    
    "Adherent 2024": {
        "subject": "Renouvellement adhésion 2026 - La Coop des Communs",
        "body_text": """Chère amie, cher ami,

Petit message de précision :
le mail que tu as reçu récemment concernant le renouvellement de l'adhésion à La Coop des Communs a été envoyé par erreur depuis une mauvaise adresse mail.

👉 Ce message n'est pas un spam : il s'agit bien d'une communication officielle de l'association.
Toutes nos excuses pour cette confusion.

Je me permets donc de te renvoyer ci-dessous le message initial depuis la bonne adresse.

👉 Lien d'adhésion 2026 : https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026

Merci pour ta compréhension et pour ton soutien fidèle à La Coop des Communs 🌱

Bien cordialement,

@@SIG_NAME@@
@@SIG_ROLE@@
@@SIG_PHONE@@
@@SIG_EMAIL@@
coopdescommuns.org

---

Chère amie, cher ami,

Merci encore d'avoir marqué ton attachement à La Coop des Communs en ayant adhéré en 2024.

Tu n'as pas renouvelé ton adhésion en 2025, mais peut-être souhaites-tu le faire en 2026 ?

La cotisation de base est de 25 €, inchangée par rapport à 2025. Si tu peux, une cotisation de soutien de 100 € est la bienvenue ; dans ce cas, un reçu fiscal te sera délivré.

Voici le lien pour payer via Hello Asso :
https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026

En cas d'impossibilité, tu peux aussi envoyer un chèque à La Coop des Communs,
20 rue du Cdt Mouchotte – 75014 PARIS
(merci d'éviter si tu peux).

Notre dernière Newsletter (https://coopdescommuns.org/fr/newsletter-29/) te donne nos actualités et celles des groupes de travail. Ces groupes constituent notre richesse, là où s'exercent les regards croisés entre communs et ESS, d'horizons et de disciplines diversifiés, et où naissent nos projets et programmes d'action-recherche associant praticiens et chercheurs.

Retrouve la description des groupes de travail sur https://coopdescommuns.org/, à la rubrique « Nos groupes de travail en action », et les dernières actualités des groupes ici :
https://coopdescommuns.org/fr/actus-groupes-travail/

Nous prévoyons une première assemblée générale le 12 juin prochain après-midi et une petite fête pour nos 10 ans le 13 juin. Prévoyez votre journée ! Et d'autres événements à venir.

L'entretien et l'animation de notre communauté décloisonnée sont l'un de nos enjeux essentiels. À cette fin, la manifestation d'intérêt que représente l'adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.

Merci d'avance. Comme tu le sais, le collectif dépend aussi de chacun de nous.

Bien cordialement,

@@SIG_NAME@@
@@SIG_ROLE@@
@@SIG_PHONE@@
@@SIG_EMAIL@@
coopdescommuns.org
""",
        "body_html": """<html>
<head></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="padding: 15px; margin-bottom: 25px;">
        <p style="margin: 0 0 10px 0;"><strong>Chère amie, cher ami,</strong></p>
        <p style="margin: 0 0 10px 0;"><strong>Petit message de précision :</strong><br>
        le mail que tu as reçu récemment concernant le renouvellement de l'adhésion à La Coop des Communs a été envoyé par erreur depuis une mauvaise adresse mail.</p>
        <p style="margin: 0 0 10px 0;">👉 <strong>Ce message n'est pas un spam</strong> : il s'agit bien d'une communication officielle de l'association.<br>
        Toutes nos excuses pour cette confusion.</p>
        <p style="margin: 0 0 10px 0;">Je me permets donc de te renvoyer ci-dessous le message initial depuis la bonne adresse.</p>
        <p style="margin: 0 0 10px 0;">👉 <strong>Lien d'adhésion 2026 :</strong> <a href="https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026">https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026</a></p>
        <p style="margin: 15px 0 0 0;">Merci pour ta compréhension et pour ton soutien fidèle à La Coop des Communs 🌱</p>
    </div>
    
    <p style="margin-bottom: 15px;">Bien cordialement,</p>
    
    <table width="400" cellspacing="0" cellpadding="0" border="0" style="margin-top: 20px;">
        <tr>
            <td width="124" valign="top" style="padding:0cm 7.5pt 0cm 0cm">
                <img width="85" height="69" src="cid:logo" style="width:.8854in;height:.7187in">
            </td>
            <td style="padding:0cm 0cm 0cm 0cm">
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <b><span style="font-size:9pt;font-family:Poppins;color:#4B4B4D">@@SIG_NAME@@</span></b>
                    <span style="font-size:9pt;font-family:Poppins"><br>
                    <span style="color:#3CB1D4">@@SIG_ROLE@@</span></span>
                </p>
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <span style="font-size:9pt;font-family:Poppins">@@SIG_PHONE@@<br>
                    <a href="mailto:@@SIG_EMAIL@@"><span style="color:#4B4B4D">@@SIG_EMAIL@@</span></a><br>
                    <a href="https://coopdescommuns.org/"><span style="color:#4B4B4D">coopdescommuns.org</span></a></span>
                </p>
            </td>
        </tr>
    </table>
    
    <hr style="border: none; border-top: 2px solid #ddd; margin: 30px 0;">
    
    <p>Chère amie, cher ami,</p>
    <p>Merci encore d'avoir marqué ton attachement à La Coop des Communs en ayant adhéré en 2024.</p>
    <p>Tu n'as pas renouvelé ton adhésion en 2025, mais peut-être souhaites-tu le faire en 2026 ?</p>
    <p>La cotisation de base est de <strong>25 €</strong>, inchangée par rapport à 2025. Si tu peux, une cotisation de soutien de <strong>100 €</strong> est la bienvenue ; dans ce cas, un reçu fiscal te sera délivré.</p>
    <p style="margin-top: 25px;">
        <a href="https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026" 
           style="background-color: #2c5aa0; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
            Adhérer pour 2026 via Hello Asso
        </a>
    </p>
    <p style="font-size: 0.9em; color: #666;">En cas d'impossibilité, tu peux aussi envoyer un chèque à La Coop des Communs,<br>
    20 rue du Cdt Mouchotte – 75014 PARIS<br>
    (merci d'éviter si tu peux).</p>
    
    <p>Notre <a href="https://coopdescommuns.org/fr/newsletter-29/">dernière Newsletter</a> te donne nos actualités et celles des groupes de travail. Ces groupes constituent notre richesse, là où s'exercent les regards croisés entre communs et ESS, d'horizons et de disciplines diversifiés, et où naissent nos projets et programmes d'action-recherche associant praticiens et chercheurs.</p>
    
    <p>Retrouve la description des groupes de travail sur <a href="https://coopdescommuns.org/">https://coopdescommuns.org/</a>, à la rubrique « Nos groupes de travail en action », et les dernières actualités des groupes ici :<br>
    <a href="https://coopdescommuns.org/fr/actus-groupes-travail/">https://coopdescommuns.org/fr/actus-groupes-travail/</a></p>
    
    <p>Nous prévoyons une première <strong>assemblée générale le 12 juin prochain après-midi</strong> et une petite fête pour nos <strong>10 ans le 13 juin</strong>. Prévoyez votre journée ! Et d'autres événements à venir.</p>
    
    <p>L'entretien et l'animation de notre communauté décloisonnée sont l'un de nos enjeux essentiels. À cette fin, la manifestation d'intérêt que représente l'adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.</p>
    
    <p>Merci d'avance. Comme tu le sais, le collectif dépend aussi de chacun de nous.</p>
    
    <p style="margin-top: 30px;">Bien cordialement,</p>
    
    <table width="400" cellspacing="0" cellpadding="0" border="0" style="margin-top: 20px;">
        <tr>
            <td width="124" valign="top" style="padding:0cm 7.5pt 0cm 0cm">
                <img width="85" height="69" src="cid:logo" style="width:.8854in;height:.7187in">
            </td>
            <td style="padding:0cm 0cm 0cm 0cm">
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <b><span style="font-size:9pt;font-family:Poppins;color:#4B4B4D">@@SIG_NAME@@</span></b>
                    <span style="font-size:9pt;font-family:Poppins"><br>
                    <span style="color:#3CB1D4">@@SIG_ROLE@@</span></span>
                </p>
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <span style="font-size:9pt;font-family:Poppins">@@SIG_PHONE@@<br>
                    <a href="mailto:@@SIG_EMAIL@@"><span style="color:#4B4B4D">@@SIG_EMAIL@@</span></a><br>
                    <a href="https://coopdescommuns.org/"><span style="color:#4B4B4D">coopdescommuns.org</span></a></span>
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },
    
    "GT non adherent": {
        "subject": "Adhésion 2026 - La Coop des Communs",
        "body_text": """Chère amie, cher ami,

Petit message de précision :
le mail que tu as reçu récemment concernant le renouvellement de l'adhésion à La Coop des Communs a été envoyé par erreur depuis une mauvaise adresse mail.

👉 Ce message n'est pas un spam : il s'agit bien d'une communication officielle de l'association.
Toutes nos excuses pour cette confusion.

Je me permets donc de te renvoyer ci-dessous le message initial depuis la bonne adresse.

👉 Lien d'adhésion 2026 : https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026

Merci pour ta compréhension et pour ton soutien fidèle à La Coop des Communs 🌱

Bien cordialement,

@@SIG_NAME@@
@@SIG_ROLE@@
@@SIG_PHONE@@
@@SIG_EMAIL@@
coopdescommuns.org

---

Chère amie, cher ami,

Merci encore d'avoir marqué ton intérêt pour La Coop des Communs en participant à un ou plusieurs groupes de travail en 2025.

Souhaites-tu t'engager davantage en adhérant à notre association en 2026 ?

La cotisation de base est de 25 €, inchangée par rapport à 2025. Si tu peux, une cotisation de soutien de 100 € est la bienvenue ; dans ce cas, un reçu fiscal te sera délivré.

Voici le lien pour payer via Hello Asso :
https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026

En cas d'impossibilité, tu peux aussi envoyer un chèque à La Coop des Communs,
20 rue du Cdt Mouchotte – 75014 PARIS
(merci d'éviter si tu peux).

Notre dernière Newsletter (https://coopdescommuns.org/fr/newsletter-29/) te donne nos actualités et celles des groupes de travail. Ces groupes constituent notre richesse, là où s'exercent les regards croisés entre communs et ESS, d'horizons et de disciplines diversifiés, et où naissent nos projets et programmes d'action-recherche associant praticiens et chercheurs.

Retrouve la description des groupes de travail sur https://coopdescommuns.org/, à la rubrique « Nos groupes de travail en action », et les dernières actualités des groupes ici :
https://coopdescommuns.org/fr/actus-groupes-travail/

Nous prévoyons une première assemblée générale le 12 juin prochain après-midi et une petite fête pour nos 10 ans le 13 juin. Prévoyez votre journée ! Et d'autres événements à venir.

L'entretien et l'animation de notre communauté décloisonnée sont l'un de nos enjeux essentiels. À cette fin, la manifestation d'intérêt que représente l'adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.

Merci d'avance. Comme tu le sais, le collectif dépend aussi de chacun de nous.

Bien cordialement,

@@SIG_NAME@@
@@SIG_ROLE@@
@@SIG_PHONE@@
@@SIG_EMAIL@@
coopdescommuns.org
""",
        "body_html": """<html>
<head></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="padding: 15px; margin-bottom: 25px;">
        <p style="margin: 0 0 10px 0;"><strong>Chère amie, cher ami,</strong></p>
        <p style="margin: 0 0 10px 0;"><strong>Petit message de précision :</strong><br>
        le mail que tu as reçu récemment concernant le renouvellement de l'adhésion à La Coop des Communs a été envoyé par erreur depuis une mauvaise adresse mail.</p>
        <p style="margin: 0 0 10px 0;">👉 <strong>Ce message n'est pas un spam</strong> : il s'agit bien d'une communication officielle de l'association.<br>
        Toutes nos excuses pour cette confusion.</p>
        <p style="margin: 0 0 10px 0;">Je me permets donc de te renvoyer ci-dessous le message initial depuis la bonne adresse.</p>
        <p style="margin: 0 0 10px 0;">👉 <strong>Lien d'adhésion 2026 :</strong> <a href="https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026">https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026</a></p>
        <p style="margin: 15px 0 0 0;">Merci pour ta compréhension et pour ton soutien fidèle à La Coop des Communs 🌱</p>
    </div>
    
    <p style="margin-bottom: 15px;">Bien cordialement,</p>
    
    <table width="400" cellspacing="0" cellpadding="0" border="0" style="margin-top: 20px;">
        <tr>
            <td width="124" valign="top" style="padding:0cm 7.5pt 0cm 0cm">
                <img width="85" height="69" src="cid:logo" style="width:.8854in;height:.7187in">
            </td>
            <td style="padding:0cm 0cm 0cm 0cm">
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <b><span style="font-size:9pt;font-family:Poppins;color:#4B4B4D">@@SIG_NAME@@</span></b>
                    <span style="font-size:9pt;font-family:Poppins"><br>
                    <span style="color:#3CB1D4">@@SIG_ROLE@@</span></span>
                </p>
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <span style="font-size:9pt;font-family:Poppins">@@SIG_PHONE@@<br>
                    <a href="mailto:@@SIG_EMAIL@@"><span style="color:#4B4B4D">@@SIG_EMAIL@@</span></a><br>
                    <a href="https://coopdescommuns.org/"><span style="color:#4B4B4D">coopdescommuns.org</span></a></span>
                </p>
            </td>
        </tr>
    </table>
    
    <hr style="border: none; border-top: 2px solid #ddd; margin: 30px 0;">
    
    <p>Chère amie, cher ami,</p>
    <p>Merci encore d'avoir marqué ton intérêt pour La Coop des Communs en participant à un ou plusieurs groupes de travail en 2025.</p>
    <p>Souhaites-tu t'engager davantage en adhérant à notre association en 2026 ?</p>
    <p>La cotisation de base est de <strong>25 €</strong>, inchangée par rapport à 2025. Si tu peux, une cotisation de soutien de <strong>100 €</strong> est la bienvenue ; dans ce cas, un reçu fiscal te sera délivré.</p>
    <p style="margin-top: 25px;">
        <a href="https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026" 
           style="background-color: #2c5aa0; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
            Adhérer pour 2026 via Hello Asso
        </a>
    </p>
    <p style="font-size: 0.9em; color: #666;">En cas d'impossibilité, tu peux aussi envoyer un chèque à La Coop des Communs,<br>
    20 rue du Cdt Mouchotte – 75014 PARIS<br>
    (merci d'éviter si tu peux).</p>
    
    <p>Notre <a href="https://coopdescommuns.org/fr/newsletter-29/">dernière Newsletter</a> te donne nos actualités et celles des groupes de travail. Ces groupes constituent notre richesse, là où s'exercent les regards croisés entre communs et ESS, d'horizons et de disciplines diversifiés, et où naissent nos projets et programmes d'action-recherche associant praticiens et chercheurs.</p>
    
    <p>Retrouve la description des groupes de travail sur <a href="https://coopdescommuns.org/">https://coopdescommuns.org/</a>, à la rubrique « Nos groupes de travail en action », et les dernières actualités des groupes ici :<br>
    <a href="https://coopdescommuns.org/fr/actus-groupes-travail/">https://coopdescommuns.org/fr/actus-groupes-travail/</a></p>
    
    <p>Nous prévoyons une première <strong>assemblée générale le 12 juin prochain après-midi</strong> et une petite fête pour nos <strong>10 ans le 13 juin</strong>. Prévoyez votre journée ! Et d'autres événements à venir.</p>
    
    <p>L'entretien et l'animation de notre communauté décloisonnée sont l'un de nos enjeux essentiels. À cette fin, la manifestation d'intérêt que représente l'adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.</p>
    
    <p>Merci d'avance. Comme tu le sais, le collectif dépend aussi de chacun de nous.</p>
    
    <p style="margin-top: 30px;">Bien cordialement,</p>
    
    <table width="400" cellspacing="0" cellpadding="0" border="0" style="margin-top: 20px;">
        <tr>
            <td width="124" valign="top" style="padding:0cm 7.5pt 0cm 0cm">
                <img width="85" height="69" src="cid:logo" style="width:.8854in;height:.7187in">
            </td>
            <td style="padding:0cm 0cm 0cm 0cm">
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <b><span style="font-size:9pt;font-family:Poppins;color:#4B4B4D">@@SIG_NAME@@</span></b>
                    <span style="font-size:9pt;font-family:Poppins"><br>
                    <span style="color:#3CB1D4">@@SIG_ROLE@@</span></span>
                </p>
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <span style="font-size:9pt;font-family:Poppins">@@SIG_PHONE@@<br>
                    <a href="mailto:@@SIG_EMAIL@@"><span style="color:#4B4B4D">@@SIG_EMAIL@@</span></a><br>
                    <a href="https://coopdescommuns.org/"><span style="color:#4B4B4D">coopdescommuns.org</span></a></span>
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },
    
    "Relance Adherent 2025": {
        "subject": "Renouvellement adhésion 2026 - La Coop des Communs",
        "body_text": """Chère amie, cher ami,

Tu n'as pas encore à ce jour renouvelé ton adhésion à La Coop des Communs pour 2026 et je me permets de te relancer.

Ton adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.

D'avance, je te remercie de continuer à faire partie de la communauté en adhérant.

Voici le lien pour payer via Hello Asso https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026

Tu peux aussi envoyer un chèque à La Coop des Communs, 20 rue du Cdt Mouchotte, 75014 PARIS.

La cotisation de base est de 25 €. Si tu peux, une cotisation de soutien de 100 € est la bienvenue ; dans ce cas, un reçu fiscal sera délivré.

Notre dernière Newsletter te donne nos actualités https://coopdescommuns.org/fr/newsletter-29/

Je te rappelle la date de notre prochaine AG, le 12 juin.

Et le 13 juin, nous fêtons nos 10 ans 🌿au cœur du Bois de Vincennes, au sein du Jardin d'agronomie tropicale de Paris

Si tu veux te joindre aux nouveaux adhérents pour faire un point sur l'association et continuer d'apprendre à nous connaître, nous vous proposons de nous réunir le 24 mars de 11 h à 12 h ou le 21 avril de 17h à 18h en ligne : https://us02web.zoom.us/j/XXXXXXXXXX, par téléphone : +33170379729.  Merci de le dire à contact@coopdescommuns.org

Comme vous le savez, le collectif dépend aussi de chacun de nous.

Merci d'avance.

Bien cordialement.

PS : Si vous recevez ce mail, cela veut dire que vous n'avez pas encore renouvelé votre cotisation ou que vous avez une autre adresse mail pour le faire. Merci de votre compréhension pour ce rappel.
""",
        "body_html": """<html>
<head></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <p>Chère amie, cher ami,</p>

    <p>Tu n'as pas encore à ce jour renouvelé ton adhésion à La Coop des Communs pour 2026 et je me permets de te relancer.</p>

    <p>Ton adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.</p>

    <p>D'avance, je te remercie de continuer à faire partie de la communauté en adhérant.</p>

    <p style="margin-top: 25px;">
        <a href="https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026"
           style="background-color: #2c5aa0; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
            Adhérer pour 2026 via Hello Asso
        </a>
    </p>

    <p style="font-size: 0.9em; color: #666;">Tu peux aussi envoyer un chèque à La Coop des Communs, 20 rue du Cdt Mouchotte, 75014 PARIS.</p>

    <p>La cotisation de base est de <strong>25 €</strong>. Si tu peux, une cotisation de soutien de <strong>100 €</strong> est la bienvenue ; dans ce cas, un reçu fiscal sera délivré.</p>

    <p>&nbsp;</p>

    <p>Notre <a href="https://coopdescommuns.org/fr/newsletter-29/">dernière Newsletter</a> te donne nos actualités.</p>

    <p>Je te rappelle la date de notre prochaine <strong>AG, le 12 juin</strong>.</p>

    <p>Et le <strong>13 juin</strong>, nous fêtons nos <strong>10 ans</strong> 🌿au cœur du Bois de Vincennes, au sein du Jardin d'agronomie tropicale de Paris</p>

    <p>&nbsp;</p>

    <p>Si tu veux te joindre aux nouveaux adhérents pour faire un point sur l'association et continuer d'apprendre à nous connaître, nous vous proposons de nous réunir le <strong>24 mars de 11 h à 12 h</strong> ou le <strong>21 avril de 17h à 18h</strong> en ligne : <a href="https://us02web.zoom.us/j/XXXXXXXXXX">https://us02web.zoom.us/j/XXXXXXXXXX</a>, par téléphone : +33170379729.  Merci de le dire à <a href="mailto:contact@coopdescommuns.org">contact@coopdescommuns.org</a></p>

    <p>Comme vous le savez, le collectif dépend aussi de chacun de nous.</p>

    <p>Merci d'avance.</p>

    <p>Bien cordialement.</p>

    <table width="400" cellspacing="0" cellpadding="0" border="0" style="margin-top: 20px;">
        <tr>
            <td width="124" valign="top" style="padding:0cm 7.5pt 0cm 0cm">
                <img width="85" height="69" src="cid:logo" style="width:.8854in;height:.7187in">
            </td>
            <td style="padding:0cm 0cm 0cm 0cm">
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <b><span style="font-size:9pt;font-family:Poppins;color:#4B4B4D">@@SIG_NAME@@</span></b>
                    <span style="font-size:9pt;font-family:Poppins"><br>
                    <span style="color:#3CB1D4">@@SIG_ROLE@@</span></span>
                </p>
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <span style="font-size:9pt;font-family:Poppins">@@SIG_PHONE@@<br>
                    <a href="mailto:@@SIG_EMAIL@@"><span style="color:#4B4B4D">@@SIG_EMAIL@@</span></a><br>
                    <a href="https://coopdescommuns.org/"><span style="color:#4B4B4D">coopdescommuns.org</span></a></span>
                </p>
            </td>
        </tr>
    </table>

    <p style="font-size: 0.85em; color: #888; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px;">
        PS : Si vous recevez ce mail, cela veut dire que vous n'avez pas encore renouvelé votre cotisation ou que vous avez une autre adresse mail pour le faire. Merci de votre compréhension pour ce rappel.
    </p>
</body>
</html>
"""
    },

    "Relance Adherent 2024": {
        "subject": "Renouvellement adhésion 2026 - La Coop des Communs",
        "body_text": """Chère amie, cher ami,

Tu n'as pas encore à ce jour renouvelé ton adhésion à La Coop des Communs pour 2026 et je me permets de te relancer.

Ton adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.

D'avance, je te remercie de continuer à faire partie de la communauté en adhérant.

Voici le lien pour payer via Hello Asso https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026

Tu peux aussi envoyer un chèque à La Coop des Communs, 20 rue du Cdt Mouchotte, 75014 PARIS.

La cotisation de base est de 25 €. Si tu peux, une cotisation de soutien de 100 € est la bienvenue ; dans ce cas, un reçu fiscal sera délivré.

Notre dernière Newsletter te donne nos actualités https://coopdescommuns.org/fr/newsletter-29/

Je te rappelle la date de notre prochaine AG, le 12 juin.

Et le 13 juin, nous fêtons nos 10 ans 🌿au cœur du Bois de Vincennes, au sein du Jardin d'agronomie tropicale de Paris

Si tu veux te joindre aux nouveaux adhérents pour faire un point sur l'association et continuer d'apprendre à nous connaître, nous vous proposons de nous réunir le 24 mars de 11 h à 12 h ou le 21 avril de 17h à 18h en ligne : https://us02web.zoom.us/j/XXXXXXXXXX, par téléphone : +33170379729.  Merci de le dire à contact@coopdescommuns.org

Comme vous le savez, le collectif dépend aussi de chacun de nous.

Merci d'avance.

Bien cordialement.

PS : Si vous recevez ce mail, cela veut dire que vous n'avez pas encore renouvelé votre cotisation ou que vous avez une autre adresse mail pour le faire. Merci de votre compréhension pour ce rappel.
""",
        "body_html": """<html>
<head></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <p>Chère amie, cher ami,</p>

    <p>Tu n'as pas encore à ce jour renouvelé ton adhésion à La Coop des Communs pour 2026 et je me permets de te relancer.</p>

    <p>Ton adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.</p>

    <p>D'avance, je te remercie de continuer à faire partie de la communauté en adhérant.</p>

    <p style="margin-top: 25px;">
        <a href="https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026"
           style="background-color: #2c5aa0; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
            Adhérer pour 2026 via Hello Asso
        </a>
    </p>

    <p style="font-size: 0.9em; color: #666;">Tu peux aussi envoyer un chèque à La Coop des Communs, 20 rue du Cdt Mouchotte, 75014 PARIS.</p>

    <p>La cotisation de base est de <strong>25 €</strong>. Si tu peux, une cotisation de soutien de <strong>100 €</strong> est la bienvenue ; dans ce cas, un reçu fiscal sera délivré.</p>

    <p>&nbsp;</p>

    <p>Notre <a href="https://coopdescommuns.org/fr/newsletter-29/">dernière Newsletter</a> te donne nos actualités.</p>

    <p>Je te rappelle la date de notre prochaine <strong>AG, le 12 juin</strong>.</p>

    <p>Et le <strong>13 juin</strong>, nous fêtons nos <strong>10 ans</strong> 🌿au cœur du Bois de Vincennes, au sein du Jardin d'agronomie tropicale de Paris</p>

    <p>&nbsp;</p>

    <p>Si tu veux te joindre aux nouveaux adhérents pour faire un point sur l'association et continuer d'apprendre à nous connaître, nous vous proposons de nous réunir le <strong>24 mars de 11 h à 12 h</strong> ou le <strong>21 avril de 17h à 18h</strong> en ligne : <a href="https://us02web.zoom.us/j/XXXXXXXXXX">https://us02web.zoom.us/j/XXXXXXXXXX</a>, par téléphone : +33170379729.  Merci de le dire à <a href="mailto:contact@coopdescommuns.org">contact@coopdescommuns.org</a></p>

    <p>Comme vous le savez, le collectif dépend aussi de chacun de nous.</p>

    <p>Merci d'avance.</p>

    <p>Bien cordialement.</p>

    <table width="400" cellspacing="0" cellpadding="0" border="0" style="margin-top: 20px;">
        <tr>
            <td width="124" valign="top" style="padding:0cm 7.5pt 0cm 0cm">
                <img width="85" height="69" src="cid:logo" style="width:.8854in;height:.7187in">
            </td>
            <td style="padding:0cm 0cm 0cm 0cm">
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <b><span style="font-size:9pt;font-family:Poppins;color:#4B4B4D">@@SIG_NAME@@</span></b>
                    <span style="font-size:9pt;font-family:Poppins"><br>
                    <span style="color:#3CB1D4">@@SIG_ROLE@@</span></span>
                </p>
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <span style="font-size:9pt;font-family:Poppins">@@SIG_PHONE@@<br>
                    <a href="mailto:@@SIG_EMAIL@@"><span style="color:#4B4B4D">@@SIG_EMAIL@@</span></a><br>
                    <a href="https://coopdescommuns.org/"><span style="color:#4B4B4D">coopdescommuns.org</span></a></span>
                </p>
            </td>
        </tr>
    </table>

    <p style="font-size: 0.85em; color: #888; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px;">
        PS : Si vous recevez ce mail, cela veut dire que vous n'avez pas encore renouvelé votre cotisation ou que vous avez une autre adresse mail pour le faire. Merci de votre compréhension pour ce rappel.
    </p>
</body>
</html>
"""
    },

    "Evenement non adherent": {
        "subject": "Adhésion 2026 - La Coop des Communs",
        "body_text": """Chère amie, cher ami,

Petit message de précision :
le mail que tu as reçu récemment concernant le renouvellement de l'adhésion à La Coop des Communs a été envoyé par erreur depuis une mauvaise adresse mail.

👉 Ce message n'est pas un spam : il s'agit bien d'une communication officielle de l'association.
Toutes nos excuses pour cette confusion.

Je me permets donc de te renvoyer ci-dessous le message initial depuis la bonne adresse.

👉 Lien d'adhésion 2026 : https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026

Merci pour ta compréhension et pour ton soutien fidèle à La Coop des Communs 🌱

Bien cordialement,

@@SIG_NAME@@
@@SIG_ROLE@@
@@SIG_PHONE@@
@@SIG_EMAIL@@
coopdescommuns.org

---

Chère amie, cher ami,

Merci encore d'avoir marqué ton intérêt pour La Coop des Communs en participant à un ou plusieurs de nos événements en 2025.

Souhaites-tu t'engager davantage en adhérant à notre association en 2026 ?

La cotisation de base est de 25 €, inchangée par rapport à 2025. Si tu peux, une cotisation de soutien de 100 € est la bienvenue ; dans ce cas, un reçu fiscal te sera délivré.

Voici le lien pour payer via Hello Asso :
https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026

En cas d'impossibilité, tu peux aussi envoyer un chèque à La Coop des Communs,
20 rue du Cdt Mouchotte – 75014 PARIS
(merci d'éviter si tu peux).

Notre dernière Newsletter (https://coopdescommuns.org/fr/newsletter-29/) te donne nos actualités et celles des groupes de travail. Ces groupes constituent notre richesse, là où s'exercent les regards croisés entre communs et ESS, d'horizons et de disciplines diversifiés, et où naissent nos projets et programmes d'action-recherche associant praticiens et chercheurs.

Retrouve la description des groupes de travail sur https://coopdescommuns.org/, à la rubrique « Nos groupes de travail en action », et les dernières actualités des groupes ici :
https://coopdescommuns.org/fr/actus-groupes-travail/

Nous prévoyons une première assemblée générale le 12 juin prochain après-midi et une petite fête pour nos 10 ans le 13 juin. Prévoyez votre journée ! Et d'autres événements à venir.

L'entretien et l'animation de notre communauté décloisonnée sont l'un de nos enjeux essentiels. À cette fin, la manifestation d'intérêt que représente l'adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.

Merci d'avance. Comme tu le sais, le collectif dépend aussi de chacun de nous.

Bien cordialement,

@@SIG_NAME@@
@@SIG_ROLE@@
@@SIG_PHONE@@
@@SIG_EMAIL@@
coopdescommuns.org
""",
        "body_html": """<html>
<head></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="padding: 15px; margin-bottom: 25px;">
        <p style="margin: 0 0 10px 0;"><strong>Chère amie, cher ami,</strong></p>
        <p style="margin: 0 0 10px 0;"><strong>Petit message de précision :</strong><br>
        le mail que tu as reçu récemment concernant le renouvellement de l'adhésion à La Coop des Communs a été envoyé par erreur depuis une mauvaise adresse mail.</p>
        <p style="margin: 0 0 10px 0;">👉 <strong>Ce message n'est pas un spam</strong> : il s'agit bien d'une communication officielle de l'association.<br>
        Toutes nos excuses pour cette confusion.</p>
        <p style="margin: 0 0 10px 0;">Je me permets donc de te renvoyer ci-dessous le message initial depuis la bonne adresse.</p>
        <p style="margin: 0 0 10px 0;">👉 <strong>Lien d'adhésion 2026 :</strong> <a href="https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026">https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026</a></p>
        <p style="margin: 15px 0 0 0;">Merci pour ta compréhension et pour ton soutien fidèle à La Coop des Communs 🌱</p>
    </div>
    
    <p style="margin-bottom: 15px;">Bien cordialement,</p>
    
    <table width="400" cellspacing="0" cellpadding="0" border="0" style="margin-top: 20px;">
        <tr>
            <td width="124" valign="top" style="padding:0cm 7.5pt 0cm 0cm">
                <img width="85" height="69" src="cid:logo" style="width:.8854in;height:.7187in">
            </td>
            <td style="padding:0cm 0cm 0cm 0cm">
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <b><span style="font-size:9pt;font-family:Poppins;color:#4B4B4D">@@SIG_NAME@@</span></b>
                    <span style="font-size:9pt;font-family:Poppins"><br>
                    <span style="color:#3CB1D4">@@SIG_ROLE@@</span></span>
                </p>
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <span style="font-size:9pt;font-family:Poppins">@@SIG_PHONE@@<br>
                    <a href="mailto:@@SIG_EMAIL@@"><span style="color:#4B4B4D">@@SIG_EMAIL@@</span></a><br>
                    <a href="https://coopdescommuns.org/"><span style="color:#4B4B4D">coopdescommuns.org</span></a></span>
                </p>
            </td>
        </tr>
    </table>
    
    <hr style="border: none; border-top: 2px solid #ddd; margin: 30px 0;">
    
    <p>Chère amie, cher ami,</p>
    <p>Merci encore d'avoir marqué ton intérêt pour La Coop des Communs en participant à un ou plusieurs de nos événements en 2025.</p>
    <p>Souhaites-tu t'engager davantage en adhérant à notre association en 2026 ?</p>
    <p>La cotisation de base est de <strong>25 €</strong>, inchangée par rapport à 2025. Si tu peux, une cotisation de soutien de <strong>100 €</strong> est la bienvenue ; dans ce cas, un reçu fiscal te sera délivré.</p>
    <p style="margin-top: 25px;">
        <a href="https://www.helloasso.com/associations/la-coop-des-communs/adhesions/adhesion-annee-2026" 
           style="background-color: #2c5aa0; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
            Adhérer pour 2026 via Hello Asso
        </a>
    </p>
    <p style="font-size: 0.9em; color: #666;">En cas d'impossibilité, tu peux aussi envoyer un chèque à La Coop des Communs,<br>
    20 rue du Cdt Mouchotte – 75014 PARIS<br>
    (merci d'éviter si tu peux).</p>
    
    <p>Notre <a href="https://coopdescommuns.org/fr/newsletter-29/">dernière Newsletter</a> te donne nos actualités et celles des groupes de travail. Ces groupes constituent notre richesse, là où s'exercent les regards croisés entre communs et ESS, d'horizons et de disciplines diversifiés, et où naissent nos projets et programmes d'action-recherche associant praticiens et chercheurs.</p>
    
    <p>Retrouve la description des groupes de travail sur <a href="https://coopdescommuns.org/">https://coopdescommuns.org/</a>, à la rubrique « Nos groupes de travail en action », et les dernières actualités des groupes ici :<br>
    <a href="https://coopdescommuns.org/fr/actus-groupes-travail/">https://coopdescommuns.org/fr/actus-groupes-travail/</a></p>
    
    <p>Nous prévoyons une première <strong>assemblée générale le 12 juin prochain après-midi</strong> et une petite fête pour nos <strong>10 ans le 13 juin</strong>. Prévoyez votre journée ! Et d'autres événements à venir.</p>
    
    <p>L'entretien et l'animation de notre communauté décloisonnée sont l'un de nos enjeux essentiels. À cette fin, la manifestation d'intérêt que représente l'adhésion compte, pour donner du cœur à l'action collective et pour conforter nos demandes de soutiens extérieurs.</p>
    
    <p>Merci d'avance. Comme tu le sais, le collectif dépend aussi de chacun de nous.</p>
    
    <p style="margin-top: 30px;">Bien cordialement,</p>
    
    <table width="400" cellspacing="0" cellpadding="0" border="0" style="margin-top: 20px;">
        <tr>
            <td width="124" valign="top" style="padding:0cm 7.5pt 0cm 0cm">
                <img width="85" height="69" src="cid:logo" style="width:.8854in;height:.7187in">
            </td>
            <td style="padding:0cm 0cm 0cm 0cm">
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <b><span style="font-size:9pt;font-family:Poppins;color:#4B4B4D">@@SIG_NAME@@</span></b>
                    <span style="font-size:9pt;font-family:Poppins"><br>
                    <span style="color:#3CB1D4">@@SIG_ROLE@@</span></span>
                </p>
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <span style="font-size:9pt;font-family:Poppins">@@SIG_PHONE@@<br>
                    <a href="mailto:@@SIG_EMAIL@@"><span style="color:#4B4B4D">@@SIG_EMAIL@@</span></a><br>
                    <a href="https://coopdescommuns.org/"><span style="color:#4B4B4D">coopdescommuns.org</span></a></span>
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    },

    "10 ans intervenants": {
        "subject": "INVITATION La Coop des Communs a 10 ans cette année !",
        "attachments": ["🎉 INVITATION La Coop des Communs a 10 ans cette année.pdf"],
        "body_text": """Cher.e ami.e,

La Coop des Communs a dix ans cette année. Pour cet anniversaire, nous organisons un moment de convivialité et de célébration le samedi 13 juin prochain, de 11h30 à 16h au Jardin d'agronomie tropicale de Paris.

Tu as joué un rôle éminent/crucial/important dans cette aventure. Je serais, nous serions toutes et tous heureux de t'y accueillir et partager ce temps avec toi. Tu peux t'inscrire dès à présent à ce lien :
https://airtable.com/appTB6ISLjbexWWIM/shryuemN81hLf3srn

Plus, nous aimerions avoir ton témoignage, sur place si tu peux te joindre, sinon par vidéo, voire par écrit. En sus du plaisir du partage, nous ferons un récit, une base de connaissance de tout cela.

Si tu as des photos, des documents écrits à partager, merci de les apporter.

D'avance, je te remercie de ta réponse.

Bien cordialement,

@@SIG_NAME@@
@@SIG_ROLE@@
@@SIG_PHONE@@
@@SIG_EMAIL@@
coopdescommuns.org
""",
        "body_html": """<html>
<head></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <p>Cher.e ami.e,</p>

    <p>La Coop des Communs a <strong>dix ans</strong> cette année. Pour cet anniversaire, nous organisons un moment de convivialité et de célébration le <strong>samedi 13 juin prochain, de 11h30 à 16h</strong> au <strong>Jardin d'agronomie tropicale de Paris</strong>.</p>

    <p>Tu as joué un rôle éminent/crucial/important dans cette aventure. Je serais, nous serions toutes et tous heureux de t'y accueillir et partager ce temps avec toi. Tu peux t'inscrire dès à présent à ce lien :</p>

    <p style="margin-top: 20px;">
        <a href="https://airtable.com/appTB6ISLjbexWWIM/shryuemN81hLf3srn"
           style="background-color: #2c5aa0; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
            S'inscrire à l'événement
        </a>
    </p>

    <p>Plus, nous aimerions avoir ton témoignage, sur place si tu peux te joindre, sinon par vidéo, voire par écrit. En sus du plaisir du partage, nous ferons un récit, une base de connaissance de tout cela.</p>

    <p>Si tu as des photos, des documents écrits à partager, merci de les apporter.</p>

    <p>D'avance, je te remercie de ta réponse.</p>

    <p style="margin-top: 30px;">Bien cordialement,</p>

    <table width="400" cellspacing="0" cellpadding="0" border="0" style="margin-top: 20px;">
        <tr>
            <td width="124" valign="top" style="padding:0cm 7.5pt 0cm 0cm">
                <img width="85" height="69" src="cid:logo" style="width:.8854in;height:.7187in">
            </td>
            <td style="padding:0cm 0cm 0cm 0cm">
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <b><span style="font-size:9pt;font-family:Poppins;color:#4B4B4D">@@SIG_NAME@@</span></b>
                    <span style="font-size:9pt;font-family:Poppins"><br>
                    <span style="color:#3CB1D4">@@SIG_ROLE@@</span></span>
                </p>
                <p style="margin:0cm 0cm 3pt 2.25pt">
                    <span style="font-size:9pt;font-family:Poppins">@@SIG_PHONE@@<br>
                    <a href="mailto:@@SIG_EMAIL@@"><span style="color:#4B4B4D">@@SIG_EMAIL@@</span></a><br>
                    <a href="https://coopdescommuns.org/"><span style="color:#4B4B4D">coopdescommuns.org</span></a></span>
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    }
}
