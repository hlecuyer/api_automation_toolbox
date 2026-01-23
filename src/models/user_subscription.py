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
    
    def to_webhook_payload(self) -> Dict[str, str]:
        """
        Convert the subscription to a webhook payload format.
        
        Returns:
            Dictionary with all fields formatted for webhook.
        """
        payload = {
            "email": self.email,
            "firstName": self.first_name,
            "lastName": self.last_name.upper(),
            "date": self.subscription_date.isoformat(),
            "cotisation": self.cotisation,
            "groupe": self.groupe,
        }
        
        # Add custom fields
        payload.update(self.custom_fields)
        
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
        
        # Handle first subscription field
        if first_sub_field and first_sub_field in custom_fields:
            if custom_fields[first_sub_field] == "Oui":
                custom_fields[first_sub_field] = subscription_date.strftime("%Y")
        
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
