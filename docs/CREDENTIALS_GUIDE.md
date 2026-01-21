# Guide : Gestion Sécurisée des Credentials

## 🔐 Principe

**Séparation des responsabilités :**
- 🔒 **Credentials sensibles** → fichier `.env` (ignoré par git)
- ⚙️ **Configuration non-sensible** → fichier JSON (peut être versionné)

---

## 📋 Configuration Initiale

### 1. Créer le fichier `.env` avec vos credentials

```bash
cp .env.example .env
```

Éditez `.env` avec vos **vraies credentials** :

```env
# HelloAsso API Credentials
HELLOASSO_CLIENT_ID=votre_vrai_client_id
HELLOASSO_CLIENT_SECRET=votre_vrai_client_secret

# OVH API Credentials
OVH_ENDPOINT=ovh-eu
OVH_APP_KEY=votre_app_key
OVH_APP_SECRET=votre_app_secret
OVH_CONSUMER_KEY=votre_consumer_key
```

### 2. Créer le fichier de configuration JSON (sans credentials)

```bash
cp hello-asso-automation-conf.json.example hello-asso-automation-conf.json
```

Le fichier JSON contient **uniquement** la configuration non-sensible :

```json
{
  "conf": {
    "helloAsso": {
      "api_url": "https://api.helloasso.com",
      "organization_name": "votre-organisation",
      "form_name": "Votre Formulaire",
      "subscription_after": "2025-01-01T00:00:00",
      "first_sub_field": "champ_premiere_adhesion",
      "name_field": "Nom"
    },
    "cotisation_label": "Payé 2025",
    "groupe": "Membres",
    "webhook_url": "https://hooks.zapier.com/...",
    "ovh": {
      "mailing_list": {
        "name": "membres",
        "domain": "votredomain.org"
      }
    }
  }
}
```

**⚠️ Important :** Le JSON ne doit **PAS** contenir de section `credentials` !

---

## 🚀 Utilisation

```python
from hello_asso_sync import SyncHelloAsso

# Le fichier JSON est requis, les credentials viennent de .env
sync = SyncHelloAsso("hello-asso-automation-conf.json")
sync.run()
```

**Flux de chargement :**
1. 📄 Charge la configuration depuis le JSON
2. 🔐 Injecte les credentials depuis `.env`
3. ✅ Valide que tout est présent

---

## 📁 Structure des Fichiers

```
├── .env                          # ❌ Git ignoré - VOS credentials
├── .env.example                  # ✅ Git versionné - Template
├── hello-asso-automation-conf.json  # ❌ Git ignoré - VOTRE config
├── hello-asso-automation-conf.json.example  # ✅ Git versionné - Template
└── config_loader.py              # ✅ Module de chargement
```

---

## 🔄 Migration depuis l'ancien système

Si vous aviez un fichier JSON avec credentials :

### Étape 1 : Extraire les credentials

Ouvrez votre ancien `hello-asso-automation-conf.json` et copiez :

```json
"credentials": {
  "helloAsso": {
    "id": "xxx",
    "secret": "yyy"
  },
  "ovh": {
    "endpoint": "ovh-eu",
    "ak": "aaa",
    "as": "bbb",
    "ck": "ccc"
  }
}
```

### Étape 2 : Les mettre dans `.env`

```env
HELLOASSO_CLIENT_ID=xxx
HELLOASSO_CLIENT_SECRET=yyy
OVH_ENDPOINT=ovh-eu
OVH_APP_KEY=aaa
OVH_APP_SECRET=bbb
OVH_CONSUMER_KEY=ccc
```

### Étape 3 : Supprimer la section `credentials` du JSON

Éditez votre JSON et **supprimez complètement** la section `credentials`.

Gardez uniquement la section `conf`.

---

## 🧪 Tests

### Tests Unitaires

Les tests utilisent des mocks, pas besoin de `.env` :

```bash
pytest test_hello_asso_sync.py -v
```

### Tests Fonctionnels

Créez un `.env` avec vos vraies credentials :

```bash
pytest test_hello_asso_sync_functional.py -v -s
```

---

## 🛡️ Sécurité

### ✅ Fichiers versionnés (sans credentials)

