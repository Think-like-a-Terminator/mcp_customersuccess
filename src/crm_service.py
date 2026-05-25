"""CRM integration service — read-only sync from Salesforce and HubSpot.

Pulls Account / Contact data into the local `customers` table so the MCP tools
(CTAs, health scores, risk alerts) always have up-to-date account information.

Supported CRMs
--------------
* **Salesforce** — uses ``simple_salesforce`` (pip install simple-salesforce)
  Set: SALESFORCE_USERNAME, SALESFORCE_PASSWORD, SALESFORCE_SECURITY_TOKEN
  Optionally set SALESFORCE_DOMAIN=test for sandboxes.

* **HubSpot** — uses the official ``hubspot-api-client`` (pip install hubspot-api-client)
  Set: HUBSPOT_API_KEY
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def _ok(upserted: int, source: str) -> dict:
    return {
        "success": True,
        "source": source,
        "upserted": upserted,
        "message": f"Synced {upserted} account(s) from {source}.",
    }


def _err(source: str, exc: Exception) -> dict:
    return {
        "success": False,
        "source": source,
        "error": str(exc),
        "error_type": type(exc).__name__,
    }


# ---------------------------------------------------------------------------
# Database upsert helper
# ---------------------------------------------------------------------------

def _upsert_accounts(rows: list[dict]) -> int:
    """Upsert a list of account dicts into the customers table."""
    from src.db_service import DatabaseService

    if not rows:
        return 0

    db = DatabaseService()
    count = 0
    for row in rows:
        query = """
            INSERT INTO customers (account_id, name, email, status, updated_at)
            VALUES (%(account_id)s, %(name)s, %(email)s, %(status)s, NOW())
            ON CONFLICT (account_id) DO UPDATE
                SET name       = EXCLUDED.name,
                    email      = EXCLUDED.email,
                    status     = EXCLUDED.status,
                    updated_at = NOW()
        """
        db.execute_query(query, row)
        count += 1

    return count


# ---------------------------------------------------------------------------
# Salesforce
# ---------------------------------------------------------------------------

class SalesforceSync:
    """Syncs Salesforce Accounts into the customers table."""

    def __init__(
        self,
        username: str,
        password: str,
        security_token: str,
        domain: str = "login",
    ):
        self.username = username
        self.password = password
        self.security_token = security_token
        self.domain = domain

    def _connect(self):
        try:
            from simple_salesforce import Salesforce  # type: ignore
        except ImportError:
            raise RuntimeError(
                "simple_salesforce is not installed. "
                "Run: pip install simple-salesforce"
            )
        return Salesforce(
            username=self.username,
            password=self.password,
            security_token=self.security_token,
            domain=self.domain,
        )

    def sync(self, limit: int = 200) -> dict:
        """
        Pull active Accounts from Salesforce and upsert into customers.

        Fetches: Id, Name, Website, Type, AccountNumber fields.
        Maps AccountNumber (or Id) → account_id, Name → name,
        Website → email fallback (uses <id>@salesforce.sync if none).

        Args:
            limit: Maximum number of accounts to sync (default 200)

        Returns:
            Sync result dict
        """
        try:
            sf = self._connect()
            soql = (
                f"SELECT Id, Name, Website, Type, AccountNumber "
                f"FROM Account "
                f"WHERE IsDeleted = false "
                f"ORDER BY LastModifiedDate DESC "
                f"LIMIT {limit}"
            )
            result = sf.query(soql)
            records = result.get("records", [])

            rows: list[dict] = []
            for rec in records:
                account_id = rec.get("AccountNumber") or rec["Id"]
                name = rec.get("Name", "Unknown")
                website = rec.get("Website") or ""
                email = website.lstrip("https://").lstrip("http://").rstrip("/") or f"{rec['Id']}@salesforce.sync"
                rows.append({
                    "account_id": f"sf-{account_id}",
                    "name": name,
                    "email": email,
                    "status": "active",
                })

            upserted = _upsert_accounts(rows)
            return _ok(upserted, "salesforce")

        except Exception as exc:
            logger.error("Salesforce sync failed: %s", exc)
            return _err("salesforce", exc)


# ---------------------------------------------------------------------------
# HubSpot
# ---------------------------------------------------------------------------

class HubSpotSync:
    """Syncs HubSpot Companies into the customers table."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _client(self):
        try:
            import hubspot  # type: ignore
            from hubspot.crm.companies import ApiClient, Configuration  # type: ignore
        except ImportError:
            raise RuntimeError(
                "hubspot-api-client is not installed. "
                "Run: pip install hubspot-api-client"
            )
        config = hubspot.Configuration(access_token=self.api_key)
        return hubspot.Client.create(access_token=self.api_key)

    def sync(self, limit: int = 200) -> dict:
        """
        Pull active Companies from HubSpot and upsert into customers.

        Fetches: id, name, domain properties.

        Args:
            limit: Maximum number of companies to sync (default 200)

        Returns:
            Sync result dict
        """
        try:
            client = self._client()
            response = client.crm.companies.basic_api.get_page(
                limit=min(limit, 100),
                properties=["name", "domain", "hs_object_id"],
            )
            results = response.results or []

            rows: list[dict] = []
            for company in results:
                props = company.properties or {}
                hs_id = str(company.id)
                name = props.get("name") or "Unknown"
                domain = props.get("domain") or f"{hs_id}@hubspot.sync"
                rows.append({
                    "account_id": f"hs-{hs_id}",
                    "name": name,
                    "email": domain,
                    "status": "active",
                })

            upserted = _upsert_accounts(rows)
            return _ok(upserted, "hubspot")

        except Exception as exc:
            logger.error("HubSpot sync failed: %s", exc)
            return _err("hubspot", exc)


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def get_crm_syncer(crm: str) -> Any:
    """
    Return a configured CRM syncer for the given platform name.

    Args:
        crm: "salesforce" or "hubspot"

    Returns:
        SalesforceSync or HubSpotSync instance

    Raises:
        ValueError: if the CRM is unknown or not configured
        RuntimeError: if required credentials are missing
    """
    from src.config import settings

    crm = crm.lower().strip()

    if crm == "salesforce":
        if not settings.salesforce_configured:
            raise ValueError(
                "Salesforce credentials not configured. "
                "Set SALESFORCE_USERNAME, SALESFORCE_PASSWORD, and SALESFORCE_SECURITY_TOKEN."
            )
        return SalesforceSync(
            username=settings.salesforce_username,
            password=settings.salesforce_password,
            security_token=settings.salesforce_security_token,
            domain=settings.salesforce_domain,
        )

    if crm == "hubspot":
        if not settings.hubspot_configured:
            raise ValueError(
                "HubSpot API key not configured. Set HUBSPOT_API_KEY."
            )
        return HubSpotSync(api_key=settings.hubspot_api_key)

    raise ValueError(f"Unknown CRM '{crm}'. Supported values: salesforce, hubspot")
