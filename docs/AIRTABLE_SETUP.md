# Configuration Airtable pour les Tests

## 🔑 Trouver votre Base ID

### Méthode 1: Via l'URL Airtable

1. Ouvrez votre base Airtable dans le navigateur
2. L'URL ressemble à: `https://airtable.com/appXXXXXXXXXXXXXX/tblYYYYYYYYYYYYYY/...`
3. Le Base ID est la partie qui commence par **`app`**: `appXXXXXXXXXXXXXX`

**Exemple:**
```
URL: https://airtable.com/app1234567890ABC/tblViewXYZ/viwGridABC
Base ID: app1234567890ABC  ← Copiez cette partie!
```

### Méthode 2: Via l'API Airtable

1. Allez sur https://airtable.com/api
2. Sélectionnez votre base
3. Le Base ID apparaît en haut: "The ID of this base is `appXXXXXXXXXXXXXX`"

### Méthode 3: Via Account > API

1. Connectez-vous à Airtable
2. Allez dans Account > API (https://airtable.com/account)
3. Cliquez sur votre base
4. Le Base ID est affiché clairement

## 📝 Configuration dans .env

Une fois que vous avez votre Base ID:

```bash
# Dans votre fichier .env
AIRTABLE_API_KEY=patXXXXXXXXXXXX.YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY
AIRTABLE_BASE_ID=app1234567890ABC  # ← Remplacez par votre vrai Base ID
```

⚠️ **Important**: Le Base ID doit commencer par `app`, PAS entre guillemets!

## ❌ Erreurs communes

### Erreur 1: Nom au lieu d'ID
```bash
# ❌ INCORRECT
AIRTABLE_BASE_ID="Annuaire sandbox testing"

# ✅ CORRECT
AIRTABLE_BASE_ID=app1234567890ABC
```

### Erreur 2: Guillemets autour de l'ID
```bash
# ❌ INCORRECT
AIRTABLE_BASE_ID="app1234567890ABC"

# ✅ CORRECT
AIRTABLE_BASE_ID=app1234567890ABC
```

## 🧪 Vérifier la configuration

Après avoir mis à jour votre `.env`:

```bash
# Test rapide
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(f'Base ID: {os.getenv(\"AIRTABLE_BASE_ID\")}')"

# Doit afficher: Base ID: appXXXXXXXXXXXXXX
```

## 🏗️ Structure de votre table Airtable

Votre table "Annuaire" doit avoir au minimum ces champs:

| Champ | Type | Requis |
|-------|------|--------|
| Email | Single line text | ✅ |
| Prénom | Single line text | ✅ |
| Nom | Single line text | ✅ |
| Date adhésion | Date | ⚪ |
| Cotisation | Single line text | ⚪ |
| Groupe | Single line text | ⚪ |

## 🎯 Test de connexion

Une fois configuré, testez:

```bash
pytest tests/test_functional.py::TestAirtableConnection::test_list_records -v -s
```

Si la configuration est correcte, vous devriez voir:
```
✓ Retrieved X records from Airtable
PASSED
```
