# Garde-fou d'envoi

> Hors production, ce code refuse d'écrire à une adresse qui n'est pas sur une
> liste blanche. Le refus est le comportement par défaut : il faut se déclarer
> pour envoyer, pas se déclarer pour ne pas envoyer.

## Pourquoi

L'annuaire porte plus de mille fiches. Un script de campagne lancé une fois de
trop, un inventaire de développement qui pointe encore sur les données de
production, et l'erreur n'est pas rattrapable : un mail parti est parti.

La parade évidente — écrire la consigne quelque part — ne tient pas. C'est
mesuré sur ce projet : la consigne « mettre le curseur à la bonne date avant le
déploiement », posée en avril 2026 dans les variables de déploiement, aurait
renvoyé un mail de bienvenue à tous les adhérents depuis avril si le playbook
n'avait pas été corrigé quatre mois plus tard. Personne ne l'avait relue.

D'où une ceinture plutôt qu'une consigne.

## Les deux variables

| Variable | Rôle |
|---|---|
| `ENVIRONNEMENT` | La vanne. Vaut `production` (casse et espaces indifférentes) ou n'importe quoi d'autre. |
| `DESTINATAIRES_AUTORISES` | La liste blanche du bac à sable, séparée par des virgules. Ignorée en production. |

Deux formes de motif :

- une adresse exacte : `hugo@dsi.coop`
- un domaine entier : `*@dsi.coop`

Les motifs qui ouvriraient la vanne en grand (`*`, `*@*`, `*@fr`) sont **ignorés
avec une erreur en syslog** : sans ça, désarmer la ceinture tiendrait en un
caractère, et quelqu'un finirait par l'écrire un soir pour débloquer un envoi.
Le seul moyen de sortir du bac à sable reste `ENVIRONNEMENT=production`, qui se
voit dans un inventaire et se relit en revue.

## Ce que ça donne

```
ENVIRONNEMENT absent        → aucun mail ne part, quel que soit le destinataire
ENVIRONNEMENT=bac-a-sable   → seules les adresses de DESTINATAIRES_AUTORISES
DESTINATAIRES_AUTORISES vide  sont joignables ; les autres sont refusées
ENVIRONNEMENT=production    → tout part normalement
```

Trois points de conception qui expliquent des comportements surprenants :

1. **Le défaut est le refus.** Une machine fraîche, un conteneur de CI, un poste
   de développement n'ont rien à poser pour être sûrs. C'est la production qui
   doit se déclarer, et elle le fait une fois, par le playbook.
2. **Le garde-fou passe avant le `dry_run`.** Une ceinture qui se relâche en
   simulation apprend au développeur que « ça marche », et l'envoi réel part
   ensuite dans le mur. Un `--dry-run` bute donc sur le refus tout de suite.
3. **`cc` et `bcc` sont contrôlés comme `to`.** Un `bcc` non contrôlé serait une
   porte ouverte.

Un envoi refusé fait retourner `False` à `send_email` et écrit la raison en
syslog, avec les trois premières adresses fautives et le nombre total.

## Où c'est posé

- **Le code** : `src/garde_fou_envoi.py`, appelé en tête de
  `OVHEmailClient.send_email` — seul endroit du dépôt qui ouvre une connexion
  SMTP. Le placer plus haut obligerait chaque nouveau script à y penser, et
  c'est exactement ce qui ne tient pas.
- **Le déploiement** : `app_garde_fou` dans les variables d'inventaire, versé au
  `.env` par le même canal que la signature. Le playbook **refuse de déployer**
  un inventaire qui ne déclare pas `ENVIRONNEMENT` : l'oubli produirait une
  production muette, et un silence ne se remarque pas.
- **Les tests** : `tests/conftest.py` force l'environnement à `tests` et n'ouvre
  la liste blanche qu'aux domaines de fiction. Le garde-fou est donc *exercé*
  par toute la suite au lieu d'être neutralisé, et un test qui écrirait à une
  adresse d'adhérent échouerait.

## Travailler avec

**Envoyer un mail de test depuis le poste** — rien à faire, le `.env` local
déclare déjà un environnement de bac à sable ouvert sur votre domaine.

**Lancer une vraie campagne depuis le poste** — passer `ENVIRONNEMENT` à
`production` dans le `.env` le temps de l'envoi, puis le remettre. C'est le
geste délibéré que le garde-fou exige, et il doit rester délibéré.

**Ajouter une adresse de test** — l'ajouter à `DESTINATAIRES_AUTORISES`, pas
contourner le garde-fou.

## Le prouver

C'est la vérification qui compte, et elle est falsifiable : tenter un envoi hors
liste blanche et constater le refus.

```bash
cd api_automation_toolbox
ENVIRONNEMENT=bac-a-sable DESTINATAIRES_AUTORISES='*@dsi.coop' \
  .venv/bin/python -c "
from src.clients.ovh_email_client import OVHEmailClient
c = OVHEmailClient(smtp_host='x', smtp_user='y', smtp_password='z')
print('hors liste :', c.send_email(sender='a@b.fr', to=['inconnu@ailleurs.fr'],
                                   subject='t', body_text='t'))
print('sur liste  :', c.send_email(sender='a@b.fr', to=['hugo@dsi.coop'],
                                   subject='t', body_text='t', dry_run=True))
"
```

Attendu : `hors liste : False`, `sur liste : True`.

Les tests couvrent la même propriété : `tests/test_garde_fou_envoi.py`.
