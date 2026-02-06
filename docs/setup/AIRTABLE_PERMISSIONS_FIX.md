# ⚠️ Erreur de Permissions Airtable Détectée

## Problème

Votre Personal Access Token (PAT) Airtable n'a **pas les permissions d'écriture**.

Erreur API:
```
403 Forbidden: INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND
Invalid permissions, or the requested model was not found
```

## ✅ Ce qui fonctionne
- ✅ Lecture (GET) - list_records
- ✅ Authentification valide

## ❌ Ce qui ne fonctionne pas
- ❌ Création (POST) - create_record
- ❌ Mise à jour (PATCH) - update_record  
- ❌ Suppression (DELETE) - delete_record

## 🔧 Solution: Créer un nouveau token avec les bonnes permissions

### Étape 1: Aller sur Airtable Developer Hub

1. Allez sur: https://airtable.com/create/tokens
2. Ou: Account > Developer hub > Personal access tokens

### Étape 2: Créer un nouveau token

1. Cliquez sur **"Create new token"** ou **"Create token"**
2. Donnez un nom: `API Automation Tests` ou `Full Access Token`

### Étape 3: Configurer les Scopes (Permissions)

Cochez **AU MINIMUM** ces permissions:

#### Data Permissions
- ✅ `data.records:read` - Read data in records
- ✅ `data.records:write` - Create, update, and delete records
- ✅ `schema.bases:read` - Read base schema

#### Permissions recommandées (optionnelles)
- `data.recordComments:read` - Read comments
- `data.recordComments:write` - Write comments

### Étape 4: Sélectionner les Bases

1. Dans la section **"Add bases"**
2. Sélectionnez votre base: **"Annuaire sandbox testing"** ou la base avec ID `appXXXXXXXXXXXXXX`
3. Cliquez sur **"Add base"****

### Étape 5: Créer et Copier le Token

1. Cliquez sur **"Create token"**
2. **Copiez le token** (il ne sera affiché qu'une fois!)
3. Le token ressemble à: `patXXXXXXXXXXXX.XXXXXXXXXXXXXXXXX`

### Étape 6: Mettre à jour votre .env

```bash
# Ancien token (READ ONLY)
# AIRTABLE_API_KEY=patOLDTOKEN.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# Nouveau token (READ + WRITE)
AIRTABLE_API_KEY=patNEWTOKEN.YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
```

### Étape 7: Vérifier

```bash
# Vérifier la configuration
python check_airtable_config.py

# Tester les tests
pytest tests/test_functional.py::TestAirtableConnection -v -s
```

## 📋 Checklist des Permissions Requises

Pour que les tests fonctionnent, votre token doit avoir:

| Permission | Requis | Description |
|------------|--------|-------------|
| `data.records:read` | ✅ Oui | Lire les enregistrements (list, find) |
| `data.records:write` | ✅ Oui | Créer/modifier/supprimer des enregistrements |
| `schema.bases:read` | ✅ Oui | Lire la structure de la base |
| Base sélectionnée | ✅ Oui | La base doit être ajoutée au token |

## 🔍 Vérification des Permissions Actuelles

Votre token actuel:
```
patXXXXXXXXXXXX.YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY
```

Permissions détectées:
- ✅ `data.records:read` - OUI (list_records fonctionne)
- ❌ `data.records:write` - NON (create/update échouent avec 403)
- ✅ Base access - OUI (mais en lecture seule)

## 💡 Alternative: Utiliser un token existant

Si vous avez déjà un token avec les bonnes permissions:

1. Allez sur https://airtable.com/create/tokens
2. Trouvez un token existant avec `data.records:write`
3. Vérifiez que votre base est dans la liste des bases autorisées
4. Copiez le token et mettez à jour votre `.env`

## 🎯 Résultat Attendu

Après avoir créé le nouveau token, les tests devraient passer:

```bash
tests/test_functional.py::TestAirtableConnection::test_list_records PASSED
tests/test_functional.py::TestAirtableConnection::test_create_and_delete_user PASSED
tests/test_functional.py::TestAirtableConnection::test_update_and_rollback_user PASSED
```

## ❓ Besoin d'aide?

Si vous ne pouvez pas créer de token avec permissions d'écriture:

1. Vérifiez que vous êtes **Owner** ou **Creator** de la base
2. Les utilisateurs avec rôle **Commenter** ou **Read only** ne peuvent pas créer de tokens d'écriture
3. Contactez l'owner de la base pour obtenir les permissions nécessaires
