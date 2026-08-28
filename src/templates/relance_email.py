"""Le rappel envoyé à un adhérent qui n'a pas mis sa fiche à jour.

Court, et il ne demande qu'une chose. Le mail de bienvenue portait déjà le lien
au milieu de dix autres informations ; si l'adhérent n'a pas cliqué, en
réexpliquer davantage ne servira à rien.

Le lien est obligatoire : un rappel sans lien n'a aucun objet. `render` le
demande donc en argument positionnel, il ne peut pas être oublié.

Le texte ne change pas d'un palier à l'autre. Dire « c'est la troisième fois que
nous vous écrivons » ne rend le message ni plus clair ni plus agréable à
recevoir.
"""

from src.templates import signature

SUBJECT = "Vos informations à la Coop des Communs"

BODY_TEXT = """Bonjour {prenom},

Un rappel rapide : vos informations dans l'annuaire de La Coop des Communs
attendent d'être vérifiées.

Le formulaire est déjà rempli avec ce que nous savons de vous, il n'y a
qu'à corriger ce qui a changé :
{lien}

Si tout est à jour, validez simplement le formulaire : nous saurons ainsi
qu'il n'y a rien à modifier, et vous ne recevrez plus ce rappel.


Bien cordialement,

@@SIG_NAME@@
@@SIG_ROLE@@
@@SIG_PHONE@@
@@SIG_EMAIL@@
coopdescommuns.org
"""

BODY_HTML = """<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0; padding:0; background-color:#f5f7f9; font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333;">
    <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f5f7f9; padding: 24px 0;">
        <tr>
            <td align="center">
                <table width="600" cellspacing="0" cellpadding="0" border="0" style="background-color:#ffffff; border-radius: 8px; max-width: 600px; width: 100%;">
                    <tr>
                        <td style="padding: 32px 32px 8px 32px;">
                            <h1 style="margin:0 0 8px 0; font-size: 20px; color:#3CB1D4;">Bonjour {prenom},</h1>
                            <p style="margin: 0 0 12px 0;">Un rappel rapide : vos informations dans l'annuaire de <strong>La Coop des Communs</strong> attendent d'être vérifiées.</p>
                            <p style="margin: 0;">Le formulaire est déjà rempli avec ce que nous savons de vous, il n'y a qu'à corriger ce qui a changé.</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 32px 0 32px;" align="center">
                            <a href="{lien}" style="display:inline-block; padding: 12px 24px; background-color:#3CB1D4; color:#ffffff; text-decoration:none; border-radius: 4px; font-weight: bold;">Vérifier mes informations</a>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 32px 0 32px;">
                            <p style="margin: 0; color:#666; font-size: 14px;">Si tout est à jour, validez simplement le formulaire : nous saurons ainsi qu'il n'y a rien à modifier, et vous ne recevrez plus ce rappel.</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 24px 32px 32px 32px; color:#666; font-size: 14px;">
                            <p style="margin:0;">Bien cordialement,<br>
                            @@SIG_NAME@@<br>
                            @@SIG_ROLE@@<br>
                            @@SIG_PHONE@@<br>
                            <a href="mailto:@@SIG_EMAIL@@" style="color:#3CB1D4;">@@SIG_EMAIL@@</a><br>
                            <a href="https://coopdescommuns.org" style="color:#3CB1D4;">coopdescommuns.org</a></p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def render(lien: str, prenom: str = None) -> tuple[str, str]:
    """Le corps du rappel, en texte et en HTML.

    La signature est substituée **après** le `.format()`, comme dans le mail de
    bienvenue et pour la même raison : une accolade dans une valeur de signature
    serait vue par `.format()` comme un champ à remplacer, et le mail ne partirait
    pas.
    """
    prenom = (prenom or "").strip() or "à vous"
    return (
        signature.appliquer(BODY_TEXT.format(prenom=prenom, lien=lien)),
        signature.appliquer(BODY_HTML.format(prenom=prenom, lien=lien)),
    )
