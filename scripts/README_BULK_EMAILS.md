# Script d'envoi d'emails groupés

Ce script permet d'envoyer des emails personnalisés à différentes catégories de destinataires à partir d'un fichier CSV.

## 📋 Structure du CSV

Le CSV doit avoir 4 colonnes représentant 4 catégories :
- `Adherent 2025` : Adhérents de 2025
- `Adherent 2024` : Adhérents de 2024
- `GT non adherent` : Participants aux Groupes de Travail (non adhérents)
- `Evenement non adherent` : Participants à des événements (non adhérents)

Chaque catégorie recevra un message différent adapté à son statut.

## ⚙️ Configuration

Les credentials SMTP doivent être dans votre fichier `.env` :

```bash
SMTP_HOST=ssl0.ovh.net
SMTP_PORT=587
SMTP_USER=contact@coopdescommuns.org
SMTP_PASSWORD=votre_mot_de_passe
```

## 🧪 Mode Test

Pour tester l'envoi des 4 types de mails sur une seule adresse :

```bash
python scripts/send_bulk_emails.py \
  --csv "scripts/data/Liste mail non envoye adhésion 2026-VV.csv" \
  --test votre.email@example.com
```

Cela enverra les 4 types de mails à l'adresse spécifiée, avec un tag `[TEST]` dans le sujet.

## 🔥 Mode Production

### Dry-run (simulation sans envoi réel)

```bash
python scripts/send_bulk_emails.py \
  --csv "scripts/data/Liste mail non envoye adhésion 2026-VV.csv" \
  --dry-run
```

### Envoi réel

```bash
python scripts/send_bulk_emails.py \
  --csv "scripts/data/Liste mail non envoye adhésion 2026-VV.csv"
```

⚠️ Une confirmation sera demandée avant l'envoi réel.

## 📝 Options disponibles

| Option | Description | Par défaut |
|--------|-------------|------------|
| `--csv` | Chemin vers le fichier CSV | **Obligatoire** |
| `--test EMAIL` | Mode test : envoie les 4 mails à cette adresse | - |
| `--dry-run` | Simule l'envoi sans envoyer | `False` |
| `--sender` | Adresse de l'expéditeur | `SMTP_USER` |
| `--smtp-host` | Serveur SMTP | `SMTP_HOST` |
| `--smtp-port` | Port SMTP | `SMTP_PORT` |
| `--smtp-user` | Utilisateur SMTP | `SMTP_USER` |
| `--smtp-password` | Mot de passe SMTP | `SMTP_PASSWORD` |
| `--delay` | Délai entre emails (secondes) | `0.5` |

## 📧 Templates de mails

Les 4 templates sont définis dans `scripts/email_templates.py` et peuvent être personnalisés :

1. **Adherent 2025** : Message de remerciement et invitation au renouvellement
2. **Adherent 2024** : Rappel et invitation à renouveler
3. **GT non adherent** : Invitation à adhérer (participants aux GT)
4. **Evenement non adherent** : Invitation à adhérer (participants événements)

Chaque template contient :
- Un sujet personnalisé
- Un corps en texte brut
- Un corps HTML avec bouton d'appel à l'action

## 🔍 Exemples

### Test avec dry-run
```bash
python scripts/send_bulk_emails.py \
  --csv "scripts/data/Liste mail non envoye adhésion 2026-VV.csv" \
  --test test@example.com \
  --dry-run
```

### Envoi réel avec délai personnalisé
```bash
python scripts/send_bulk_emails.py \
  --csv "scripts/data/Liste mail non envoye adhésion 2026-VV.csv" \
  --delay 1.0
```

### Utiliser un expéditeur différent
```bash
python scripts/send_bulk_emails.py \
  --csv "scripts/data/Liste mail non envoye adhésion 2026-VV.csv" \
  --sender autre@coopdescommuns.org \
  --smtp-user autre@coopdescommuns.org \
  --smtp-password "mot_de_passe"
```

## 📊 Statistiques

Le script affiche :
- Nombre d'emails par catégorie
- Total d'emails à envoyer
- Progression en temps réel
- Résumé avec nombre d'envois réussis et d'erreurs

## ⚠️ Sécurité

- Ne commitez **jamais** votre fichier `.env` avec les credentials
- Le fichier CSV avec les vraies adresses emails ne doit pas être committé
- Utilisez toujours le mode test avant un envoi en production
- Le délai entre emails évite de surcharger le serveur SMTP
