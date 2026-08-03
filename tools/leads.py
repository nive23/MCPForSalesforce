"""
Lead Operations
Handles Salesforce Lead creation, campaign membership, and lead conversion
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
from xml.sax.saxutils import escape

import requests

from simple_salesforce import SFType
from simple_salesforce.exceptions import (
    SalesforceError,
    SalesforceExpiredSession,
    SalesforceResourceNotFound,
)

import salesforce_config as _sf_cfg
from salesforce_config import get_salesforce


def invalidate_salesforce_session() -> None:
    """
    Clear cached JWT Salesforce client so the next get_salesforce() re-authenticates.
    Uses salesforce_config.invalidate_salesforce_session when present; otherwise clears
    module globals (works with older deployed salesforce_config.py that lacks the helper).
    """
    fn = getattr(_sf_cfg, "invalidate_salesforce_session", None)
    if callable(fn):
        fn()
    else:
        setattr(_sf_cfg, "_sf_client", None)
        setattr(_sf_cfg, "_auth_time", None)

# Apex REST lead convert (same Bearer as Data API). Path segment after /services/apexrest/
DEFAULT_APEX_CONVERT_LEAD_PATH = "convertLead"
# Bump when lead-convert logic changes so Azure deploys can be verified via / or convert response.
LEAD_CONVERT_BUILD = "2025-06-06-convert-v5-no-dup-json-keys"

# Custom metadata aligned with ConvertLeadApex (adjust if your org uses different API names)
LEAD_PRODUCT_OBJECT = "Lead_Product__c"
LEAD_PRODUCT_LEAD_FIELD = "Lead__c"
LEAD_PRODUCT_PRODUCT_FIELD = "Product__c"
LEAD_PRODUCT_QUANTITY_FIELD = "Quantity__c"
# Default Lead owner when not overridden (env SF_DEFAULT_LEAD_OWNER_ID or SF_DEFAULT_LEAD_OWNER_NAME)
DEFAULT_LEAD_OWNER_NAME = "Anand S"
_WORD_TO_QTY: Dict[str, float] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
}
_RE_LEADING_NUMBER = re.compile(r"^(\d+(?:\.\d+)?)\s+(.+)$")
OPPORTUNITY_PLATFORM_EVENT_OBJECT = "Opportunity_PlatformEvent__e"
OPPORTUNITY_PLATFORM_EVENT_OPP_FIELD = "OpportunityId__c"

def get_lead_tools() -> List[Dict[str, Any]]:
    """Return list of lead-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_CREATE_LEAD",
            "description": (
                "Creates a new lead; parses product_description into Product2 + Lead_Product__c rows "
                "(e.g. 'One Basic Laptop Bundle' -> qty 1, product Basic Laptop Bundle). "
                "Comma-separated values create multiple Lead_Product__c records. "
                "Owner defaults to Anand S: prefer SF_DEFAULT_LEAD_OWNER_USERNAME (exact User.Username) "
                "or SF_DEFAULT_LEAD_OWNER_ID; else User.Name match. After create, OwnerId is verified and "
                "PATCHed once if Salesforce stored a different owner."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "last_name": {
                        "type": "string",
                        "description": "Lead last name (required)"
                    },
                    "company": {
                        "type": "string",
                        "description": "Company name (optional). If omitted, a placeholder is sent so Salesforce orgs that require Company still accept the record."
                    },
                    "first_name": {
                        "type": "string",
                        "description": "Lead first name (required)"
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address (required)"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Phone number"
                    },
                    "title": {
                        "type": "string",
                        "description": "Job title"
                    },
                    "rating": {
                        "type": "string",
                        "description": "Lead rating (e.g., Hot, Warm, Cold)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Lead status (e.g., Open, Contacted, Qualified)"
                    },
                    "lead_source": {
                        "type": "string",
                        "description": "Lead source"
                    },
                    "street": {
                        "type": "string",
                        "description": "Street address"
                    },
                    "city": {
                        "type": "string",
                        "description": "City"
                    },
                    "state": {
                        "type": "string",
                        "description": "State"
                    },
                    "postal_code": {
                        "type": "string",
                        "description": "Postal code"
                    },
                    "country": {
                        "type": "string",
                        "description": "Country"
                    },
                    "website": {
                        "type": "string",
                        "description": "Website URL"
                    },
                    "industry": {
                        "type": "string",
                        "description": "Industry"
                    },
                    "annual_revenue": {
                        "type": "number",
                        "description": "Annual revenue (required), numeric only e.g. 10000 for 10,000"
                    },
                    "product_description": {
                        "type": "string",
                        "description": (
                            "Required. Stored on Lead Product_Description__c. Also parsed to create "
                            "Lead_Product__c rows: optional leading quantity (word or number) then product "
                            "name matching Product2.Name (e.g. 'One Basic Laptop Bundle'). "
                            "Multiple entries: comma-separated (e.g. 'One Basic Laptop Bundle, 2 USB Hub')."
                        ),
                    },
                    "owner_id": {
                        "type": "string",
                        "description": "Optional 15/18 char User Id for Lead OwnerId. Overrides env defaults.",
                    },
                    "Product_Description__c": {
                        "type": "string",
                        "description": "Custom field: Product Description (API name Product_Description__c). Use this or product_description."
                    },
                    "custom_fields": {
                        "type": "object",
                        "description": "Additional custom fields as key-value pairs"
                    }
                },
                "required": ["first_name", "last_name", "email", "annual_revenue", "product_description"]
            }
        },
        {
            "name": "SALESFORCE_ADD_LEAD_TO_CAMPAIGN",
            "description": "Adds a lead to a campaign by creating a CampaignMember record, allowing you to track campaign engagement.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "lead_id": {
                        "type": "string",
                        "description": "Lead ID (required)"
                    },
                    "campaign_id": {
                        "type": "string",
                        "description": "Campaign ID (required)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Campaign member status (e.g., Sent, Responded, Opted Out)"
                    },
                    "custom_fields": {
                        "type": "object",
                        "description": "Additional custom fields as key-value pairs"
                    }
                },
                "required": ["lead_id", "campaign_id"]
            }
        },
        {
            "name": "SALESFORCE_DELETE_LEAD",
            "description": "Permanently deletes a lead from Salesforce. This action cannot be undone.",
            "inputSchema": {"type": "object", "properties": {"lead_id": {"type": "string"}}, "required": ["lead_id"]}
        },
        {
            "name": "SALESFORCE_GET_LEAD",
            "description": (
                "Retrieves one Lead by Id via SOQL (standard fields). "
                "Accepts lead_id, leadId, or id. Alias tool name: SALESFORCE_GET_LEADS."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "15 or 18 character Lead Id"},
                    "leadId": {"type": "string", "description": "Same as lead_id (alternate key)"},
                    "id": {"type": "string", "description": "Same as lead_id (alternate key)"},
                },
                "description": "Provide lead_id, leadId, or id (at least one).",
            },
        },
        {
            "name": "SALESFORCE_GET_LEADS",
            "description": "Alias of SALESFORCE_GET_LEAD — fetches one Lead by Id (not a list).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string"},
                    "leadId": {"type": "string"},
                    "id": {"type": "string"},
                },
                "description": "Provide lead_id, leadId, or id (at least one).",
            },
        },
        {
            "name": "SALESFORCE_LIST_LEADS",
            "description": "Lists leads from Salesforce using SOQL query.",
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}
        },
        {
            "name": "SALESFORCE_SEARCH_LEADS",
            "description": "Search for Salesforce leads using name, email, phone, company, title, status, or lead source.",
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "company": {"type": "string"}, "title": {"type": "string"}, "status": {"type": "string"}, "lead_source": {"type": "string"}, "limit": {"type": "integer"}, "fields": {"type": "string"}}
            }
        },
        {
            "name": "SALESFORCE_UPDATE_LEAD",
            "description": "Updates an existing lead in Salesforce with the specified changes.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string"},
                    "first_name": {"type": "string"}, "last_name": {"type": "string"}, "company": {"type": "string"},
                    "email": {"type": "string"}, "phone": {"type": "string"}, "title": {"type": "string"},
                    "street": {"type": "string"}, "city": {"type": "string"}, "state": {"type": "string"},
                    "postal_code": {"type": "string"}, "country": {"type": "string"}, "website": {"type": "string"},
                    "industry": {"type": "string"}, "rating": {"type": "string"}, "status": {"type": "string"},
                    "lead_source": {"type": "string"}, "description": {"type": "string"},
                    "annual_revenue": {"type": "number"}, "number_of_employees": {"type": "integer"},
                    "product_description": {"type": "string"}, "custom_fields": {"type": "object"}
                },
                "required": ["lead_id"]
            }
        },
        {
            "name": "SALESFORCE_CONVERT_LEAD",
            "description": (
                "Converts a lead to an Opportunity (and Contact). By default creates a new Account "
                "named FirstName + LastName (Lead.Company is set to that before convert). Pass "
                "account_id only to attach to an existing Account instead of creating a new one. "
                "Always creates an Opportunity named after the lead unless do_not_create_opportunity=true. "
                "Then standard price book, Lead_Product__c line items, and Opportunity_PlatformEvent__e. "
                "Uses org Apex ConvertLeadRestApi at /services/apexrest/convertLead (see LEAD_CONVERT_SETUP.md), "
                "then REST LeadConvert, then Partner SOAP."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "15 or 18 character Lead Id"},
                    "leadId": {"type": "string", "description": "Same as lead_id"},
                    "id": {"type": "string", "description": "Same as lead_id"},
                    "account_id": {
                        "type": "string",
                        "description": (
                            "Existing Account Id (15/18 char). When set, Salesforce links the "
                            "converted Opportunity to this account and does not create a new Account."
                        ),
                    },
                    "accountId": {"type": "string", "description": "Same as account_id"},
                    "contact_id": {
                        "type": "string",
                        "description": "Optional existing Contact Id to link on convert.",
                    },
                    "contactId": {"type": "string", "description": "Same as contact_id"},
                    "do_not_create_opportunity": {
                        "type": "boolean",
                        "description": "If true, only convert to Account/Contact (default false).",
                    },
                },
                "description": "Provide lead_id, leadId, or id. Prefer account_id when the lead should not create a new Account.",
            },
        },
    ]

