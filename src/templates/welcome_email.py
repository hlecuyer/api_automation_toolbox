"""Template du mail de bienvenue envoyé à chaque nouvelle adhésion Hello Asso.

Personnalisable par prénom via `{first_name}`. La signature est identique à celle
de `scripts/email_templates.py` : elle porte des données personnelles, donc elle
vient de l'environnement via `signature`, pas du code. Le logo est embarqué via
`cid:logo` (à passer en `inline_images` à OVHEmailClient.send_email).
"""

from pathlib import Path

from src.templates import signature

LOGO_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data" / "image.png"

SUBJECT = "Bienvenue à La Coop des Communs !"

BODY_TEXT = """Bonjour {first_name},

Merci d'apporter ton soutien à La Coop des Communs en ayant adhéré ou réadhéré pour l'année 2026.

C'est une chance pour nous.


À NOTER DANS TON AGENDA
- 12 juin (après-midi) — Assemblée générale
- 13 juin (journée)    — Nos 10 ans, en présence à Paris


QUELQUES INFOS UTILES

- Des visios d'accueil sont prévues pour les nouveaux adhérents :
  vous recevrez une invitation après adhésion. Au plaisir de vous retrouver !

- La Newsletter de l'association est envoyée à tous les membres.

- Sauf avis contraire, nous vous inscrivons sur la liste d'échanges
  ess-communs, qui diffuse au fil de l'eau des informations à la croisée
  des communs et de l'ESS. Si vous avez utilisé plusieurs adresses,
  l'équipe DSI.coop vous contactera pour n'en garder qu'une.

- Les groupes de travail vous sont ouverts. Si l'un d'eux vous motive,
  dites-le — un·e animateur·ice vous briefera et vous accueillera.


POUR ALLER PLUS LOIN

- Découvrir les groupes de travail :
  https://coopdescommuns.org/

- Lire les dernières actus des GT :
  https://coopdescommuns.org/fr/actus-groupes-travail/

- Participer à un GT — vade-mecum :
  https://contribuer.coopdescommuns.org/gouvernance/les-groupes-de-travail/participer-a-un-groupe-de-travail


L'équipe DSI peut répondre à vos questions (mails, accès aux ressources, formations à nos outils collaboratifs deux fois par an avec le soutien du Fonds de développement de la vie associative). N'hésitez pas à écrire à contact@dsi.coop.


Bien cordialement,

@@SIG_NAME@@
@@SIG_ROLE@@
@@SIG_PHONE@@
@@SIG_EMAIL@@
coopdescommuns.org
"""

