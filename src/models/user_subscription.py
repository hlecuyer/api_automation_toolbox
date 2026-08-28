"""User subscription data model."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


# Mapping explicite des questions HelloAsso → colonnes de la table Annuaire.
#
# Clés = **libellés exacts** des questions, tels que HelloAsso les renvoie. Un
# libellé qui diffère d'un caractère ne lève rien : la réponse est simplement
# ignorée, et la colonne reste vide pour toujours.
#
# Ce n'est pas théorique. Le 27/08/2026, la clé « Règles de Confidentialité » ne
# correspondait à aucune question du formulaire — la vraie s'appelle
# « J'accepte les règles de confidentialité de La Coop des Communs… », espace
# finale comprise. Résultat : le consentement de 84 adhérents 2026 n'a jamais
# été enregistré, sans le moindre message d'erreur.
#
# Sorti au niveau module pour être inspectable : `scripts/bac_a_sable.py
# formulaire` compare ces clés aux questions réellement publiées et signale
# celles qui ne rencontrent rien.
def _cle(libelle):
    """Forme d'un libellé de question retenue pour la comparaison.

    Ne sert qu'à rapprocher deux libellés, jamais à écrire : ce qui part vers
    Airtable reste la valeur reçue.
    """
    return libelle.strip() if isinstance(libelle, str) else libelle


CHAMPS_HELLOASSO_VERS_AIRTABLE = {
    "Genre": "Genre",
    "Structure": "Structure(s)",
    # "Date de naissance": "date de naissance",  # Format incompatible, à convertir
    "Fonction au sein de votre structure": "Fonction (structure)",
    "Intérêts (mot-clés)": "Intérêts",
    "Localisation (code postal)": "code postal",
    "Je souhaite que mon Nom et Prénom soient partagés sur le site web de l'association dans la liste des adhérent·es": "Visible sur le site",
    "Souhaitez-vous partager les informations précédentes avec les autres adhérent·es de la Coop des Communs ? Pour information, les champs suivants seront uniquement accessibles par l'équipe de gestion de l'association et les prestataires missionnés.": "Partage de donnée autorisé",
    "Si oui, pouvez-vous nous indiquer deux personnes connues au sein de l'association ?": "2 personnes connues",
    "Est-ce votre première adhésion à la coop des communs ?": "Année de première adhésion",
    # Le libellé complet, tel que le formulaire le pose. La clé était
    # « Règles de Confidentialité » — un nom de colonne Airtable, pas une
    # question — et ne rencontrait donc jamais rien. Aucun message d'erreur :
    # 84 consentements de l'année 2026 non enregistrés, découverts le
    # 27/08/2026 en comparant le formulaire au code.
    "J'accepte les règles de confidentialité de La Coop des Communs, disponibles à cette adresse : https://coopdescommuns.org/fr/confidentialite/": "Règles de Confidentialité",
}

# Colonnes Airtable de type « case à cocher », qui n'acceptent qu'un booléen.
#
# Cette déclaration vit dans le code, avec le mappage, et non dans la
# configuration : les deux moitiés du correctif doivent voyager ensemble. Corriger
# le libellé ci-dessus sans convertir la valeur ferait écrire la chaîne « Oui »
# dans une case à cocher ; comme le code n'utilise pas `typecast`, Airtable
# refuserait **l'écriture entière** et `hello_asso_sync` abandonnerait l'adhésion
# complète — fiche, liste de diffusion et mail de bienvenue compris — pour un
# champ secondaire. Mesuré le 28/08/2026 dans le bac à sable, pas supposé :
#   INVALID_VALUE_FOR_COLUMN — Field "Règles de Confidentialité" cannot accept
#   the provided value
# Les deux autres questions Oui/Non du formulaire (« Visible sur le site »,
# « Partage de donnée autorisé ») ne sont pas des cases à cocher : elles
# acceptent la chaîne, vérifié au même passage.
CHAMPS_BOOLEENS_AIRTABLE = {"Règles de Confidentialité"}

# Ce qu'une réponse HelloAsso veut dire pour une case à cocher. Une valeur
# inconnue n'est pas devinée : elle laisse la case décochée, ce qui est le sens
# prudent d'un consentement.
REPONSES_VRAIES = {"oui", "yes", "true", "1"}


def _booleen(valeur):
    if isinstance(valeur, bool):
        return valeur
    return str(valeur).strip().lower() in REPONSES_VRAIES


@dataclass
class UserSubscription:
    """Represents a user subscription from HelloAsso."""
    
    email: str
    first_name: str
    last_name: str
    subscription_date: datetime
    cotisation: str
    groupe: str
    custom_fields: Dict[str, str] = field(default_factory=dict)
    
    # Optional fields from HelloAsso
    state: str = "Processed"
    
    def to_airtable_payload(self) -> Dict[str, str]:
        """
        Convert the subscription to an Airtable payload format.
        
        Returns:
            Dictionary with all fields formatted for Airtable.
        """
        payload = {
            "E-mail": self.email,
            "Prénom": self.first_name,
            "Nom": self.last_name.upper(),
            # "Date d'adhésion" is a computed field in Airtable, don't send it
            "Cotisation LCDC": self.cotisation,
            "Groupe(s)": self.groupe,
        }
        
        custom_field_mapping = CHAMPS_HELLOASSO_VERS_AIRTABLE
        
        # Ajouter uniquement les custom fields qui existent dans le mapping
        for helloasso_field, airtable_field in custom_field_mapping.items():
            if _cle(helloasso_field) in self.custom_fields:
                value = self.custom_fields[_cle(helloasso_field)]
                # N'ajouter que si la valeur n'est pas vide
                if value:
                    if airtable_field in CHAMPS_BOOLEENS_AIRTABLE:
                        value = _booleen(value)
                    payload[airtable_field] = value
        
        return payload
    
    @classmethod
    def from_hello_asso_item(
        cls,
        item: Dict,
        cotisation: str,
        groupe: str,
        default_fields: Optional[Dict[str, str]] = None,
        first_sub_field: Optional[str] = None,
        name_field: Optional[str] = None,
    ) -> "UserSubscription":
        """
        Create a UserSubscription from HelloAsso API item.
        
        Args:
            item: Raw item data from HelloAsso API
            cotisation: Cotisation label from config
            groupe: Group from config
            default_fields: Default custom fields to apply
            first_sub_field: Field name for first subscription year
            name_field: Field name to uppercase
            
        Returns:
            UserSubscription instance
        """
        # Les libellés sont rognés à l'entrée, une fois, pour que plus rien en aval
        # n'ait à y penser.
        #
        # Un libellé de question est saisi à la main dans HelloAsso et recopié à la
        # main dans la configuration : une espace en trop d'un côté suffit à ce que
        # la réponse ne soit jamais lue, sans erreur ni trace. Le 27/08/2026, le
        # formulaire de production posait « J'accepte les règles de confidentialité
        # … » avec une espace finale, et le formulaire de test créé par duplication
        # posait le même libellé sans elle : deux formulaires censés être
        # identiques, deux comportements différents. Un bac à sable qui ne rejoue
        # pas la production ne prouve rien.
        custom_fields = {}
        for field_data in item.get("customFields", []):
            custom_fields[_cle(field_data["name"])] = field_data["answer"]
        
        # Apply default fields
        if default_fields:
            for key, value in default_fields.items():
                if _cle(key) not in custom_fields:
                    custom_fields[_cle(key)] = value
        
        # Parse subscription date
        date_str = item["order"]["date"].split("+")[0].split(".")[0]
        subscription_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        
        # Handle first subscription field:
        # "Oui" → store the current year (Airtable receives "2026").
        # Anything else (e.g. "Non", empty default) → drop it so the upsert layer
        # falls back to the configured first_year_subscription label.
        if first_sub_field and _cle(first_sub_field) in custom_fields:
            if custom_fields[_cle(first_sub_field)] == "Oui":
                custom_fields[_cle(first_sub_field)] = subscription_date.strftime("%Y")
            else:
                del custom_fields[_cle(first_sub_field)]
        
        # Handle name field uppercase
        if name_field and _cle(name_field) in custom_fields:
            custom_fields[_cle(name_field)] = custom_fields[_cle(name_field)].upper()
        
        return cls(
            email=item["payer"]["email"],
            first_name=item["user"]["firstName"],
            last_name=item["user"]["lastName"],
            subscription_date=subscription_date,
            cotisation=cotisation,
            groupe=groupe,
            custom_fields=custom_fields,
            state=item["state"],
        )