def _normalize_lead_id_in_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Copy args and set lead_id from common alternate keys (MCP / LLM naming)."""
    out = dict(arguments or {})
    if out.get("lead_id") and str(out["lead_id"]).strip():
        out["lead_id"] = str(out["lead_id"]).strip()
        return out
    for alt in (
        "leadId",
        "Lead_Id",
        "LeadId",
        "salesforce_lead_id",
        "record_id",
        "RecordId",
        "id",
        "Id",
        "ID",
    ):
        v = out.get(alt)
        if v is not None and str(v).strip():
            out["lead_id"] = str(v).strip()
            break
    return out


def _normalize_convert_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize lead_id plus optional account_id / contact_id for convert."""
    out = _normalize_lead_id_in_arguments(arguments if isinstance(arguments, dict) else {})
    for alt, target in (
        ("accountId", "account_id"),
        ("AccountId", "account_id"),
        ("existing_account_id", "account_id"),
        ("ExistingAccountId", "account_id"),
        ("contactId", "contact_id"),
        ("ContactId", "contact_id"),
        ("existing_contact_id", "contact_id"),
    ):
        if out.get(target) and str(out[target]).strip():
            out[target] = str(out[target]).strip()
            continue
        v = out.get(alt)
        if v is not None and str(v).strip():
            out[target] = str(v).strip()
    dnc = out.get("do_not_create_opportunity")
    if dnc is None:
        dnc = out.get("doNotCreateOpportunity")
    if dnc is not None:
        out["do_not_create_opportunity"] = bool(dnc)
    return out


def _account_name_from_lead_person(lead_row: Dict[str, Any]) -> str:
    """New Account name on convert: always Lead FirstName + LastName."""
    first = (lead_row.get("FirstName") or "").strip()
    last = (lead_row.get("LastName") or "").strip()
    person = f"{first} {last}".strip() or (lead_row.get("Name") or "").strip()
    return person or "Unknown Account"


def _set_lead_company_for_new_account_convert(
    sf: Any, lead_id: str, lead_row: Dict[str, Any]
) -> str:
    """
    Before convert (new Account path), set Lead.Company to FirstName + LastName so
    Salesforce creates Account with that name. Returns the company value applied.
    """
    new_company = _account_name_from_lead_person(lead_row)
    current = (lead_row.get("Company") or "").strip()
    if current == new_company:
        return new_company
    lead_sf = SFType("Lead", sf.session_id, sf.sf_instance)
    lead_sf.update(lead_id, {"Company": new_company})
    print(
        f"[Lead] Set Company for new Account on convert: {current!r} -> {new_company!r}",
        file=sys.stderr,
    )
    return new_company


def _query_lead_row_by_id(sf: Any, lead_id: str) -> Optional[Dict[str, Any]]:
    """Single Lead row by Id (standard fields only). Shared by get_lead and convert."""
    esc = _lead_escape(str(lead_id).strip())
    q = (
        "SELECT Id, Name, FirstName, LastName, Company, Email, Phone, MobilePhone, "
        "Street, City, State, PostalCode, Country, Status, LeadSource, Rating, "
        "Title, Industry, AnnualRevenue, NumberOfEmployees, Website, Description, "
        "IsConverted, ConvertedAccountId, ConvertedContactId, ConvertedOpportunityId, "
        "OwnerId, CreatedDate, LastModifiedDate "
        f"FROM Lead WHERE Id = '{esc}' LIMIT 1"
    )
    result = sf.query(q)
    recs = result.get("records") or []
    return recs[0] if recs else None


def handle_lead_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle lead-related tool calls"""
    args = _normalize_lead_id_in_arguments(arguments if isinstance(arguments, dict) else {})
    sf = get_salesforce()
    if tool_name == "SALESFORCE_CREATE_LEAD":
        return create_lead(sf, args)
    if tool_name == "SALESFORCE_ADD_LEAD_TO_CAMPAIGN":
        return add_lead_to_campaign(sf, args)
    if tool_name == "SALESFORCE_DELETE_LEAD":
        return delete_lead(sf, args)
    if tool_name in ("SALESFORCE_GET_LEAD", "SALESFORCE_GET_LEADS"):
        return get_lead(sf, args)
    if tool_name == "SALESFORCE_LIST_LEADS":
        return list_leads(sf, args)
    if tool_name == "SALESFORCE_SEARCH_LEADS":
        return search_leads(sf, args)
    if tool_name == "SALESFORCE_UPDATE_LEAD":
        return update_lead(sf, args)
    if tool_name == "SALESFORCE_CONVERT_LEAD":
        return convert_lead(sf, args)
    raise ValueError(f"Unknown lead tool: {tool_name}")

def create_lead(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new lead in Salesforce"""
    try:
        last_name = arguments.get("last_name")
        first_name = arguments.get("first_name")
        email = arguments.get("email")
        annual_revenue = arguments.get("annual_revenue")
        product_description = arguments.get("product_description") or arguments.get("Product_Description__c")

        if not last_name or not str(last_name).strip():
            raise ValueError("Lead last name is required")
        if not first_name or not str(first_name).strip():
            raise ValueError("Lead first name is required")
        if not email or not str(email).strip():
            raise ValueError("Email is required")
        if annual_revenue is None:
            raise ValueError("Annual revenue is required")
        if not product_description or not str(product_description).strip():
            raise ValueError("Product description is required")

        pd_text = str(product_description).strip()
        segments = _parse_product_description_segments(pd_text)
        if not segments:
            raise ValueError(
                "Product description must list at least one product (e.g. 'One Basic Laptop Bundle')."
            )
        resolved_products: List[Tuple[float, str, str]] = []
        for qty, pname in segments:
            pid = _query_product2_id_by_name(sf, pname)
            if not pid:
                raise ValueError(
                    f"No active Product2 found with Name matching '{pname}' (check Product2.Name in Salesforce)."
                )
            resolved_products.append((qty, pname, pid))

        owner_user = _resolve_lead_owner_user(sf, arguments)
        owner_id = owner_user["id"]

        company_raw = arguments.get("company")
        company = str(company_raw).strip() if company_raw is not None else ""
        if not company:
            company = f"{str(first_name).strip()} {str(last_name).strip()}".strip() or "(Not specified)"

        lead_data = {
            "LastName": str(last_name).strip(),
            "FirstName": str(first_name).strip(),
            "Company": company,
            "Email": str(email).strip(),
            "AnnualRevenue": annual_revenue,
            "Product_Description__c": pd_text,
        }

        optional_fields = [
            "phone", "title", "rating", "status",
            "lead_source", "street", "city", "state", "postal_code",
            "country", "website", "industry"
        ]
        
        for field in optional_fields:
            value = arguments.get(field)
            if value is not None:
                if field == "lead_source":
                    sf_field = "LeadSource"
                elif field == "postal_code":
                    sf_field = "PostalCode"
                else:
                    sf_field = field[0].upper() + field[1:] if field else field
                lead_data[sf_field] = value

        custom_fields = arguments.get("custom_fields", {})
        if custom_fields:
            lead_data.update(custom_fields)

        lead_data["Product_Description__c"] = pd_text
        lead_data["OwnerId"] = owner_id

        # Create lead
        lead_sf = SFType('Lead', sf.session_id, sf.sf_instance)
        result = lead_sf.create(lead_data)

        lead_id = result["id"]
        print(
            f"[Lead] Created lead: {lead_id} owner={owner_id} "
            f"user.Name={owner_user.get('Name')!r} Username={owner_user.get('Username')!r}",
            file=sys.stderr,
        )

        owner_sync = _ensure_lead_owner_matches(sf, lead_id, owner_id)
        if owner_sync.get("patched"):
            print(
                f"[Lead] Owner after PATCH: {owner_sync.get('after')}",
                file=sys.stderr,
            )

        lp_ids, lp_details = _create_lead_product_rows_resolved(sf, lead_id, resolved_products)
        print(f"[Lead] Created {len(lp_ids)} Lead_Product__c row(s) for lead {lead_id}", file=sys.stderr)

        out: Dict[str, Any] = {
            "success": True,
            "lead_id": lead_id,
            "owner_id": owner_id,
            "owner_resolved_name": owner_user.get("Name") or None,
            "owner_resolved_username": owner_user.get("Username") or None,
            "lead_owner_after_create": owner_sync.get("after"),
            "owner_patched_after_create": bool(owner_sync.get("patched")),
            "lead_product_ids": lp_ids,
            "lead_products": lp_details,
            "message": f"Lead '{str(first_name).strip()} {str(last_name).strip()}' created successfully",
        }
        if owner_sync.get("before"):
            out["lead_owner_before_patch"] = owner_sync.get("before")
        if owner_sync.get("patch_error"):
            out["owner_patch_error"] = owner_sync["patch_error"]
        return out
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Lead ERROR] {error_msg}", file=sys.stderr)
        return {
            "success": False,
            "error": error_msg
        }