BODY_HTML = """<html>
<head>
<meta charset="UTF-8">
</head>
<body style="margin:0; padding:0; background-color:#f5f7f9; font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333;">
    <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f5f7f9; padding: 24px 0;">
        <tr>
            <td align="center">
                <table width="600" cellspacing="0" cellpadding="0" border="0" style="background-color:#ffffff; border-radius: 8px; max-width: 600px; width: 100%;">
                    <tr>
                        <td style="padding: 32px 32px 8px 32px;">
                            <h1 style="margin:0 0 8px 0; font-size: 22px; color:#3CB1D4;">Bienvenue, {first_name} !</h1>
                            <p style="margin: 0 0 12px 0;">Merci d'apporter ton soutien à <strong>La Coop des Communs</strong> en ayant adhéré ou réadhéré pour l'année 2026.</p>
                            <p style="margin: 0;">C'est une chance pour nous.</p>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 16px 32px 0 32px;">
                            <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#eef9fc; border-left: 4px solid #3CB1D4; border-radius: 4px;">
                                <tr>
                                    <td style="padding: 14px 18px;">
                                        <p style="margin:0 0 6px 0; font-weight: bold; color:#3CB1D4;">À noter dans ton agenda</p>
                                        <p style="margin:0;"><strong>12 juin après-midi</strong> — Assemblée générale<br>
                                        <strong>13 juin (journée)</strong> — Nos 10 ans, en présence à Paris</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 24px 32px 0 32px;">
                            <h2 style="margin:0 0 8px 0; font-size: 16px; color:#4B4B4D;">Quelques infos utiles</h2>
                            <ul style="margin: 0 0 0 18px; padding: 0;">
                                <li style="margin-bottom: 8px;">Des <strong>visios d'accueil</strong> sont prévues pour les nouveaux adhérents : vous recevrez une invitation après adhésion. Au plaisir de vous retrouver !</li>
                                <li style="margin-bottom: 8px;">La <strong>Newsletter</strong> de l'association est envoyée à tous les membres.</li>
                                <li style="margin-bottom: 8px;">Sauf avis contraire, nous vous inscrivons sur la liste d'échanges <em>ess-communs</em>, qui diffuse au fil de l'eau des informations à la croisée des communs et de l'ESS. Si vous avez utilisé plusieurs adresses, l'équipe <a href="https://dsi.coop" style="color:#3CB1D4;">DSI.coop</a> vous contactera pour n'en garder qu'une.</li>
                                <li style="margin-bottom: 0;">Les <strong>groupes de travail</strong> vous sont ouverts. Si l'un d'eux vous motive, dites-le — un·e animateur·ice vous briefera et vous accueillera.</li>
                            </ul>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 24px 32px 0 32px;">
                            <h2 style="margin:0 0 12px 0; font-size: 16px; color:#4B4B4D;">Pour aller plus loin</h2>

                            <table cellspacing="0" cellpadding="0" border="0" style="margin: 0 0 10px 0;">
                                <tr>
                                    <td style="background-color:#3CB1D4; border-radius: 4px;">
                                        <a href="https://coopdescommuns.org/" style="display: inline-block; padding: 11px 22px; color:#ffffff; text-decoration: none; font-weight: bold; font-size: 14px;">Découvrir les groupes de travail</a>
                                    </td>
                                </tr>
                            </table>

                            <table cellspacing="0" cellpadding="0" border="0" style="margin: 0 0 10px 0;">
                                <tr>
                                    <td style="background-color:#ffffff; border: 1px solid #3CB1D4; border-radius: 4px;">
                                        <a href="https://coopdescommuns.org/fr/actus-groupes-travail/" style="display: inline-block; padding: 10px 22px; color:#3CB1D4; text-decoration: none; font-weight: bold; font-size: 14px;">Lire les dernières actus des GT</a>
                                    </td>
                                </tr>
                            </table>

                            <table cellspacing="0" cellpadding="0" border="0" style="margin: 0;">
                                <tr>
                                    <td style="background-color:#ffffff; border: 1px solid #3CB1D4; border-radius: 4px;">
                                        <a href="https://contribuer.coopdescommuns.org/gouvernance/les-groupes-de-travail/participer-a-un-groupe-de-travail" style="display: inline-block; padding: 10px 22px; color:#3CB1D4; text-decoration: none; font-weight: bold; font-size: 14px;">Participer à un GT — vade-mecum</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 24px 32px 0 32px;">
                            <p style="margin: 0; font-size: 14px; color:#666;">L'équipe DSI peut répondre à vos questions (mails, accès aux ressources, formations à nos outils collaboratifs deux fois par an avec le soutien du Fonds de développement de la vie associative). N'hésitez pas à écrire à <a href="mailto:contact@dsi.coop" style="color:#3CB1D4;">contact@dsi.coop</a>.</p>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 28px 32px 8px 32px;">
                            <p style="margin: 0;">Bien cordialement,</p>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 8px 32px 32px 32px;">
                            <table cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td valign="top" style="padding-right: 12px;">
                                        <img width="85" height="69" src="cid:logo" alt="La Coop des Communs" style="display:block;">
                                    </td>
                                    <td valign="top">
                                        <p style="margin:0;">
                                            <strong style="font-size:13px; color:#4B4B4D;">@@SIG_NAME@@</strong><br>
                                            <span style="color:#3CB1D4; font-size:12px;">@@SIG_ROLE@@</span>
                                        </p>
                                        <p style="margin: 4px 0 0 0; font-size:12px;">@@SIG_PHONE@@<br>
                                            <a href="mailto:@@SIG_EMAIL@@" style="color:#4B4B4D;">@@SIG_EMAIL@@</a><br>
                                            <a href="https://coopdescommuns.org/" style="color:#4B4B4D;">coopdescommuns.org</a>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def render(first_name: str) -> tuple[str, str]:
    """Render the welcome email body for a given first name.

    Returns:
        (body_text, body_html) tuple with `{first_name}` substituted.
    """
    safe_name = (first_name or "").strip() or "à toi"
    # La signature est substituée APRÈS le `.format()`, et non avant : dans l'autre
    # ordre, une accolade dans une valeur de signature (un nom entre parenthèses
    # typographiques, une fonction entre crochets) est vue par `.format()` comme un
    # champ à remplacer et lève `KeyError` — le mail de bienvenue ne part pas et
    # l'adhésion échoue. Les sentinelles ne contiennent pas d'accolade, elles
    # traversent donc `.format()` intactes.
    return (
        signature.appliquer(BODY_TEXT.format(first_name=safe_name)),
        signature.appliquer(BODY_HTML.format(first_name=safe_name)),
    )
