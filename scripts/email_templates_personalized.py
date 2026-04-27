"""Templates d'emails personnalisés (avec placeholders {prenom}, etc.).

Utilisés par scripts/send_personalized_email.py.
Le rendu se fait avec str.format(**row), où `row` vient d'une ligne CSV.
"""

PERSONALIZED_EMAIL_TEMPLATES = {
    "10 ans intervenants": {
        "subject": "INVITATION La Coop des Communs a 10 ans cette année !",
        "attachments": ["🎉 INVITATION La Coop des Communs a 10 ans cette année.pdf"],
        "body_text": """{genre} {prenom},

La Coop des Communs a dix ans cette année. Pour cet anniversaire, nous organisons un moment de convivialité et de célébration le samedi 13 juin prochain, de 11h30 à 16h au Jardin d'agronomie tropicale de Paris.

Tu as joué un rôle {role} dans cette aventure. Tu trouveras ci-joint le programme de la journée. Je serais, nous serions toutes et tous heureux de t'y accueillir et partager ce temps avec toi. Tu peux t'inscrire dès à présent à ce lien :
https://airtable.com/appTB6ISLjbexWWIM/shryuemN81hLf3srn

Plus, nous aimerions avoir ton témoignage, sur place si tu peux te joindre, sinon par vidéo, voire par écrit. Tu peux me l'envoyer à cette adresse mail. En sus du plaisir du partage, nous ferons un récit, une base de connaissance de tout cela.

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
    <p>{genre} {prenom},</p>

    <p>La Coop des Communs a <strong>dix ans</strong> cette année. Pour cet anniversaire, nous organisons un moment de convivialité et de célébration le <strong>samedi 13 juin prochain, de 11h30 à 16h</strong> au <strong>Jardin d'agronomie tropicale de Paris</strong>.</p>

    <p>Tu as joué un rôle {role} dans cette aventure. Tu trouveras <strong>ci-joint le programme de la journée</strong>. Je serais, nous serions toutes et tous heureux de t'y accueillir et partager ce temps avec toi. Tu peux t'inscrire dès à présent à ce lien :</p>

    <p style="margin-top: 20px;">
        <a href="https://airtable.com/appTB6ISLjbexWWIM/shryuemN81hLf3srn"
           style="background-color: #2c5aa0; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
            S'inscrire à l'événement
        </a>
    </p>

    <p>Plus, nous aimerions avoir ton témoignage, sur place si tu peux te joindre, sinon par vidéo, voire par écrit. Tu peux me l'envoyer à cette adresse mail. En sus du plaisir du partage, nous ferons un récit, une base de connaissance de tout cela.</p>

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