def add_lead_to_campaign(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Add a lead to a campaign (fails if already a member). Both campaign_id and lead_id must be valid Salesforce IDs."""
    try:
        arguments = _normalize_lead_id_in_arguments(arguments if isinstance(arguments, dict) else {})
        lead_id = arguments.get("lead_id")
        campaign_id = arguments.get("campaign_id")
        if not lead_id:
            raise ValueError("Lead ID is required")
        if not campaign_id:
            raise ValueError("Campaign ID is required")
        # Pre-check: lead already in campaign?
        existing = sf.query(f"SELECT Id FROM CampaignMember WHERE LeadId = '{str(lead_id).replace(chr(39), chr(39)+chr(39))}' AND CampaignId = '{str(campaign_id).replace(chr(39), chr(39)+chr(39))}' LIMIT 1")
        if existing.get("records"):
            return {"success": False, "error": "Lead is already a member of this campaign"}
        member_data = {
            "LeadId": lead_id,
            "CampaignId": campaign_id
        }
        
        # Add optional status
        status = arguments.get("status")
        if status:
            member_data["Status"] = status
        
        # Add custom fields
        custom_fields = arguments.get("custom_fields", {})
        if custom_fields:
            member_data.update(custom_fields)
        
        # Create campaign member
        member_sf = SFType('CampaignMember', sf.session_id, sf.sf_instance)
        result = member_sf.create(member_data)
        
        member_id = result["id"]
        print(f"[CampaignMember] Added lead {lead_id} to campaign {campaign_id}", file=sys.stderr)
        
        return {
            "success": True,
            "campaign_member_id": member_id,
            "lead_id": lead_id,
            "campaign_id": campaign_id,
            "message": "Lead added to campaign successfully"
        }
    
    except Exception as e:
        error_msg = str(e)
        print(f"[CampaignMember ERROR] {error_msg}", file=sys.stderr)
        return {"success": False, "error": error_msg}


def delete_lead(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        arguments = _normalize_lead_id_in_arguments(arguments if isinstance(arguments, dict) else {})
        lead_id = arguments.get("lead_id")
        if not lead_id:
            raise ValueError("lead_id is required")
        lead_sf = SFType("Lead", sf.session_id, sf.sf_instance)
        lead_sf.delete(lead_id)
        return {"success": True, "message": "Lead deleted"}
    except Exception as e:
        print(f"[Lead ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def get_lead(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch one Lead by Id using SOQL (bounded standard fields).
    Avoids SObject GET returning huge/unserializable payloads and matches typical FLS.
    """
    try:
        args = _normalize_lead_id_in_arguments(arguments if isinstance(arguments, dict) else {})
        lead_id = args.get("lead_id")
        if not lead_id:
            return {
                "success": False,
                "error": "Provide lead_id, leadId, or id for the Lead to fetch.",
            }
        rec = _query_lead_row_by_id(sf, str(lead_id))
        if not rec:
            return {"success": False, "error": f"No Lead found with Id {lead_id}"}
        return {"success": True, "record": rec}
    except Exception as e:
        print(f"[Lead ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def list_leads(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        query = arguments.get("query") or "SELECT Id, Name, Company, Email, Status FROM Lead LIMIT 2000"
        result = sf.query(str(query).strip())
        return {"success": True, "records": result.get("records", []), "totalSize": result.get("totalSize", 0), "done": result.get("done", True), "nextRecordsUrl": result.get("nextRecordsUrl")}
    except Exception as e:
        print(f"[Lead ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def _lead_escape(s: str) -> str:
    return str(s).replace("'", "''")


def _parse_one_product_segment(segment: str) -> Tuple[float, str]:
    """
    'One Basic Laptop Bundle' -> (1.0, 'Basic Laptop Bundle')
    '2 USB Hub' -> (2.0, 'USB Hub')
    'Basic Laptop Bundle' -> (1.0, 'Basic Laptop Bundle')  # no leading qty => 1
    """
    raw = " ".join(str(segment).strip().split())
    if not raw:
        return 1.0, ""
    m = _RE_LEADING_NUMBER.match(raw)
    if m:
        try:
            return float(m.group(1)), str(m.group(2)).strip()
        except ValueError:
            pass
    parts = raw.split(None, 1)
    w0 = parts[0].lower()
    if w0 in _WORD_TO_QTY:
        qty = float(_WORD_TO_QTY[w0])
        name = parts[1].strip() if len(parts) > 1 else ""
        return qty, name
    return 1.0, raw


def _parse_product_description_segments(product_description: str) -> List[Tuple[float, str]]:
    """Split on commas; each segment -> (quantity, product_name)."""
    out: List[Tuple[float, str]] = []
    for piece in str(product_description).split(","):
        qty, pname = _parse_one_product_segment(piece)
        pname = pname.strip()
        if pname:
            out.append((qty, pname))
    return out


def _query_product2_id_by_name(sf: Any, product_name: str) -> Optional[str]:
    """Resolve active Product2 Id by Name (exact, then case-insensitive within LIKE prefix scan)."""
    n = " ".join(str(product_name).strip().split())
    if not n:
        return None
    esc = _lead_escape(n)
    q = (
        f"SELECT Id, Name FROM Product2 WHERE IsActive = true AND Name = '{esc}' LIMIT 1"
    )
    r = sf.query(q)
    recs = r.get("records") or []
    if recs:
        return str(recs[0]["Id"])
    first = n.split()[0][:40] if n.split() else n[:40]
    esc_first = _lead_escape(first)
    q2 = (
        f"SELECT Id, Name FROM Product2 WHERE IsActive = true AND Name LIKE '{esc_first}%' LIMIT 200"
    )
    r2 = sf.query(q2)
    want = n.casefold()
    for row in r2.get("records") or []:
        nm = (row.get("Name") or "").strip()
        if nm.casefold() == want:
            return str(row["Id"])
    return None


def _resolve_lead_owner_user(sf: Any, arguments: Dict[str, Any]) -> Dict[str, str]:
    """
    Resolve Lead Owner User. Returns dict: id, Name, Username (for logs and API response).
    Precedence: owner_id / OwnerId, SF_DEFAULT_LEAD_OWNER_ID, SF_DEFAULT_LEAD_OWNER_USERNAME,
    User.Name = SF_DEFAULT_LEAD_OWNER_NAME, then FirstName + LastName split on last token.
    """
    oid = arguments.get("owner_id") or arguments.get("OwnerId")
    if oid and str(oid).strip():
        uid = str(oid).strip()
        row = _query_user_row_by_id(sf, uid)
        if row:
            return {
                "id": uid,
                "Name": str(row.get("Name") or ""),
                "Username": str(row.get("Username") or ""),
            }
        return {"id": uid, "Name": "", "Username": ""}

    env_id = os.getenv("SF_DEFAULT_LEAD_OWNER_ID", "").strip()
    if env_id:
        row = _query_user_row_by_id(sf, env_id)
        if row:
            return {
                "id": env_id,
                "Name": str(row.get("Name") or ""),
                "Username": str(row.get("Username") or ""),
            }
        return {"id": env_id, "Name": "", "Username": ""}

    uname = os.getenv("SF_DEFAULT_LEAD_OWNER_USERNAME", "").strip()
    if uname:
        esc = _lead_escape(uname)
        q = (
            f"SELECT Id, Name, Username FROM User WHERE Username = '{esc}' "
            f"AND IsActive = true LIMIT 1"
        )
        res = sf.query(q)
        recs = res.get("records") or []
        if not recs:
            raise ValueError(
                f"No active User with Username = '{uname}'. Check SF_DEFAULT_LEAD_OWNER_USERNAME."
            )
        r = recs[0]
        return {
            "id": str(r["Id"]),
            "Name": str(r.get("Name") or ""),
            "Username": str(r.get("Username") or ""),
        }

    name = os.getenv("SF_DEFAULT_LEAD_OWNER_NAME", DEFAULT_LEAD_OWNER_NAME).strip()
    if not name:
        raise ValueError(
            "Lead owner: set owner_id, SF_DEFAULT_LEAD_OWNER_ID, SF_DEFAULT_LEAD_OWNER_USERNAME, "
            "or SF_DEFAULT_LEAD_OWNER_NAME"
        )
    esc = _lead_escape(name)
    q = (
        f"SELECT Id, Name, Username FROM User WHERE Name = '{esc}' "
        f"AND IsActive = true ORDER BY CreatedDate ASC LIMIT 5"
    )
    res = sf.query(q)
    recs = res.get("records") or []
    if len(recs) == 1:
        r = recs[0]
        return {
            "id": str(r["Id"]),
            "Name": str(r.get("Name") or ""),
            "Username": str(r.get("Username") or ""),
        }
    if len(recs) > 1:
        raise ValueError(
            f"Multiple active Users have Name = '{name}' ({len(recs)} rows). "
            "Set SF_DEFAULT_LEAD_OWNER_USERNAME or SF_DEFAULT_LEAD_OWNER_ID to pick one."
        )

    parts = name.split()
    if len(parts) >= 2:
        fn = _lead_escape(parts[0])
        ln = _lead_escape(" ".join(parts[1:]))
        q2 = (
            f"SELECT Id, Name, Username FROM User WHERE FirstName = '{fn}' "
            f"AND LastName = '{ln}' AND IsActive = true ORDER BY CreatedDate ASC LIMIT 5"
        )
        res2 = sf.query(q2)
        recs2 = res2.get("records") or []
        if len(recs2) == 1:
            r = recs2[0]
            return {
                "id": str(r["Id"]),
                "Name": str(r.get("Name") or ""),
                "Username": str(r.get("Username") or ""),
            }
        if len(recs2) > 1:
            raise ValueError(
                f"Multiple Users match FirstName/LastName for '{name}'. "
                "Set SF_DEFAULT_LEAD_OWNER_USERNAME or SF_DEFAULT_LEAD_OWNER_ID."
            )

    raise ValueError(
        f"No active User found for owner '{name}'. Set SF_DEFAULT_LEAD_OWNER_USERNAME "
        f"(recommended), SF_DEFAULT_LEAD_OWNER_ID, or owner_id on the tool call."
    )


def _query_user_row_by_id(sf: Any, user_id: str) -> Optional[Dict[str, Any]]:
    esc = _lead_escape(str(user_id).strip())
    q = f"SELECT Id, Name, Username FROM User WHERE Id = '{esc}' LIMIT 1"
    res = sf.query(q)
    recs = res.get("records") or []
    return recs[0] if recs else None


def _query_lead_owner_snapshot(sf: Any, lead_id: str) -> Dict[str, str]:
    esc = _lead_escape(str(lead_id).strip())
    q = f"SELECT Id, OwnerId, Owner.Name FROM Lead WHERE Id = '{esc}' LIMIT 1"
    res = sf.query(q)
    recs = res.get("records") or []
    if not recs:
        return {"OwnerId": "", "Owner_Name": ""}
    r = recs[0]
    owner = r.get("Owner") or {}
    return {
        "OwnerId": str(r.get("OwnerId") or ""),
        "Owner_Name": str(owner.get("Name") or ""),
    }


def _ensure_lead_owner_matches(sf: Any, lead_id: str, owner_id: str) -> Dict[str, Any]:
    """
    If Lead.OwnerId in Salesforce differs from owner_id, PATCH OwnerId once (flows may adjust it).
    Returns { patched: bool, after: snapshot dict }.
    """
    snap = _query_lead_owner_snapshot(sf, lead_id)
    want = str(owner_id).strip()
    if snap.get("OwnerId") == want:
        return {"patched": False, "after": snap}
    print(
        f"[Lead] Owner mismatch after create: stored={snap.get('OwnerId')} ({snap.get('Owner_Name')}) "
        f"wanted={want}; PATCHing OwnerId",
        file=sys.stderr,
    )
    lead_sf = SFType("Lead", sf.session_id, sf.sf_instance)
    try:
        lead_sf.update(lead_id, {"OwnerId": want})
    except Exception as ex:
        print(f"[Lead ERROR] Owner PATCH failed: {ex}", file=sys.stderr)
        return {
            "patched": False,
            "after": snap,
            "before": snap,
            "patch_error": str(ex),
        }
    snap2 = _query_lead_owner_snapshot(sf, lead_id)
    return {"patched": True, "after": snap2, "before": snap}


def _create_lead_product_rows_resolved(
    sf: Any,
    lead_id: str,
    resolved: List[Tuple[float, str, str]],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Create Lead_Product__c for each (quantity, product_name, product2_id).
    Returns (new Lead_Product__c Ids, detail dicts for API response).
    """
    lp_sf = SFType(LEAD_PRODUCT_OBJECT, sf.session_id, sf.sf_instance)
    created_ids: List[str] = []
    details: List[Dict[str, Any]] = []
    for qty, pname, pid in resolved:
        name_label = pname[:80] if len(pname) <= 80 else pname[:77] + "..."
        base_row: Dict[str, Any] = {
            LEAD_PRODUCT_LEAD_FIELD: lead_id,
            LEAD_PRODUCT_PRODUCT_FIELD: pid,
            LEAD_PRODUCT_QUANTITY_FIELD: qty,
        }
        row = dict(base_row, Name=name_label)
        try:
            res = lp_sf.create(row)
        except Exception as ex:
            err = str(ex).upper()
            if "NAME" in err or "INVALID_FIELD" in err or "DUPLICATE" in err:
                res = lp_sf.create(base_row)
            else:
                raise
        lid = str(res["id"])
        created_ids.append(lid)
        details.append(
            {
                "lead_product_id": lid,
                "product2_id": pid,
                "product_name": pname,
                "quantity": qty,
            }
        )
    return created_ids, details


def search_leads(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        limit = min(int(arguments.get("limit", 50)), 200)
        fields = arguments.get("fields") or "Id, Name, Company, Email, Status, LeadSource"
        where = []
        if arguments.get("name"):
            where.append(f"Name LIKE '%{_lead_escape(arguments['name'])}%'")
        if arguments.get("email"):
            where.append(f"Email LIKE '%{_lead_escape(arguments['email'])}%'")
        if arguments.get("phone"):
            where.append(f"Phone LIKE '%{_lead_escape(arguments['phone'])}%'")
        if arguments.get("company"):
            where.append(f"Company LIKE '%{_lead_escape(arguments['company'])}%'")
        if arguments.get("title"):
            where.append(f"Title LIKE '%{_lead_escape(arguments['title'])}%'")
        if arguments.get("status"):
            where.append(f"Status = '{_lead_escape(arguments['status'])}'")
        if arguments.get("lead_source"):
            where.append(f"LeadSource = '{_lead_escape(arguments['lead_source'])}'")
        where_clause = " AND ".join(where) if where else "Id != null"
        result = sf.query(f"SELECT {fields} FROM Lead WHERE {where_clause} LIMIT {limit}")
        return {"success": True, "records": result.get("records", []), "totalSize": result.get("totalSize", 0)}
    except Exception as e:
        print(f"[Lead ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


LEAD_UPDATE_MAP = {
    "first_name": "FirstName", "last_name": "LastName", "company": "Company", "email": "Email", "phone": "Phone",
    "title": "Title", "street": "Street", "city": "City", "state": "State", "postal_code": "PostalCode", "country": "Country",
    "website": "Website", "industry": "Industry", "rating": "Rating", "status": "Status", "lead_source": "LeadSource",
    "description": "Description", "annual_revenue": "AnnualRevenue", "number_of_employees": "NumberOfEmployees",
}


def update_lead(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        arguments = _normalize_lead_id_in_arguments(arguments if isinstance(arguments, dict) else {})
        lead_id = arguments.get("lead_id")
        if not lead_id:
            raise ValueError("lead_id is required")
        update_data = {}
        for k, sf_field in LEAD_UPDATE_MAP.items():
            v = arguments.get(k)
            if v is not None:
                update_data[sf_field] = v
        pd = arguments.get("product_description")
        if pd is not None and str(pd).strip():
            update_data["Product_Description__c"] = str(pd).strip()
        custom = arguments.get("custom_fields", {})
        if custom:
            update_data.update(custom)
        if not update_data:
            return {"success": True, "message": "No fields to update"}
        lead_sf = SFType("Lead", sf.session_id, sf.sf_instance)
        lead_sf.update(lead_id, update_data)
        return {"success": True, "lead_id": lead_id, "message": "Lead updated"}
    except Exception as e:
        print(f"[Lead ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def _soap_local_tag(tag: str) -> str:
    if not tag:
        return ""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _soap_session_id_cdata(session_id: str) -> str:
    """Embed OAuth access token in CDATA so XML special characters cannot break the envelope."""
    sid = str(session_id)
    if "]]>" in sid:
        sid = sid.replace("]]>", "]]]]><![CDATA[>")
    return sid


def _soap_first_descendant_text(root: ET.Element, local_tag: str) -> Optional[str]:
    for el in root.iter():
        if _soap_local_tag(el.tag) == local_tag and el.text:
            t = el.text.strip()
            if t:
                return t
    return None


def _soap_partner_password_login(login_base: str, api_version: str, username: str, password: str) -> Tuple[str, str]:
    """
    Partner SOAP login() with username + password (password is usually password+security_token).
    Returns (session_id, instance_hostname) for subsequent SOAP calls on the instance host.
    """
    user_cdata = _soap_session_id_cdata(username)
    pwd_cdata = _soap_session_id_cdata(password)
    url = f"{login_base.rstrip('/')}/services/Soap/u/{api_version}"
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:partner.soap.sforce.com">
  <soapenv:Body>
    <urn:login>
      <urn:username><![CDATA[{user_cdata}]]></urn:username>
      <urn:password><![CDATA[{pwd_cdata}]]></urn:password>
    </urn:login>
  </soapenv:Body>
</soapenv:Envelope>"""
    headers = {"Content-Type": "text/xml; charset=UTF-8", "SOAPAction": '""'}
    resp = requests.post(url, data=envelope.encode("utf-8"), headers=headers, timeout=60)
    if resp.status_code >= 300:
        raise RuntimeError(f"SOAP login HTTP {resp.status_code}: {resp.text[:1500]}")
    root = ET.fromstring(resp.content)
    for el in root.iter():
        if _soap_local_tag(el.tag) == "faultstring" and el.text:
            raise RuntimeError(f"SOAP login fault: {el.text.strip()}")
    sid = _soap_first_descendant_text(root, "sessionId")
    surl = _soap_first_descendant_text(root, "serverUrl")
    if not sid or not surl:
        raise RuntimeError(f"SOAP login: missing sessionId or serverUrl: {resp.text[:1500]}")
    parsed = urlparse(surl)
    host = parsed.hostname
    if not host:
        raise RuntimeError(f"SOAP login: invalid serverUrl: {surl}")
    return sid, host


def _build_partner_convert_soap_envelope(
    *,
    include_session_header: bool,
    session_id: str,
    lead_id: str,
    converted_status: str,
    opportunity_name: str,
    account_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    do_not_create_opportunity: bool = False,
) -> str:
    lid = escape(str(lead_id), entities={"'": "&apos;", '"': "&quot;"})
    cst = escape(str(converted_status), entities={"'": "&apos;", '"': "&quot;"})
    onm = escape(str(opportunity_name), entities={"'": "&apos;", '"': "&quot;"})
    acc_xml = ""
    if account_id and str(account_id).strip():
        aid = escape(str(account_id).strip(), entities={"'": "&apos;", '"': "&quot;"})
        acc_xml = f"\n        <urn:accountId>{aid}</urn:accountId>"
    con_xml = ""
    if contact_id and str(contact_id).strip():
        cid = escape(str(contact_id).strip(), entities={"'": "&apos;", '"': "&quot;"})
        con_xml = f"\n        <urn:contactId>{cid}</urn:contactId>"
    dnc_opp = "true" if do_not_create_opportunity else "false"
    if include_session_header:
        sid_cdata = _soap_session_id_cdata(session_id)
        header_xml = (
            "  <soapenv:Header>\n"
            "    <urn:SessionHeader>\n"
            f"      <urn:sessionId><![CDATA[{sid_cdata}]]></urn:sessionId>\n"
            "    </urn:SessionHeader>\n"
            "  </soapenv:Header>"
        )
    else:
        header_xml = "  <soapenv:Header/>"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:partner.soap.sforce.com">
{header_xml}
  <soapenv:Body>
    <urn:convertLead>
      <urn:leadConverts>
        <urn:leadId>{lid}</urn:leadId>
        <urn:convertedStatus>{cst}</urn:convertedStatus>
        <urn:doNotCreateOpportunity>{dnc_opp}</urn:doNotCreateOpportunity>
        <urn:overwriteLeadSource>false</urn:overwriteLeadSource>
        <urn:sendNotificationEmail>false</urn:sendNotificationEmail>{acc_xml}{con_xml}
        <urn:opportunityName>{onm}</urn:opportunityName>
      </urn:leadConverts>
    </urn:convertLead>
  </soapenv:Body>
</soapenv:Envelope>"""


def _parse_soap_convert_lead_response(
    resp: requests.Response,
    *,
    do_not_create_opportunity: bool = False,
) -> Tuple[str, str, str]:
    if resp.status_code >= 300:
        raise RuntimeError(f"SOAP convertLead HTTP {resp.status_code}: {resp.text[:2500]}")

    root = ET.fromstring(resp.content)
    fault = None
    for el in root.iter():
        if _soap_local_tag(el.tag) == "faultstring" and el.text:
            fault = el.text.strip()
            break
    if fault:
        raise RuntimeError(f"SOAP fault: {fault}")

    result_maps: List[Dict[str, str]] = []
    for el in root.iter():
        if _soap_local_tag(el.tag) != "result":
            continue
        row: Dict[str, str] = {}
        for child in el:
            ln = _soap_local_tag(child.tag)
            if child.text is not None and str(child.text).strip():
                row[ln] = str(child.text).strip()
        if row:
            result_maps.append(row)

    if not result_maps:
        raise RuntimeError(f"SOAP convertLead: no result element in response: {resp.text[:2500]}")

    r0 = result_maps[0]
    if str(r0.get("success", "")).lower() != "true":
        msgs = [m for m in (_soap_gather_messages(root)) if m]
        detail = "; ".join(msgs) if msgs else str(r0)
        raise RuntimeError(f"SOAP convertLead failed: {detail}")

    acc_id = r0.get("accountId")
    con_id = r0.get("contactId")
    opp_id = r0.get("opportunityId")
    if not acc_id or not con_id:
        raise RuntimeError(f"SOAP convertLead missing account/contact: {r0}")
    if not opp_id and not do_not_create_opportunity:
        raise RuntimeError(
            "SOAP convertLead did not return opportunityId; org may block opportunity on convert."
        )
    return acc_id, con_id, opp_id or ""


def _convert_lead_soap(
    sf: Any,
    lead_id: str,
    converted_status: str,
    opportunity_name: str,
    account_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    do_not_create_opportunity: bool = False,
) -> Tuple[str, str, str]:
    """
    Partner SOAP convertLead when REST quick action is unavailable.

    Order:
    1) If SF_SOAP_PASSWORD is set: SOAP login() with SF_USERNAME + that password (use
       password+Security Token concatenated) to obtain a real SOAP session id — works when
       JWT access tokens are rejected by Partner SOAP ("Illegal Session").
    2) OAuth Bearer on HTTP + empty SOAP header.
    3) OAuth access token in SessionHeader only.
    """
    ver = sf.sf_version
    host = sf.sf_instance
    url = f"https://{host}/services/Soap/u/{ver}"
    token = str(sf.session_id)
    base_headers = {
        "Content-Type": "text/xml; charset=UTF-8",
        "SOAPAction": '""',
    }
    errors: List[str] = []

    soap_pw = os.getenv("SF_SOAP_PASSWORD")
    if soap_pw and str(soap_pw).strip():
        try:
            login_base = getattr(_sf_cfg, "SF_LOGIN_URL", None) or os.getenv(
                "SF_LOGIN_URL", "https://login.salesforce.com"
            )
            username = getattr(_sf_cfg, "SF_USERNAME", None) or os.getenv("SF_USERNAME")
            if not username:
                raise RuntimeError("SF_USERNAME is required for SF_SOAP_PASSWORD SOAP login")
            sid, soap_host = _soap_partner_password_login(
                str(login_base), str(ver), str(username).strip(), str(soap_pw).strip()
            )
            convert_url = f"https://{soap_host}/services/Soap/u/{ver}"
            env0 = _build_partner_convert_soap_envelope(
                include_session_header=True,
                session_id=sid,
                lead_id=lead_id,
                converted_status=converted_status,
                opportunity_name=opportunity_name,
                account_id=account_id,
                contact_id=contact_id,
                do_not_create_opportunity=do_not_create_opportunity,
            )
            r0 = requests.post(convert_url, data=env0.encode("utf-8"), headers=base_headers, timeout=120)
            return _parse_soap_convert_lead_response(
                r0, do_not_create_opportunity=do_not_create_opportunity
            )
        except Exception as ex0:
            errors.append(f"soap_password_login: {ex0}")

    try:
        env1 = _build_partner_convert_soap_envelope(
            include_session_header=False,
            session_id=token,
            lead_id=lead_id,
            converted_status=converted_status,
            opportunity_name=opportunity_name,
            account_id=account_id,
            contact_id=contact_id,
            do_not_create_opportunity=do_not_create_opportunity,
        )
        h1 = dict(base_headers)
        h1["Authorization"] = f"Bearer {token}"
        r1 = requests.post(url, data=env1.encode("utf-8"), headers=h1, timeout=120)
        return _parse_soap_convert_lead_response(
            r1, do_not_create_opportunity=do_not_create_opportunity
        )
    except Exception as ex1:
        errors.append(f"bearer_header: {ex1}")

    try:
        env2 = _build_partner_convert_soap_envelope(
            include_session_header=True,
            session_id=token,
            lead_id=lead_id,
            converted_status=converted_status,
            opportunity_name=opportunity_name,
            account_id=account_id,
            contact_id=contact_id,
            do_not_create_opportunity=do_not_create_opportunity,
        )
        r2 = requests.post(url, data=env2.encode("utf-8"), headers=base_headers, timeout=120)
        return _parse_soap_convert_lead_response(
            r2, do_not_create_opportunity=do_not_create_opportunity
        )
    except Exception as ex2:
        errors.append(f"session_header: {ex2}")

    raise RuntimeError(
        "SOAP convertLead failed with all auth modes. "
        + " | ".join(errors)
        + " — Set SF_SOAP_PASSWORD (integration user password + security token) for SOAP login, "
        "or enable REST LeadConvert / add Apex REST. JWT access tokens are not accepted by "
        "Partner SOAP in this org."
    )


def _salesforce_session_should_retry(exc: BaseException) -> bool:
    """True when a fresh JWT login may fix the failure (REST 401 / expired session)."""
    if isinstance(exc, SalesforceExpiredSession):
        return True
    if isinstance(exc, SalesforceError) and getattr(exc, "status", None) == 401:
        return True
    msg = str(exc).upper()
    # SOAP Partner often returns INVALID_SESSION_ID + Illegal Session for OAuth token issues;
    # re-fetching JWT does not fix that — do not burn a retry loop.
    if "ILLEGAL SESSION" in msg:
        return False
    if "INVALID_SESSION_ID" in msg and "SOAP" in msg:
        return False
    if "SESSION_EXPIRED" in msg or "INSUFFICIENT_SESSION" in msg:
        return True
    if "INVALID_SESSION_ID" in msg:
        return True
    return False


def _soap_gather_messages(root: ET.Element) -> List[str]:
    out: List[str] = []
    for el in root.iter():
        if _soap_local_tag(el.tag) == "message" and el.text:
            t = el.text.strip()
            if t:
                out.append(t)
    return out


def _parse_lead_convert_response(resp: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Normalize Lead Convert quick-action JSON into account/contact/opportunity ids."""
    if resp is None:
        return None, None, None
    data = resp[0] if isinstance(resp, list) and resp else resp
    if not isinstance(data, dict):
        return None, None, None
    inner = data.get("outputValues") if isinstance(data.get("outputValues"), dict) else data
    acc = inner.get("accountId") or inner.get("AccountId")
    con = inner.get("contactId") or inner.get("ContactId")
    opp = inner.get("opportunityId") or inner.get("OpportunityId")
    return acc, con, opp


def _pick_sf_id(row: Dict[str, Any], *keys: str) -> Optional[str]:
    for k in keys:
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _query_lead_converted_ids(sf: Any, lead_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Read ConvertedAccountId / Contact / Opportunity from Lead after Apex convert."""
    row = _query_lead_row_by_id(sf, str(lead_id).strip())
    if not row or not row.get("IsConverted"):
        return None, None, None
    return (
        row.get("ConvertedAccountId"),
        row.get("ConvertedContactId"),
        row.get("ConvertedOpportunityId"),
    )


def _deep_scan_convert_ids(node: Any, found: Dict[str, str]) -> None:
    """Collect account/contact/opportunity ids from nested Apex JSON."""
    if isinstance(node, dict):
        for k, v in node.items():
            kl = str(k).lower()
            if isinstance(v, str) and _is_salesforce_id(v):
                if kl in ("accountid", "account_id", "accountid__c") and "account" not in found:
                    found["account"] = v
                elif kl in ("contactid", "contact_id") and "contact" not in found:
                    found["contact"] = v
                elif kl in ("opportunityid", "opportunity_id") and "opportunity" not in found:
                    found["opportunity"] = v
                elif v.startswith("001") and "account" not in found:
                    found["account"] = v
                elif v.startswith("003") and "contact" not in found:
                    found["contact"] = v
                elif v.startswith("006") and "opportunity" not in found:
                    found["opportunity"] = v
            _deep_scan_convert_ids(v, found)
    elif isinstance(node, list):
        for item in node:
            _deep_scan_convert_ids(item, found)


def _parse_apex_convert_lead_response(data: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse JSON from Apex REST (ConvertLeadRestApi / LeadConversionResponse shapes)."""
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        return None, None, None
    inner: Any = data
    for key in ("result", "data", "output", "response", "leadConversionResponse"):
        if isinstance(data.get(key), dict):
            inner = data[key]
            break
    if not isinstance(inner, dict):
        return None, None, None

    acc = _pick_sf_id(inner, "accountID", "accountId", "AccountId", "account_id")
    con = _pick_sf_id(inner, "contactID", "contactId", "ContactId", "contact_id")
    opp = _pick_sf_id(inner, "opportunityID", "opportunityId", "OpportunityId", "opportunity_id")
    if acc and con and opp:
        return acc, con, opp
    found: Dict[str, str] = {}
    _deep_scan_convert_ids(data, found)
    return (
        acc or found.get("account"),
        con or found.get("contact"),
        opp or found.get("opportunity"),
    )


def _apex_convert_payload_variants(
    lead_id: str,
    converted_status: str,
    opportunity_name: str,
    *,
    account_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    do_not_create_opportunity: bool = False,
) -> List[Dict[str, Any]]:
    """
    Request bodies for ConvertLeadRestApi / LeadConversionRequest.

    Salesforce JSON.deserialize treats property names case-insensitively for duplicates:
    sending both leadId and leadID in one body raises
    \"Duplicate field: ConvertLeadRestApi.LeadConversionRequest.leadID\".
    Each variant uses exactly one spelling of each field.
    """
    lid = str(lead_id).strip()
    cst = str(converted_status).strip()
    onm = str(opportunity_name).strip()
    create_opp = not do_not_create_opportunity
    aid = str(account_id).strip() if account_id and str(account_id).strip() else None
    cid = str(contact_id).strip() if contact_id and str(contact_id).strip() else None

    # Primary: matches ConvertLeadApex / ConvertLeadRestApi (leadID, accountID, contactID)
    primary: Dict[str, Any] = {
        "leadID": lid,
        "convertedStatus": cst,
        "createOpportunity": create_opp,
        "opportunityName": onm,
        "overWriteLeadSource": False,
        "sendEmailToOwner": False,
    }
    if aid:
        primary["accountID"] = aid
    if cid:
        primary["contactID"] = cid

    # Fallback spelling only (never combine with primary keys in the same object)
    alt: Dict[str, Any] = {
        "leadId": lid,
        "convertedStatus": cst,
        "createOpportunity": create_opp,
        "opportunityName": onm,
        "overWriteLeadSource": False,
        "sendEmailToOwner": False,
    }
    if aid:
        alt["accountId"] = aid
    if cid:
        alt["contactId"] = cid

    return [primary, alt]


def _apex_convert_rest_urls(sf: Any, path_seg: str, lead_id: str) -> List[str]:
    """URLs for @RestResource(urlMapping='/convertLead/*') and plain /convertLead."""
    base = f"https://{sf.sf_instance}/services/apexrest"
    seg = path_seg.strip().strip("/") or DEFAULT_APEX_CONVERT_LEAD_PATH
    lid = str(lead_id).strip()
    candidates = [
        f"{base}/{seg}",
        f"{base}/{seg}/",
        f"{base}/{seg}/{lid}",
    ]
    seen: set = set()
    out: List[str] = []
    for u in candidates:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _apex_response_failed(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    err = (
        data.get("errorMessage")
        or data.get("error_message")
        or data.get("message")
        or data.get("error")
        or data.get("errors")
    )
    if err and str(err).strip():
        if data.get("success") is not True and data.get("isSuccess") is not True:
            has_ids = any(
                data.get(k)
                for k in (
                    "accountID",
                    "accountId",
                    "contactID",
                    "contactId",
                    "opportunityID",
                    "opportunityId",
                )
            )
            if not has_ids:
                return str(err).strip()
    if data.get("success") is False or data.get("isSuccess") is False:
        return str(err or "Apex convertLead returned success=false")
    return None


def _resolve_convert_triplet_after_apex(
    sf: Any,
    lead_id: str,
    data: Any,
    *,
    do_not_create_opportunity: bool,
) -> Optional[Tuple[str, str, str]]:
    """Parse Apex JSON; if ids missing, read them from the converted Lead row."""
    acc, con, opp = _parse_apex_convert_lead_response(data)
    if not (acc and con) or (not do_not_create_opportunity and not opp):
        q_acc, q_con, q_opp = _query_lead_converted_ids(sf, lead_id)
        acc = acc or q_acc
        con = con or q_con
        opp = opp or q_opp
    if acc and con and (opp or do_not_create_opportunity):
        return str(acc), str(con), str(opp) if opp else ""
    return None


def _try_convert_lead_apex_rest(
    sf: Any,
    lead_id: str,
    converted_status: str,
    opportunity_name: str,
    account_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    do_not_create_opportunity: bool = False,
) -> Optional[Tuple[str, str, str]]:
    """
    POST /services/apexrest/convertLead (ConvertLeadRestApi) with OAuth Bearer.
    Returns (accountId, contactId, opportunityId) on success, None if all routes return 404.
    """
    if os.getenv("SF_APEX_CONVERT_LEAD_DISABLED", "").strip().lower() in ("1", "true", "yes"):
        return None
    path_seg = (
        os.getenv("SF_APEX_CONVERT_LEAD_PATH", DEFAULT_APEX_CONVERT_LEAD_PATH).strip().strip("/")
        or DEFAULT_APEX_CONVERT_LEAD_PATH
    )
    bodies = _apex_convert_payload_variants(
        lead_id,
        converted_status,
        opportunity_name,
        account_id=account_id,
        contact_id=contact_id,
        do_not_create_opportunity=do_not_create_opportunity,
    )
    headers = {
        "Authorization": f"Bearer {sf.session_id}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    last_404_text = ""
    last_error = ""
    saw_non_404 = False
    for body in bodies:
        for url in _apex_convert_rest_urls(sf, path_seg, lead_id):
            resp = requests.post(url, json=body, headers=headers, timeout=120)
            if resp.status_code == 404:
                last_404_text = resp.text[:500]
                print(f"[Lead] Apex convert 404 at {url}", file=sys.stderr)
                continue
            saw_non_404 = True
            if resp.status_code >= 400:
                last_error = f"HTTP {resp.status_code} at {url}: {resp.text[:1500]}"
                print(f"[Lead] Apex convert {last_error}", file=sys.stderr)
                continue
            try:
                data = resp.json()
            except ValueError:
                last_error = f"non-JSON from {url}: {resp.text[:1500]}"
                continue
            fail_msg = _apex_response_failed(data)
            if fail_msg:
                last_error = f"{fail_msg} (url={url}, body_keys={list(body.keys())})"
                print(f"[Lead] Apex convert business error: {last_error}", file=sys.stderr)
                continue
            triplet = _resolve_convert_triplet_after_apex(
                sf, lead_id, data, do_not_create_opportunity=do_not_create_opportunity
            )
            if triplet:
                print(f"[Lead] Apex convert succeeded via {url}", file=sys.stderr)
                return triplet
            last_error = f"no ids in response or on Lead after POST {url}: {data!r}"
    if saw_non_404 and last_error:
        raise RuntimeError(f"Apex convertLead: {last_error}")
    if last_404_text:
        print(f"[Lead] Apex convert last 404 body: {last_404_text}", file=sys.stderr)
    return None


def _resolve_converted_status(sf: Any, preferred: str = "Converted") -> str:
    """Pick a valid converted LeadStatus MasterLabel for this org."""
    try:
        res = sf.query(
            "SELECT MasterLabel FROM LeadStatus WHERE IsConverted = true "
            "ORDER BY SortOrder ASC LIMIT 20"
        )
        labels = [
            str(r.get("MasterLabel") or "").strip()
            for r in (res.get("records") or [])
            if r.get("MasterLabel")
        ]
        if preferred in labels:
            return preferred
        if labels:
            return labels[0]
    except Exception as ex:
        print(f"[Lead] LeadStatus query failed, using default: {ex}", file=sys.stderr)
    return preferred


def _lead_convert_unavailable_message(lead_id: str, detail: str) -> str:
    return (
        f"Lead {lead_id} could not be converted. {detail} "
        "Ensure ConvertLeadRestApi is deployed and the integration user can access it "
        "(see LEAD_CONVERT_SETUP.md), or set SF_SOAP_PASSWORD on the MCP server, then redeploy Azure."
    )


def _get_standard_pricebook_id(sf: Any) -> str:
    q = "SELECT Id FROM Pricebook2 WHERE IsStandard = true LIMIT 1"
    res = sf.query(q)
    recs = res.get("records") or []
    if not recs:
        raise RuntimeError("No standard Pricebook2 found in org")
    return recs[0]["Id"]


def _existing_opp_product_ids(sf: Any, opportunity_id: str) -> set:
    """Product2 Ids already on the opportunity (via OpportunityLineItem)."""
    q = (
        "SELECT Product2Id FROM OpportunityLineItem "
        f"WHERE OpportunityId = '{_lead_escape(opportunity_id)}'"
    )
    res = sf.query(q)
    return {
        str(r["Product2Id"])
        for r in (res.get("records") or [])
        if r.get("Product2Id")
    }


def _dedupe_lead_products_by_product(
    lead_products: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """One row per Product__c; sum Quantity__c when the same product appears twice."""
    merged: Dict[str, Dict[str, Any]] = {}
    for row in lead_products:
        prod_id = row.get(LEAD_PRODUCT_PRODUCT_FIELD)
        if not prod_id:
            continue
        pid = str(prod_id)
        qty = row.get(LEAD_PRODUCT_QUANTITY_FIELD)
        try:
            qty_f = float(qty) if qty is not None else 1.0
        except (TypeError, ValueError):
            qty_f = 1.0
        if pid in merged:
            prev = merged[pid].get(LEAD_PRODUCT_QUANTITY_FIELD) or 0
            try:
                merged[pid][LEAD_PRODUCT_QUANTITY_FIELD] = float(prev) + qty_f
            except (TypeError, ValueError):
                merged[pid][LEAD_PRODUCT_QUANTITY_FIELD] = qty_f
        else:
            merged[pid] = dict(row)
            merged[pid][LEAD_PRODUCT_QUANTITY_FIELD] = qty_f
    return list(merged.values())


def _post_convert_opportunity_extras(
    sf: Any,
    lead_id: str,
    opportunity_id: str,
    *,
    convert_via: str = "rest",
) -> Dict[str, Any]:
    """
    Standard price book, platform event, Lead_Product__c -> OpportunityLineItem.
    Skipped when convert_via is apex_rest (ConvertLeadRestApi already performs these steps).
    """
    notes: List[str] = []
    if convert_via == "apex_rest":
        notes.append(
            "Skipped post-convert pricebook, platform event, and products; "
            "ConvertLeadRestApi already applied them."
        )
        print(
            f"[Lead] Skipping post-convert extras for opp {opportunity_id} "
            "(ConvertLeadRestApi handled pricebook, event, and line items)",
            file=sys.stderr,
        )
        return {"line_items_created": 0, "line_items_skipped": 0, "notes": notes}

    line_items_created = 0
    line_items_skipped = 0
    standard_pb_id = _get_standard_pricebook_id(sf)
    opp_sf = SFType("Opportunity", sf.session_id, sf.sf_instance)
    opp_sf.update(opportunity_id, {"Pricebook2Id": standard_pb_id})

    evt_sf = SFType(OPPORTUNITY_PLATFORM_EVENT_OBJECT, sf.session_id, sf.sf_instance)
    evt_sf.create({OPPORTUNITY_PLATFORM_EVENT_OPP_FIELD: opportunity_id})

    lp_q = (
        f"SELECT {LEAD_PRODUCT_PRODUCT_FIELD}, {LEAD_PRODUCT_QUANTITY_FIELD} "
        f"FROM {LEAD_PRODUCT_OBJECT} WHERE {LEAD_PRODUCT_LEAD_FIELD} = '{_lead_escape(lead_id)}'"
    )
    lp_res = sf.query(lp_q)

    lead_products = _dedupe_lead_products_by_product(lp_res.get("records") or [])
    if not lead_products:
        return {"line_items_created": 0, "line_items_skipped": 0, "notes": notes}

    product_ids: List[str] = []
    for row in lead_products:
        pid = row.get(LEAD_PRODUCT_PRODUCT_FIELD)
        if pid:
            product_ids.append(str(pid))
    if not product_ids:
        return {"line_items_created": 0, "line_items_skipped": 0, "notes": notes}

    existing_products = _existing_opp_product_ids(sf, opportunity_id)

    in_list = ",".join(f"'{_lead_escape(x)}'" for x in product_ids)
    pbe_q = (
        f"SELECT Id, Product2Id, UnitPrice FROM PricebookEntry "
        f"WHERE Pricebook2Id = '{_lead_escape(standard_pb_id)}' AND Product2Id IN ({in_list}) "
        f"AND IsActive = true"
    )
    pbe_res = sf.query(pbe_q)
    pbe_by_product: Dict[str, Dict[str, Any]] = {}
    for pbe in pbe_res.get("records") or []:
        pbe_by_product[pbe["Product2Id"]] = pbe

    oli_sf = SFType("OpportunityLineItem", sf.session_id, sf.sf_instance)
    for row in lead_products:
        prod_id = row.get(LEAD_PRODUCT_PRODUCT_FIELD)
        if not prod_id or prod_id not in pbe_by_product:
            continue
        prod_key = str(prod_id)
        if prod_key in existing_products:
            line_items_skipped += 1
            print(
                f"[Lead] Skipping duplicate OLI for Product2 {prod_key} on opp {opportunity_id}",
                file=sys.stderr,
            )
            continue
        pbe = pbe_by_product[prod_id]
        qty = row.get(LEAD_PRODUCT_QUANTITY_FIELD)
        if qty is None:
            qty = 1
        try:
            qty = float(qty)
        except (TypeError, ValueError):
            qty = 1.0
        oli_sf.create(
            {
                "OpportunityId": opportunity_id,
                "PricebookEntryId": pbe["Id"],
                "Quantity": qty,
                "UnitPrice": pbe.get("UnitPrice") or 0,
            }
        )
        line_items_created += 1
        existing_products.add(prod_key)

    return {
        "line_items_created": line_items_created,
        "line_items_skipped": line_items_skipped,
        "notes": notes,
    }


def _convert_lead_execute(sf: Any, lead_id: str, convert_options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single attempt: Apex REST convertLead, then REST quick action LeadConvert, then SOAP
    (only if SF_SOAP_PASSWORD or SF_SOAP_ALLOW_JWT=1); then post-convert steps.
    Raises on failure so caller can retry after session refresh.
    """
    lead_row = _query_lead_row_by_id(sf, lead_id)
    if not lead_row:
        raise RuntimeError(f"No Lead found with Id {lead_id}")
    if lead_row.get("IsConverted"):
        acc0 = lead_row.get("ConvertedAccountId")
        con0 = lead_row.get("ConvertedContactId")
        opp0 = lead_row.get("ConvertedOpportunityId")
        if acc0 or con0:
            return {
                "success": True,
                "account_id": acc0,
                "contact_id": con0,
                "opportunity_id": opp0,
                "converted_status": lead_row.get("Status"),
                "opportunity_name": None,
                "convert_via": "already_converted",
                "message": "Lead was already converted.",
                "line_items_created": 0,
            }

    existing_account_id = (convert_options.get("account_id") or "").strip() or None
    existing_contact_id = (convert_options.get("contact_id") or "").strip() or None
    do_not_create_opportunity = bool(convert_options.get("do_not_create_opportunity"))

    if not existing_account_id:
        lead_row["Company"] = _set_lead_company_for_new_account_convert(sf, lead_id, lead_row)

    first = (lead_row.get("FirstName") or "").strip()
    last = (lead_row.get("LastName") or "").strip()
    lead_name = (lead_row.get("Name") or f"{first} {last}".strip() or "Lead").strip()

    converted_status = _resolve_converted_status(sf, "Converted")
    opportunity_name = lead_name

    payload: Dict[str, Any] = {
        "convertedStatus": str(converted_status).strip(),
        "overwriteLeadSource": False,
        "sendNotificationEmail": False,
        "doNotCreateOpportunity": do_not_create_opportunity,
        "opportunityName": str(opportunity_name).strip(),
    }
    if existing_account_id:
        payload["accountId"] = existing_account_id
    if existing_contact_id:
        payload["contactId"] = existing_contact_id

    path = f"sobjects/Lead/{lead_id}/actions/quick/LeadConvert"
    acc_id: Optional[str] = None
    con_id: Optional[str] = None
    opp_id: Optional[str] = None
    convert_via = "rest"

    apex_triplet = _try_convert_lead_apex_rest(
        sf,
        str(lead_id),
        converted_status,
        str(opportunity_name).strip(),
        account_id=existing_account_id,
        contact_id=existing_contact_id,
        do_not_create_opportunity=do_not_create_opportunity,
    )
    if apex_triplet:
        acc_id, con_id, opp_id = apex_triplet
        convert_via = "apex_rest"
    else:
        acc_id, con_id, opp_id = None, None, None
        soap_error = ""
        rest_error = ""
        try:
            convert_via = "soap"
            acc_id, con_id, opp_id = _convert_lead_soap(
                sf,
                str(lead_id),
                converted_status,
                str(opportunity_name).strip(),
                account_id=existing_account_id,
                contact_id=existing_contact_id,
                do_not_create_opportunity=do_not_create_opportunity,
            )
        except Exception as soap_ex:
            soap_error = str(soap_ex)
            print(f"[Lead] SOAP convertLead failed: {soap_error}", file=sys.stderr)

        if not (acc_id and con_id):
            rest_error = ""
            try:
                convert_via = "rest"
                raw = sf.restful(path, method="POST", json=payload)
                acc_id, con_id, opp_id = _parse_lead_convert_response(raw)
            except Exception as rest_ex:
                rest_error = str(rest_ex)
                print(f"[Lead] REST LeadConvert failed: {rest_error}", file=sys.stderr)

        if not (acc_id and con_id):
            q_acc, q_con, q_opp = _query_lead_converted_ids(sf, lead_id)
            if q_acc or q_con:
                acc_id, con_id, opp_id = q_acc, q_con, q_opp
                convert_via = "lead_query"
            else:
                raise RuntimeError(
                    _lead_convert_unavailable_message(
                        str(lead_id),
                        "Apex REST returned 404 or failed, SOAP and REST quick action did not convert the lead. "
                        f"SOAP: {soap_error or 'not attempted or no error captured'}. "
                        f"REST: {rest_error or 'not attempted'}. "
                        "Check Azure logs for [Lead] Apex convert lines.",
                    )
                )

    if existing_account_id:
        acc_id = acc_id or existing_account_id
    if not (acc_id and con_id):
        q_acc, q_con, q_opp = _query_lead_converted_ids(sf, lead_id)
        acc_id = acc_id or q_acc
        con_id = con_id or q_con
        opp_id = opp_id or q_opp
    if not acc_id and not con_id:
        raise RuntimeError("Lead convert returned no account or contact id")
    if not do_not_create_opportunity and not opp_id:
        _, _, q_opp = _query_lead_converted_ids(sf, lead_id)
        opp_id = opp_id or q_opp
    if not do_not_create_opportunity and not opp_id:
        raise RuntimeError(
            "Lead convert did not return an opportunity id; ensure the org allows creating "
            "an opportunity on convert, or pass account_id to link to an existing account."
        )

    result: Dict[str, Any] = {
        "success": True,
        "account_id": acc_id,
        "contact_id": con_id,
        "opportunity_id": opp_id,
        "converted_status": converted_status,
        "opportunity_name": opportunity_name,
        "convert_via": convert_via,
        "used_existing_account": bool(existing_account_id),
        "lead_convert_build": LEAD_CONVERT_BUILD,
    }
    if existing_account_id:
        result["existing_account_id"] = existing_account_id

    if opp_id:
        try:
            extras = _post_convert_opportunity_extras(
                sf, lead_id, opp_id, convert_via=convert_via
            )
            result["line_items_created"] = extras["line_items_created"]
            if extras.get("line_items_skipped"):
                result["line_items_skipped"] = extras["line_items_skipped"]
            if extras.get("notes"):
                result["notes"] = extras["notes"]
        except Exception as post_ex:
            result["post_convert_warning"] = str(post_ex)
            result["line_items_created"] = 0
    else:
        result["line_items_created"] = 0

    print(f"[Lead] Converted lead {lead_id} -> account={acc_id} contact={con_id} opp={opp_id}", file=sys.stderr)
    return result


def diagnose_lead_convert_health(sf: Any, lead_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Probe Apex REST convertLead without converting. POSTs a minimal body and reports HTTP status.
    If lead_id is provided, uses it in the payload (lead is not converted on 4xx/validation errors).
    """
    path_seg = (
        os.getenv("SF_APEX_CONVERT_LEAD_PATH", DEFAULT_APEX_CONVERT_LEAD_PATH).strip().strip("/")
        or DEFAULT_APEX_CONVERT_LEAD_PATH
    )
    lid = (lead_id or "00Q000000000000").strip()
    status = _resolve_converted_status(sf, "Converted")
    body = {
        "leadID": lid,
        "convertedStatus": status,
        "createOpportunity": True,
        "opportunityName": "Health Check",
        "overWriteLeadSource": False,
        "sendEmailToOwner": False,
    }
    headers = {
        "Authorization": f"Bearer {sf.session_id}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    probes: List[Dict[str, Any]] = []
    for url in _apex_convert_rest_urls(sf, path_seg, lid):
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=60)
            snippet = (resp.text or "")[:800]
            probes.append({"url": url, "status": resp.status_code, "body": snippet})
        except Exception as ex:
            probes.append({"url": url, "status": None, "error": str(ex)})
    apex_ok = any(p.get("status") not in (None, 404) for p in probes)
    return {
        "success": apex_ok,
        "lead_convert_build": LEAD_CONVERT_BUILD,
        "instance": sf.sf_instance,
        "apex_path": path_seg,
        "converted_status": status,
        "probes": probes,
        "hint": (
            "404 on all probes: integration user cannot see ConvertLeadRestApi. "
            "200 with errorMessage: Apex reachable; check message. "
            "200 with accountID/contactID: convert path works."
        ),
    }


def convert_lead(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a lead: Apex REST /services/apexrest/convertLead when available, else REST quick action
    LeadConvert, else SOAP; then standard price book, platform event, and Lead_Product__c line items.
    Retries once after a fresh JWT login if the session is invalid (SOAP/REST).
    """
    args = _normalize_convert_arguments(arguments if isinstance(arguments, dict) else {})
    lead_id = args.get("lead_id")
    if not lead_id:
        return {
            "success": False,
            "error": "Provide lead_id, leadId, or id for the Lead to convert.",
            "account_id": None,
            "contact_id": None,
            "opportunity_id": None,
        }

    convert_options = {
        "account_id": args.get("account_id"),
        "contact_id": args.get("contact_id"),
        "do_not_create_opportunity": args.get("do_not_create_opportunity", False),
    }
    lid = str(lead_id).strip()
    for attempt in range(2):
        try:
            if attempt > 0:
                invalidate_salesforce_session()
                sf = get_salesforce()
            return _convert_lead_execute(sf, lid, convert_options)
        except Exception as e:
            if attempt == 0 and _salesforce_session_should_retry(e):
                print(
                    "[Lead] Salesforce session invalid; clearing cache and retrying convert once...",
                    file=sys.stderr,
                )
                continue
            err = str(e)
            print(f"[Lead ERROR] convert_lead: {err}", file=sys.stderr)
            out: Dict[str, Any] = {
                "success": False,
                "error": err,
                "error_code": "LEAD_CONVERT_FAILED",
                "lead_id": lid,
                "lead_convert_build": LEAD_CONVERT_BUILD,
                "account_id": None,
                "contact_id": None,
                "opportunity_id": None,
            }
            if "could not be converted" in err or "convertLead" in err.lower():
                out["error_code"] = "LEAD_CONVERT_UNAVAILABLE"
                out["setup_doc"] = "LEAD_CONVERT_SETUP.md"
                out["fix_steps"] = [
                    "Grant integration user access to ConvertLeadRestApi and Connected App OAuth scopes",
                    "Confirm POST https://<instance>/services/apexrest/convertLead returns 200 (not 404)",
                    "Redeploy/restart the MCP server so tools/leads.py Apex payload matches LeadConversionRequest",
                    "Or set SF_SOAP_PASSWORD (password + security token) on Azure App Service",
                ]
            return out

    return {
        "success": False,
        "error": "Convert failed after session retry",
        "account_id": None,
        "contact_id": None,
        "opportunity_id": None,
    }


