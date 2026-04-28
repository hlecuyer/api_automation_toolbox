"""Airtable API client."""
import sys
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
        linked_records: Optional[Dict[str, Dict]] = None,
        computed_fields: Optional[Dict[str, Dict]] = None,
    ):
        """
        Initialize Airtable client.

        Args:
            api_key: Airtable API key or personal access token
            base_id: Airtable base ID
            table_name: Name of the table to work with (default: Annuaire)
            linked_records: Optional mapping of field name → {linked_table, match_field, on_missing}.
                on_missing is "warn" (drop the field) or "create" (create the linked record).
                Used by upsert_record to resolve string values to record IDs.
            computed_fields: Optional dict of fields whose value depends on the upsert context
                (whether the record is being created or updated). Recognized keys:
                - "new_member": {"field": str, "create_value": str, "update_value": str} —
                   always sets the field to create_value on CREATE, update_value on UPDATE.
                - "first_year_subscription": {"field": str, "fallback_value": str} —
                   on CREATE, sets the field to fallback_value if it isn't already in the
                   payload (e.g. HelloAsso didn't say "Oui" to "first adhésion?"). On UPDATE,
                   only fills it if both the payload and the existing record are missing it,
                   so historical values are preserved.
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
        self.linked_records = linked_records or {}
        self.computed_fields = computed_fields or {}
        # In-process cache to avoid re-querying linked tables for the same name
        # Key: (linked_table, match_field, value) → record_id
        self._linked_record_cache: Dict[tuple, str] = {}
    
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

            if response.status_code not in (200, 201):
                error_msg = f"Airtable API error {response.status_code} on PATCH {url}: {response.text}"
                syslog.syslog(syslog.LOG_ERR, error_msg)
                # Print so cron MAILTO triggers (syslog alone doesn't surface to cron)
                print(f"DEBUG - {error_msg}")
                response.raise_for_status()

            syslog.syslog(
                syslog.LOG_INFO,
                f"Successfully updated record {record_id}",
            )
            return response.json()

        except Exception as e:
            error_msg = f"Failed to update record {record_id}: {e}"
            syslog.syslog(syslog.LOG_ERR, error_msg)
            print(f"DEBUG - {error_msg}")
            if hasattr(e, "response") and hasattr(e.response, "text"):
                print(f"DEBUG - Response: {e.response.text}")
            return None
    
    def resolve_linked_record(
        self,
        linked_table: str,
        match_field: str,
        value: str,
        create_if_missing: bool = False,
    ) -> Optional[str]:
        """
        Resolve a string value to a linked record ID by matching a field in another table.

        Args:
            linked_table: Name of the table to search in (e.g., "Liste des groupes")
            match_field: Field name to match against (typically the primary field, e.g., "Nom")
            value: String value to look up
            create_if_missing: If True and value is not found, create a new record in the linked table

        Returns:
            Record ID (e.g., "recXXX") if found or created, None otherwise.
        """
        if not value:
            return None

        cache_key = (linked_table, match_field, value)
        if cache_key in self._linked_record_cache:
            return self._linked_record_cache[cache_key]

        encoded_table = quote(linked_table)
        url = f"https://api.airtable.com/v0/{self.base_id}/{encoded_table}"

        # Airtable formulas use single quotes for strings; escape any in the value
        escaped_value = value.replace("'", "\\'")
        formula = f"{{{match_field}}}='{escaped_value}'"

        try:
            response = requests.get(
                url,
                headers=self.headers,
                params={"filterByFormula": formula, "maxRecords": 1},
                timeout=10,
            )
            response.raise_for_status()
            records = response.json().get("records", [])
            if records:
                record_id = records[0]["id"]
                self._linked_record_cache[cache_key] = record_id
                return record_id
        except Exception as e:
            error_msg = (
                f"Failed to lookup '{value}' in linked table '{linked_table}' "
                f"(match_field='{match_field}'): {e}"
            )
            syslog.syslog(syslog.LOG_ERR, error_msg)
            print(f"DEBUG - {error_msg}", file=sys.stderr)
            if hasattr(e, "response") and hasattr(e.response, "text"):
                print(f"DEBUG - Response: {e.response.text}", file=sys.stderr)
            return None

        # Not found
        if not create_if_missing:
            warning_msg = (
                f"Linked value '{value}' not found in '{linked_table}' "
                f"(match_field='{match_field}') — field will be skipped"
            )
            syslog.syslog(syslog.LOG_WARNING, warning_msg)
            print(f"WARNING - {warning_msg}", file=sys.stderr)
            return None

        # Create on the fly
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json={"fields": {match_field: value}},
                timeout=10,
            )
            if response.status_code not in (200, 201):
                error_msg = (
                    f"Failed to create '{value}' in '{linked_table}': "
                    f"{response.status_code} {response.text}"
                )
                syslog.syslog(syslog.LOG_ERR, error_msg)
                print(f"DEBUG - {error_msg}", file=sys.stderr)
                return None
            new_id = response.json()["id"]
            syslog.syslog(
                syslog.LOG_INFO,
                f"Created '{value}' in '{linked_table}' as {new_id}",
            )
            self._linked_record_cache[cache_key] = new_id
            return new_id
        except Exception as e:
            error_msg = f"Failed to create '{value}' in '{linked_table}': {e}"
            syslog.syslog(syslog.LOG_ERR, error_msg)
            print(f"DEBUG - {error_msg}", file=sys.stderr)
            if hasattr(e, "response") and hasattr(e.response, "text"):
                print(f"DEBUG - Response: {e.response.text}", file=sys.stderr)
            return None

    def _apply_linked_records(
        self,
        fields: Dict,
        existing_record: Optional[Dict],
    ) -> None:
        """
        Resolve configured linked-record fields in `fields` from string → [record IDs].

        On UPDATE (existing_record provided), merges with the record's existing IDs so
        we never overwrite groups/structures already attached to the user.

        If a value cannot be resolved (and on_missing != "create"), the field is removed
        from `fields` so the rest of the payload still goes through.

        Mutates `fields` in place.
        """
        for field_name, conf in self.linked_records.items():
            if field_name not in fields:
                continue

            value = fields[field_name]
            if not value:
                # Empty value — drop the field (don't send "" to a linked field)
                del fields[field_name]
                continue

            new_id = self.resolve_linked_record(
                linked_table=conf["linked_table"],
                match_field=conf.get("match_field", "Nom"),
                value=value,
                create_if_missing=conf.get("on_missing") == "create",
            )

            if new_id is None:
                # Resolution failed and not creating → drop the field, keep the rest
                del fields[field_name]
                continue

            ids = [new_id]
            if existing_record:
                existing_ids = existing_record.get("fields", {}).get(field_name, [])
                if isinstance(existing_ids, list):
                    # Preserve existing links, append new one if not already there.
                    # dict.fromkeys preserves insertion order while deduplicating.
                    ids = list(dict.fromkeys(existing_ids + [new_id]))

            fields[field_name] = ids

    def _apply_computed_fields(
        self,
        fields: Dict,
        existing_record: Optional[Dict],
    ) -> None:
        """
        Apply computed-field rules to `fields` based on whether this is a CREATE or UPDATE.

        - "new_member": always sets the field. CREATE → create_value, UPDATE → update_value.
        - "first_year_subscription": curated Airtable data always wins. We do NOT trust
          the user's "Est-ce votre première adhésion ?" answer over a value the team has
          already set on the record. Priority order:
            1. Existing Airtable value → keep it (drop the field from the PATCH payload)
            2. HelloAsso payload (year from "Oui") → send it
            3. fallback_value (if non-empty) → send it
            4. Otherwise → leave the column empty

        Mutates `fields` in place.
        """
        is_create = existing_record is None

        new_member_conf = self.computed_fields.get("new_member")
        if new_member_conf and "field" in new_member_conf:
            field_name = new_member_conf["field"]
            fields[field_name] = (
                new_member_conf.get("create_value", "Oui")
                if is_create
                else new_member_conf.get("update_value", "Non")
            )

        first_year_conf = self.computed_fields.get("first_year_subscription")
        if first_year_conf and "field" in first_year_conf:
            field_name = first_year_conf["field"]
            fallback = first_year_conf.get("fallback_value")

            existing_value = (
                existing_record.get("fields", {}).get(field_name)
                if existing_record
                else None
            )

            if existing_value:
                # Curated value on Airtable wins, even over a HelloAsso "Oui" → year.
                # Drop the field from the payload so the PATCH doesn't touch it.
                fields.pop(field_name, None)
            elif field_name not in fields or not fields[field_name]:
                # No existing value AND no HelloAsso year → use fallback if configured.
                if fallback:
                    fields[field_name] = fallback

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

            # Try to find existing record (also used for linked-record merge)
            existing_record = self.find_record_by_email(email)

            # Resolve any configured linked-record fields (Groupe(s), Structure(s), …)
            # before sending. Merges with existing IDs on UPDATE.
            if self.linked_records:
                self._apply_linked_records(fields, existing_record)

            # Apply create/update-aware computed fields (Nouvel Adherent, fallback year, …)
            if self.computed_fields:
                self._apply_computed_fields(fields, existing_record)

            if existing_record:
                return self.update_record(existing_record["id"], fields)
            else:
                return self.create_record(fields)
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to upsert record for {email}: {e}",
            )
            print(f"DEBUG - Failed to upsert record for {email}: {e}", file=sys.stderr)
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