- `.env.example` - template vide
- `hello-asso-automation-conf.json.example` - exemple de config
- `config_loader.py` - code de chargement

### ❌ Fichiers ignorés par git (avec vos données)

- `.env` - vos credentials
- `hello-asso-automation-conf.json` - votre config
- `hello-asso-automation-conf-test.json` - config de test

### Vérification

```bash
# Ces fichiers ne doivent PAS apparaître
git status

# Doit afficher (si déjà trackés, les supprimer du cache) :
# nothing to commit, working tree clean
```

Si `.env` ou le JSON avec credentials apparaissent :

```bash
git rm --cached .env hello-asso-automation-conf.json
git commit -m "Remove sensitive files from git"
```

---

## 🆘 Dépannage

### Erreur : "Missing required configuration fields"

**Cause :** Credentials manquantes dans `.env`

**Solution :**
```bash
# Vérifiez que .env existe et contient :
cat .env

# Doit afficher vos credentials
HELLOASSO_CLIENT_ID=xxx
HELLOASSO_CLIENT_SECRET=xxx
OVH_APP_KEY=xxx
# ...
```

### Erreur : "Configuration file not found"

**Cause :** Fichier JSON manquant

**Solution :**
```bash
cp hello-asso-automation-conf.json.example hello-asso-automation-conf.json
# Puis éditez le fichier avec votre config
```

### Les credentials du JSON sont toujours utilisées

**Cause :** Vous avez laissé la section `credentials` dans le JSON

**Solution :** Supprimez complètement cette section du JSON. Les credentials doivent **uniquement** être dans `.env`.

---

## 📊 Comparaison Avant/Après

### ❌ Avant (non sécurisé)

```json
{
  "credentials": {
    "helloAsso": {
      "id": "MON_SECRET",  ← DANGER !
      "secret": "MON_AUTRE_SECRET"  ← DANGER !
    }
  },
  "conf": { ... }
}
```

**Problèmes :**
- ❌ Credentials dans git
- ❌ Visibles dans l'historique
- ❌ Partagées avec tout le monde

### ✅ Après (sécurisé)

**Fichier JSON (versionné) :**
```json
{
  "conf": {
    "helloAsso": {
      "organization_name": "mon-org",
      "form_name": "Mon Formulaire"
    }
  }
}
```

**Fichier .env (ignoré) :**
```env
HELLOASSO_CLIENT_ID=MON_SECRET
HELLOASSO_CLIENT_SECRET=MON_AUTRE_SECRET
```

**Avantages :**
- ✅ Credentials hors de git
- ✅ Config peut être partagée
- ✅ Sécurité maximale

---

## 🚀 En Production

### Avec Docker

```dockerfile
# Dockerfile
ENV HELLOASSO_CLIENT_ID=${HELLOASSO_CLIENT_ID}
ENV HELLOASSO_CLIENT_SECRET=${HELLOASSO_CLIENT_SECRET}
# ...

COPY hello-asso-automation-conf.json /app/
```

```bash
# Lancement
docker run \
  -e HELLOASSO_CLIENT_ID=xxx \
  -e HELLOASSO_CLIENT_SECRET=yyy \
  myapp
```

### Avec systemd

```ini
# /etc/systemd/system/helloasso-sync.service
[Service]
EnvironmentFile=/etc/helloasso/.env
ExecStart=/usr/bin/python /app/main.py /etc/helloasso/config.json
```

### CI/CD

```yaml
# GitHub Actions
env:
  HELLOASSO_CLIENT_ID: ${{ secrets.HELLOASSO_CLIENT_ID }}
  HELLOASSO_CLIENT_SECRET: ${{ secrets.HELLOASSO_CLIENT_SECRET }}
```

---

## ✅ Checklist de Migration

- [ ] Créer `.env` depuis `.env.example`
- [ ] Copier vos credentials dans `.env`
- [ ] Créer JSON depuis `.json.example`
- [ ] Supprimer section `credentials` du JSON
- [ ] Vérifier que `.env` est dans `.gitignore`
- [ ] Tester le chargement
- [ ] Supprimer les credentials de l'historique git si nécessaire

---

**🎉 Voilà ! Vos credentials sont maintenant sécurisées !**
