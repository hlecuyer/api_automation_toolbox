# Scripts de Synchronisation HelloAsso

## 📋 Modes Disponibles

### 1. 🧪 **Full Dry Run** (Rien n'est modifié) - `dry_run="full"`
```bash
python scripts/test_sync_dry_run.py
```

**Ce qui se passe :**
- ✅ Récupère les données depuis HelloAsso
- ❌ N'écrit PAS dans Airtable (simulation)
- ❌ N'ajoute PAS à la mailing list OVH (simulation)
- ❌ N'envoie PAS d'emails (simulation)
- ❌ Ne met PAS à jour la date `subscription_after`

**Utilisation :** Test complet sans aucune modification


### 2. � **Only Airtable** (Airtable seulement) - `dry_run="only_airtable"`
```bash
python scripts/test_sync_only_airtable.py
```

**Ce qui se passe :**
- ✅ Récupère les données depuis HelloAsso
- ✅ Écrit dans Airtable (**RÉEL**)
- ❌ N'ajoute PAS à la mailing list OVH (désactivé)
- ❌ N'envoie PAS d'emails (désactivé)
- ❌ Ne met PAS à jour la date `subscription_after`

**Utilisation :** Mise à jour Airtable uniquement (utile pour tester ou récupérer des données)


### 3. 📧 **Dry Run Emails** (Tout sauf les emails) - `dry_run="only_mail"`
```bash
python scripts/test_sync_no_email.py
```

**Ce qui se passe :**
- ✅ Récupère les données depuis HelloAsso
- ✅ Écrit dans Airtable (**RÉEL**)
- ✅ Ajoute à la mailing list OVH (**RÉEL**)
- ❌ N'envoie PAS d'emails (désactivé)
- ❌ Ne met PAS à jour la date `subscription_after`

**Utilisation :** Synchronisation réelle mais sans envoyer d'emails aux adhérents


### 4. 🚀 **Mode Production** (Tout est réel) - `dry_run=None`
```bash
python src/hello_asso_sync.py --conf config/hello-asso-automation-conf.json
```

**Ce qui se passe :**
- ✅ Récupère les données depuis HelloAsso
- ✅ Écrit dans Airtable (**RÉEL**)
- ✅ Ajoute à la mailing list OVH (**RÉEL**)
- ✅ Envoie des emails de confirmation (**RÉEL**)
- ✅ Met à jour la date `subscription_after` dans le fichier de config

**Utilisation :** Synchronisation complète en production

---

## 🔒 Sécurité

**Important :** 
- Le script `test_sync_no_email.py` demande confirmation avant d'exécuter
- En mode production, la date `subscription_after` est mise à jour pour éviter de synchroniser plusieurs fois les mêmes adhérents
- Les credentials sensibles (mots de passe, tokens) doivent être dans `.env`, pas dans le fichier de config JSON

## 📝 Configuration

Les paramètres SMTP doivent être dans `.env` :
```bash
SMTP_HOST=ssl0.ovh.net
SMTP_PORT=587
SMTP_USER=votre-email@domain.org
SMTP_PASSWORD=votre-mot-de-passe
```

## 🐛 Debug

Pour voir les logs système :
```bash
sudo tail -f /var/log/syslog | grep hello_asso
```
