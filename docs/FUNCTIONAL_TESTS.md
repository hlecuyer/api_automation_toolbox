# Tests Fonctionnels HelloAsso Sync

## Vue d'ensemble

Les tests fonctionnels se connectent **réellement à l'API HelloAsso** pour valider l'intégration, mais **mockent les appels aux webhooks Zapier et à l'API OVH** pour éviter d'envoyer des données pendant les tests.

## ⚠️ Important

**Ce qui est testé avec de vraies connexions :**
- ✅ Authentification HelloAsso
- ✅ Récupération des formulaires
- ✅ Récupération des données d'adhésions

**Ce qui est mocké (pas d'envoi réel) :**
- 🚫 Webhooks Zapier/Airtable - **AUCUN envoi**
- 🚫 API OVH mailing list - **AUCUN appel**

## Configuration

### 1. Créer le fichier de configuration de test

Copiez le template :

```bash
cp hello-asso-automation-conf.json.example hello-asso-automation-conf-test.json
```

Remplissez avec **votre vraie configuration HelloAsso** (les webhooks ne seront pas appelés) :

```json
{
  "conf": {
    "helloAsso": {
      "api_url": "https://api.helloasso.com",
      "organization_name": "votre-org",
      "form_name": "Votre Formulaire",
      "subscription_after": "2024-01-01T00:00:00"
    },
    "webhook_url": "https://hooks.zapier.com/... (ne sera pas appelé)"
  }
}
```

### 2. Créer le fichier `.env` avec vos credentials

```bash
cp .env.example .env
```

Remplissez `.env` avec vos **vraies credentials HelloAsso** :

```env
HELLOASSO_CLIENT_ID=votre_client_id
HELLOASSO_CLIENT_SECRET=votre_client_secret

# OVH (peut être vide, l'API est mockée)
OVH_ENDPOINT=ovh-eu
OVH_APP_KEY=dummy
OVH_APP_SECRET=dummy
OVH_CONSUMER_KEY=dummy
```

**Important** : Ajoutez `hello-asso-automation-conf-test.json` à votre `.gitignore` !

## Exécution des tests

### Tous les tests fonctionnels
```bash
pytest test_hello_asso_sync_functional.py -v -s
```

### Tests spécifiques

**Test de connexion HelloAsso :**
```bash
pytest test_hello_asso_sync_functional.py::TestFunctionalSync::test_real_connection_to_helloasso -v -s
```

**Test de récupération de données :**
```bash
pytest test_hello_asso_sync_functional.py::TestFunctionalSync::test_get_form_data_from_helloasso -v -s
```

**Test du workflow complet (mocké) :**
```bash
pytest test_hello_asso_sync_functional.py::TestFunctionalSync::test_sync_workflow_without_sending -v -s
```

**Dry run (inspection des données) :**
```bash
pytest test_hello_asso_sync_functional.py::TestFunctionalSync::test_dry_run_data_inspection -v -s
```

**Inspection des appels webhook et OVH :**
```bash
pytest test_hello_asso_sync_functional.py::TestFunctionalSync::test_inspect_webhook_and_ovh_data -v -s
```

## Description des tests

### test_real_connection_to_helloasso
- ✅ Teste la connexion à l'API HelloAsso
- ✅ Vérifie l'authentification
- ✅ Récupère les détails du formulaire
- 🚫 Ne touche pas aux webhooks ou OVH

### test_get_form_data_from_helloasso
- ✅ Récupère les données réelles de HelloAsso
- ✅ Affiche le nombre d'enregistrements
- ✅ Affiche les statistiques (processed, etc.)
- 🚫 N'envoie rien nulle part

### test_sync_workflow_without_sending
- ✅ Récupère les données de HelloAsso
- ✅ Exécute la logique de synchronisation
- 🔶 Mock les appels webhook (comptabilisés mais pas envoyés)
- 🔶 Mock les appels OVH (comptabilisés mais pas envoyés)
- ✅ Affiche combien d'appels auraient été faits

### test_dry_run_data_inspection
- ✅ Récupère les données de HelloAsso
- ✅ Sauvegarde dans un fichier JSON pour inspection
- ✅ Affiche des statistiques détaillées
- ✅ Montre un échantillon de données
- 🚫 N'envoie rien

### test_inspect_webhook_and_ovh_data
- ✅ Récupère les données de HelloAsso
- ✅ Traite les données comme pour un envoi réel
- 📊 **Affiche en détail** ce qui serait envoyé aux webhooks
- 📊 **Affiche en détail** ce qui serait envoyé à OVH
- 🔶 Mock les appels (capture mais n'envoie pas)
- ✅ Parfait pour valider le format des données

### test_authentication_token_valid
- ✅ Vérifie que le token d'authentification est valide
- ✅ Fait un appel API simple pour tester
- 🚫 Ne manipule aucune donnée

### test_complete_sync_workflow_mocked (slow)
- ✅ Exécute le workflow complet `sync.run()`
- 🔶 Tous les appels externes sont mockés sauf HelloAsso
- ⚠️ Marqué comme `@pytest.mark.slow`

## Workflow recommandé

### 1. Développement - Tests unitaires avec mocks
```bash
pytest test_hello_asso_sync.py -v
```

### 2. Validation HelloAsso - Test de connexion
```bash
pytest test_hello_asso_sync_functional.py::TestFunctionalSync::test_real_connection_to_helloasso -v -s
```

### 3. Inspection des données - Dry run
```bash
pytest test_hello_asso_sync_functional.py::TestFunctionalSync::test_dry_run_data_inspection -v -s
```

Les données sont sauvegardées dans `/tmp/pytest-xxx/helloasso_data_inspection.json`

### 4. Test du workflow - Sans envoi réel
```bash
pytest test_hello_asso_sync_functional.py::TestFunctionalSync::test_sync_workflow_without_sending -v -s
```

Vous verrez combien d'appels webhook/OVH auraient été faits, sans rien envoyer réellement.

### 5. Production - Avec vraie config
Une fois validé, utilisez votre vraie config de production.

## Variables d'environnement

Spécifiez un fichier de config personnalisé :

```bash
export FUNCTIONAL_TEST_CONFIG=/path/to/your/config.json
pytest test_hello_asso_sync_functional.py -v -s
```

## Sécurité et Bonnes Pratiques

✅ **Tests sans risque :**
- Aucun webhook n'est appelé
- Aucune donnée n'est envoyée à OVH
- Seule l'API HelloAsso est interrogée (lecture seule)

✅ **Credentials protégées :**
- `.env` dans `.gitignore`
- `hello-asso-automation-conf-test.json` dans `.gitignore`
- Ne commitez jamais vos credentials

✅ **Données réelles :**
- Les tests utilisent vos vraies données HelloAsso
- Utile pour valider le parsing et la logique métier
- Aucun risque d'envoi accidentel

## Dépannage

### Erreur : "Functional test config not found"

→ Créez `hello-asso-automation-conf-test.json` depuis le template

### Erreur : "Missing required configuration fields"

→ Vérifiez que `.env` contient vos credentials HelloAsso

### Erreur d'authentification HelloAsso

→ Vérifiez que vos credentials dans `.env` sont correctes

### Je veux tester les vrais webhooks

⚠️ **Ce n'est pas le but de ces tests !** Pour tester les webhooks :
1. Utilisez un environnement de staging dédié
2. Ou créez des tests d'intégration séparés avec des webhooks de test

## Prochaines étapes

Quand vous migrez de Zapier vers Airtable directement :
1. Créez de nouveaux tests pour l'API Airtable
2. Moquez Airtable dans les tests fonctionnels
3. Créez des tests d'intégration séparés pour Airtable

## Résumé

🎯 **Ces tests valident :**
- ✅ Connexion HelloAsso
- ✅ Récupération de données
- ✅ Logique de traitement
- ✅ Workflow complet

🚫 **Sans jamais envoyer de données vers :**
- Webhooks Zapier/Airtable
- API OVH
- Aucun service externe (sauf HelloAsso en lecture)
