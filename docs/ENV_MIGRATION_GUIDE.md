# Guide de Migration vers les Variables d'Environnement

## 🔐 Nouvelle Méthode Sécurisée

Vos credentials ne sont plus dans le code ou les fichiers JSON versionnés. Ils sont maintenant gérés via des **variables d'environnement** avec `.env`.

---

## 📋 Étapes de Configuration

### 1. Installer les dépendances

```bash
pip install -r requirements.txt
```

Cela installera `python-dotenv==1.0.0`.

### 2. Créer votre fichier `.env`

```bash
cp .env.example .env
```

### 3. Remplir vos credentials dans `.env`

Éditez le fichier `.env` (qui est **ignoré par git**) :

```env
# HelloAsso API Credentials
HELLOASSO_CLIENT_ID=votre_vrai_client_id
HELLOASSO_CLIENT_SECRET=votre_vrai_client_secret
HELLOASSO_API_URL=https://api.helloasso.com
HELLOASSO_ORG_NAME=votre_organisation
HELLOASSO_FORM_NAME=Votre Formulaire
HELLOASSO_SUBSCRIPTION_AFTER=2024-01-01T00:00:00

# OVH API Credentials
OVH_ENDPOINT=ovh-eu
OVH_APP_KEY=votre_app_key
OVH_APP_SECRET=votre_app_secret
OVH_CONSUMER_KEY=votre_consumer_key
OVH_MAILING_LIST_NAME=votre_liste
OVH_MAILING_LIST_DOMAIN=votredomaine.org

# Airtable/Webhook
WEBHOOK_URL=https://hooks.airtable.com/workflows/v1/PROD_ID
WEBHOOK_URL_TEST=https://hooks.airtable.com/workflows/v1/TEST_ID

# Autres
COTISATION_LABEL=votre_label
GROUPE=votre_groupe
```

---

## 🚀 Utilisation

### Option 1 : Uniquement variables d'environnement (recommandé)

```python
from hello_asso_sync import SyncHelloAsso

# Charge automatiquement depuis .env
sync = SyncHelloAsso()
sync.run()
```

### Option 2 : Variables d'environnement + fichier JSON

```python
from hello_asso_sync import SyncHelloAsso

# Charge .env ET le JSON, .env a la priorité
sync = SyncHelloAsso("config.json")
sync.run()
```

### Option 3 : Variables d'environnement système

```bash
# Sans fichier .env, directement dans le terminal
export HELLOASSO_CLIENT_ID="xxx"
export HELLOASSO_CLIENT_SECRET="xxx"
# ...

python main.py
```

---

## 🔄 Compatibilité

### ✅ Ancien code (avec JSON)

```python
# Fonctionne toujours !
sync = SyncHelloAsso("hello-asso-automation-conf.json")
```

### ✅ Nouveau code (avec .env)

```python
# Nouveau - plus sécurisé !
sync = SyncHelloAsso()  # config_path est maintenant optionnel
```

### ✅ Hybride (JSON + .env)

```python
# Les variables d'environnement écrasent le JSON
sync = SyncHelloAsso("config.json")
```

---

## 🧪 Tests

### Tests unitaires (mocks)

Les tests unitaires continuent de fonctionner avec des configs mockées :

```bash
pytest test_hello_asso_sync.py -v
```

### Tests fonctionnels (vraies APIs)

Créez un fichier `.env.test` pour les tests :

```bash
cp .env.example .env.test
# Remplissez avec vos credentials de test
```

Puis :

```bash
# Charge .env.test au lieu de .env
export $(cat .env.test | xargs)
pytest test_hello_asso_sync_functional.py -v -s
```

---

## 📦 En Production

### CI/CD (GitHub Actions, GitLab CI, etc.)

Ajoutez vos variables d'environnement dans les secrets de votre CI :

```yaml
# Exemple GitHub Actions
env:
  HELLOASSO_CLIENT_ID: ${{ secrets.HELLOASSO_CLIENT_ID }}
  HELLOASSO_CLIENT_SECRET: ${{ secrets.HELLOASSO_CLIENT_SECRET }}
  # ...
```

### Serveur / Docker

```bash
# Avec Docker
docker run -e HELLOASSO_CLIENT_ID=xxx -e HELLOASSO_CLIENT_SECRET=xxx ...

# Ou avec un fichier .env
docker run --env-file .env ...
```

### Systemd / Cron

```ini
# /etc/systemd/system/helloasso-sync.service
[Service]
EnvironmentFile=/path/to/.env
ExecStart=/path/to/python /path/to/main.py
```

---

## ✅ Avantages de cette approche

1. **🔒 Sécurité** : Credentials jamais dans le code versionné
2. **🔄 Flexibilité** : Changement facile entre environnements (dev/test/prod)
3. **📝 Standard** : Approche utilisée par la majorité des projets
4. **✨ Rétrocompatible** : Ancien code avec JSON fonctionne toujours
5. **🚀 CI/CD Ready** : Facile à intégrer dans les pipelines

---

## 🛡️ Sécurité

### ✅ Fichiers ignorés par git

Le `.gitignore` inclut maintenant :
```
.env
.env.local
.env.test
*.local.json
```

### ⚠️ Ne commitez JAMAIS

- ❌ `.env`
- ❌ Fichiers contenant des credentials
- ✅ `.env.example` (sans credentials, juste la structure)

---

## 📚 Référence des Variables

Voir [.env.example](.env.example) pour la liste complète des variables disponibles.

### Priorité de chargement

1. **Variables d'environnement système** (priorité max)
2. **Fichier `.env`**
3. **Fichier JSON** (si fourni)
4. **Valeurs par défaut** (dans `config_loader.py`)

---

## 🆘 Dépannage

### Erreur : "Missing required configuration fields"

→ Vérifiez que toutes les variables requises sont définies dans `.env`

### .env n'est pas chargé

→ Assurez-vous que le fichier `.env` est à la racine du projet

### Tests échouent

→ Pour les tests unitaires : pas besoin de `.env` (ils utilisent des mocks)
→ Pour les tests fonctionnels : créez `.env` avec vos vraies credentials

---

## 🔄 Migration depuis l'ancien système

### Si vous aviez `hello-asso-automation-conf.json` avec credentials :

1. Copiez les valeurs vers `.env`
2. Supprimez les credentials du JSON (gardez juste la structure si besoin)
3. Lancez votre code : `python main.py`

Le nouveau système charge automatiquement depuis `.env` !
