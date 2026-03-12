"""Airtable API client."""
import syslog
from typing import Dict, List, Optional
from urllib.parse import quote
import requests


class AirtableClient:
    """Client for interacting with Airtable API."""
    
    def __init__(
        self,
        api_key: str,
        base_id: str,
        table_name: str = "Annuaire",
    ):
        """
        Initialize Airtable client.
        
        Args:
            api_key: Airtable API key or personal access token
            base_id: Airtable base ID
            table_name: Name of the table to work with (default: Annuaire)
        """
        self.api_key = api_key
        self.base_id = base_id
        self.table_name = table_name
        # Encode table name for URL
        self.table_name_encoded = quote(table_name)
        self.base_url = f"https://api.airtable.com/v0/{base_id}/{self.table_name_encoded}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    
    def find_record_by_email(self, email: str, dry_run: bool = False) -> Optional[Dict]:
        """
        Find a record in Airtable by email address.
        
        Args:
            email: Email address to search for
            dry_run: If True, don't make actual API calls
            
        Returns:
            Record dict if found, None otherwise
        """
        if dry_run:
            syslog.syslog(
                syslog.LOG_INFO,
                f"[DRY RUN] Would search for record with email: {email}",
            )
            return None
            
        try:
            # Use filterByFormula to search by email
            # Note: Use single braces {E-mail} in formula, not doubled
            formula = "{E-mail}='" + email + "'"
            
            params = {
                "filterByFormula": formula,
                "maxRecords": 1,
            }
            
            response = requests.get(
                self.base_url,
                headers=self.headers,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            
            records = response.json().get("records", [])
            if records:
                return records[0]
            return None
            
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to find record by email {email}: {e}",
            )
            return None
    
    def create_record(self, fields: Dict, dry_run: bool = False) -> Optional[Dict]:
        """
        Create a new record in Airtable.
        
        Args:
            fields: Dictionary of field names and values
            dry_run: If True, don't make actual API calls
            
        Returns:
            Created record dict if successful, None otherwise
        """
        if dry_run:
            syslog.syslog(
                syslog.LOG_INFO,
                f"[DRY RUN] Would create record with fields: {fields}",
            )
            return {
                "id": "dry_run_record_id",
                "fields": fields,
                "createdTime": "2024-01-01T00:00:00.000Z",
            }
            
        try:
            payload = {
                "fields": fields,
            }
            
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=10,
            )
            
            # Check status before raising
            if response.status_code not in (200, 201):
                error_msg = f"Airtable API error {response.status_code}: {response.text}"
                syslog.syslog(syslog.LOG_ERR, error_msg)
                print(f"DEBUG - {error_msg}")
                response.raise_for_status()
            
            syslog.syslog(
                syslog.LOG_INFO,
                f"Successfully created record for {fields.get('E-mail', fields.get('email', 'unknown'))}",
            )
            return response.json()
            
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to create record: {e}",
            )
            # Also print for debugging in tests
            print(f"DEBUG - Create record error: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                print(f"DEBUG - Response: {e.response.text}")
            return None
    
    def update_record(self, record_id: str, fields: Dict, dry_run: bool = False) -> Optional[Dict]:
        """
        Update an existing record in Airtable.
        
        Args:
            record_id: Airtable record ID
            fields: Dictionary of field names and values to update
            dry_run: If True, don't make actual API calls
            
        Returns:
            Updated record dict if successful, None otherwise
        """
        if dry_run:
            syslog.syslog(
                syslog.LOG_INFO,
                f"[DRY RUN] Would update record {record_id} with fields: {fields}",
            )
            return {
                "id": record_id,
                "fields": fields,
                "createdTime": "2024-01-01T00:00:00.000Z",
            }
            
        try:
            url = f"{self.base_url}/{record_id}"
            
            payload = {
                "fields": fields,
            }
            
            response = requests.patch(
                url,
                headers=self.headers,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            
            syslog.syslog(
                syslog.LOG_INFO,
                f"Successfully updated record {record_id}",
            )
            return response.json()
            
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to update record {record_id}: {e}",
            )
            return None
    
    def upsert_record(self, email: str, fields: Dict, dry_run: bool = False) -> Optional[Dict]:
        """
        Create or update a record based on email (upsert operation).
        
        Args:
            email: Email address to use for lookup
            fields: Dictionary of field names and values (must include email)
            dry_run: If True, don't make actual API calls
            
        Returns:
            Created or updated record dict if successful, None otherwise
        """
        if dry_run:
            syslog.syslog(
                syslog.LOG_INFO,
                f"[DRY RUN] Would upsert record for email: {email}",
            )
            return {
                "id": "dry_run_upsert_id",
                "fields": fields,
                "createdTime": "2024-01-01T00:00:00.000Z",
            }
        
        try:
            # Ensure email is in fields with the correct Airtable field name
            if "E-mail" not in fields:
                fields["E-mail"] = email
            
            # Try to find existing record
            existing_record = self.find_record_by_email(email)
            
            if existing_record:
                # Update existing record
                record_id = existing_record["id"]
                return self.update_record(record_id, fields)
            else:
                # Create new record
                return self.create_record(fields)
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to upsert record for {email}: {e}",
            )
            return None
    
    def list_records(
        self,
        max_records: Optional[int] = None,
        filter_by_formula: Optional[str] = None,
        dry_run: bool = False,
    ) -> List[Dict]:
        """
        List records from Airtable table with automatic pagination.

        Args:
            max_records: Maximum number of records to return
            filter_by_formula: Airtable formula to filter records
            dry_run: If True, don't make actual API calls

        Returns:
            List of record dicts
        """
        if dry_run:
            syslog.syslog(
                syslog.LOG_INFO,
                "[DRY RUN] Would list records",
            )
            return []

        try:
            all_records = []
            offset = None

            while True:
                params = {}
                if max_records:
                    params["maxRecords"] = max_records
                if filter_by_formula:
                    params["filterByFormula"] = filter_by_formula
                if offset:
                    params["offset"] = offset

                response = requests.get(
                    self.base_url,
                    headers=self.headers,
                    params=params,
                    timeout=10,
                )
                response.raise_for_status()

                data = response.json()
                all_records.extend(data.get("records", []))

                offset = data.get("offset")
                if not offset:
                    break

                if max_records and len(all_records) >= max_records:
                    break

            return all_records

        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to list records: {e}",
            )
            return []
