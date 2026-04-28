"""User subscription data model."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


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
        
        # Mapping explicite des custom fields HelloAsso → Airtable.
        # Clés = libellés exacts des questions HelloAsso (formulaire "Adhésion année 2026").
        # Valeurs = noms de colonnes Airtable dans la table Annuaire.
        custom_field_mapping = {
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
            "Règles de Confidentialité": "Règles de Confidentialité",
        }
        
        # Ajouter uniquement les custom fields qui existent dans le mapping
        for helloasso_field, airtable_field in custom_field_mapping.items():
            if helloasso_field in self.custom_fields:
                value = self.custom_fields[helloasso_field]
                # N'ajouter que si la valeur n'est pas vide
                if value:
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
        # Extract custom fields
        custom_fields = {}
        for field_data in item.get("customFields", []):
            custom_fields[field_data["name"]] = field_data["answer"]
        
        # Apply default fields
        if default_fields:
            for key, value in default_fields.items():
                if key not in custom_fields:
                    custom_fields[key] = value
        
        # Parse subscription date
        date_str = item["order"]["date"].split("+")[0].split(".")[0]
        subscription_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        
        # Handle first subscription field:
        # "Oui" → store the current year (Airtable receives "2026").
        # Anything else (e.g. "Non", empty default) → drop it so the upsert layer
        # falls back to the configured first_year_subscription label.
        if first_sub_field and first_sub_field in custom_fields:
            if custom_fields[first_sub_field] == "Oui":
                custom_fields[first_sub_field] = subscription_date.strftime("%Y")
            else:
                del custom_fields[first_sub_field]
        
        # Handle name field uppercase
        if name_field and name_field in custom_fields:
            custom_fields[name_field] = custom_fields[name_field].upper()
        
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
