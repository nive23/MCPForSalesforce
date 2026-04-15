"""
Lead Operations
Handles Salesforce Lead creation, campaign membership, and lead conversion
"""
import sys
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
from xml.sax.saxutils import escape

from simple_salesforce import SFType
from simple_salesforce.exceptions import (
    SalesforceError,
    SalesforceExpiredSession,
    SalesforceResourceNotFound,
)

from salesforce_config import get_salesforce, invalidate_salesforce_session

# Custom metadata aligned with ConvertLeadApex (adjust if your org uses different API names)
LEAD_PRODUCT_OBJECT = "Lead_Product__c"
LEAD_PRODUCT_LEAD_FIELD = "Lead__c"
LEAD_PRODUCT_PRODUCT_FIELD = "Product__c"
LEAD_PRODUCT_QUANTITY_FIELD = "Quantity__c"
OPPORTUNITY_PLATFORM_EVENT_OBJECT = "Opportunity_PlatformEvent__e"
OPPORTUNITY_PLATFORM_EVENT_OPP_FIELD = "OpportunityId__c"

def get_lead_tools() -> List[Dict[str, Any]]:
    """Return list of lead-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_CREATE_LEAD",
            "description": "Creates a new lead in Salesforce with the specified information.",
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
                        "description": "Product description (required) - stored in Product_Description__c (e.g., One Basic Laptop Bundle)."
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
                "Converts a lead with a fixed business flow: always creates a new Account and Contact, "
                "always creates an Opportunity named after the lead, overwriteLeadSource=false, "
                "no owner notification email, converted status 'Converted', then standard price book, "
                "Lead_Product__c line items, and Opportunity_PlatformEvent__e. "
                "Uses REST LeadConvert quick action when available; if that returns 404, falls back to "
                "SOAP Partner API convertLead (same as Database.convertLead)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "15 or 18 character Lead Id"},
                    "leadId": {"type": "string", "description": "Same as lead_id"},
                    "id": {"type": "string", "description": "Same as lead_id"},
                },
                "description": "Provide lead_id, leadId, or id. All other convert flags are fixed in code.",
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

        company_raw = arguments.get("company")
        company = str(company_raw).strip() if company_raw is not None else ""
        if not company:
            company = "(Not specified)"

        lead_data = {
            "LastName": str(last_name).strip(),
            "FirstName": str(first_name).strip(),
            "Company": company,
            "Email": str(email).strip(),
            "AnnualRevenue": annual_revenue,
            "Product_Description__c": str(product_description).strip(),
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

        lead_data["Product_Description__c"] = str(product_description).strip()
        
        # Create lead
        lead_sf = SFType('Lead', sf.session_id, sf.sf_instance)
        result = lead_sf.create(lead_data)
        
        lead_id = result["id"]
        print(f"[Lead] Created lead: {lead_id}", file=sys.stderr)
        
        return {
            "success": True,
            "lead_id": lead_id,
            "message": f"Lead '{str(first_name).strip()} {str(last_name).strip()}' created successfully"
        }
    
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


def _convert_lead_soap(
    sf: Any,
    lead_id: str,
    converted_status: str,
    opportunity_name: str,
) -> Tuple[str, str, str]:
    """
    Partner SOAP API convertLead — works when REST .../actions/quick/LeadConvert is not available (404).
    """
    sid = escape(str(sf.session_id), entities={"'": "&apos;", '"': "&quot;"})
    lid = escape(str(lead_id), entities={"'": "&apos;", '"': "&quot;"})
    cst = escape(str(converted_status), entities={"'": "&apos;", '"': "&quot;"})
    onm = escape(str(opportunity_name), entities={"'": "&apos;", '"': "&quot;"})
    ver = sf.sf_version
    host = sf.sf_instance
    url = f"https://{host}/services/Soap/u/{ver}"
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:partner.soap.sforce.com">
  <soapenv:Header>
    <urn:SessionHeader>
      <urn:sessionId>{sid}</urn:sessionId>
    </urn:SessionHeader>
  </soapenv:Header>
  <soapenv:Body>
    <urn:convertLead>
      <urn:leadConverts>
        <urn:leadId>{lid}</urn:leadId>
        <urn:convertedStatus>{cst}</urn:convertedStatus>
        <urn:doNotCreateOpportunity>false</urn:doNotCreateOpportunity>
        <urn:overwriteLeadSource>false</urn:overwriteLeadSource>
        <urn:sendNotificationEmail>false</urn:sendNotificationEmail>
        <urn:opportunityName>{onm}</urn:opportunityName>
      </urn:leadConverts>
    </urn:convertLead>
  </soapenv:Body>
</soapenv:Envelope>"""
    headers = {
        "Content-Type": "text/xml; charset=UTF-8",
        "SOAPAction": '""',
    }
    resp = sf.session.post(url, data=envelope.encode("utf-8"), headers=headers, timeout=120)
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
    if not opp_id:
        raise RuntimeError(
            "SOAP convertLead did not return opportunityId; org may block opportunity on convert."
        )
    return acc_id, con_id, opp_id


def _salesforce_session_should_retry(exc: BaseException) -> bool:
    """True when a fresh JWT login may fix the failure (SOAP fault or REST 401)."""
    if isinstance(exc, SalesforceExpiredSession):
        return True
    if isinstance(exc, SalesforceError) and getattr(exc, "status", None) == 401:
        return True
    msg = str(exc).upper()
    if "INVALID_SESSION_ID" in msg:
        return True
    if "SESSION_EXPIRED" in msg or "INSUFFICIENT_SESSION" in msg:
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


def _get_standard_pricebook_id(sf: Any) -> str:
    q = "SELECT Id FROM Pricebook2 WHERE IsStandard = true LIMIT 1"
    res = sf.query(q)
    recs = res.get("records") or []
    if not recs:
        raise RuntimeError("No standard Pricebook2 found in org")
    return recs[0]["Id"]


def _post_convert_opportunity_extras(sf: Any, lead_id: str, opportunity_id: str) -> Dict[str, Any]:
    """Standard price book, mandatory platform event, Lead_Product__c -> OpportunityLineItem."""
    notes: List[str] = []
    line_items_created = 0
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

    lead_products = lp_res.get("records") or []
    if not lead_products:
        return {"line_items_created": 0, "notes": notes}

    opp_sf.update(opportunity_id, {"Pricebook2Id": standard_pb_id})

    product_ids: List[str] = []
    for row in lead_products:
        pid = row.get(LEAD_PRODUCT_PRODUCT_FIELD)
        if pid:
            product_ids.append(pid)
    if not product_ids:
        return {"line_items_created": 0, "notes": notes}

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

    return {"line_items_created": line_items_created, "notes": notes}


def _convert_lead_execute(sf: Any, lead_id: str) -> Dict[str, Any]:
    """
    Single attempt: REST LeadConvert or SOAP fallback, then post-convert steps.
    Raises on failure so caller can retry after session refresh.
    """
    lead_row = _query_lead_row_by_id(sf, lead_id)
    if not lead_row:
        raise RuntimeError(f"No Lead found with Id {lead_id}")
    first = (lead_row.get("FirstName") or "").strip()
    last = (lead_row.get("LastName") or "").strip()
    lead_name = (lead_row.get("Name") or f"{first} {last}".strip() or "Lead").strip()

    converted_status = "Converted"
    opportunity_name = lead_name

    payload: Dict[str, Any] = {
        "convertedStatus": str(converted_status).strip(),
        "overwriteLeadSource": False,
        "sendNotificationEmail": False,
        "doNotCreateOpportunity": False,
        "opportunityName": str(opportunity_name).strip(),
    }

    path = f"sobjects/Lead/{lead_id}/actions/quick/LeadConvert"
    convert_via = "rest"
    acc_id: Optional[str] = None
    con_id: Optional[str] = None
    opp_id: Optional[str] = None
    try:
        raw = sf.restful(path, method="POST", json=payload)
        acc_id, con_id, opp_id = _parse_lead_convert_response(raw)
    except SalesforceResourceNotFound:
        convert_via = "soap"
        acc_id, con_id, opp_id = _convert_lead_soap(
            sf, str(lead_id), converted_status, str(opportunity_name).strip()
        )

    if not acc_id and not con_id:
        raise RuntimeError("Lead convert returned no account or contact id")
    if not opp_id:
        raise RuntimeError(
            "Lead convert did not return an opportunity id; ensure the org allows creating "
            "an opportunity on convert (this tool always requests one)."
        )

    result: Dict[str, Any] = {
        "success": True,
        "account_id": acc_id,
        "contact_id": con_id,
        "opportunity_id": opp_id,
        "converted_status": converted_status,
        "opportunity_name": opportunity_name,
        "convert_via": convert_via,
    }

    try:
        extras = _post_convert_opportunity_extras(sf, lead_id, opp_id)
        result["line_items_created"] = extras["line_items_created"]
        if extras.get("notes"):
            result["notes"] = extras["notes"]
    except Exception as post_ex:
        result["post_convert_warning"] = str(post_ex)
        result["line_items_created"] = 0

    print(f"[Lead] Converted lead {lead_id} -> account={acc_id} contact={con_id} opp={opp_id}", file=sys.stderr)
    return result


def convert_lead(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a lead via REST quick action LeadConvert: always new Account/Contact, always Opportunity,
    then standard price book, platform event, and Lead_Product__c line items.
    Retries once after a fresh JWT login if the session is invalid (SOAP/REST).
    """
    args = _normalize_lead_id_in_arguments(arguments if isinstance(arguments, dict) else {})
    lead_id = args.get("lead_id")
    if not lead_id:
        return {
            "success": False,
            "error": "Provide lead_id, leadId, or id for the Lead to convert.",
            "account_id": None,
            "contact_id": None,
            "opportunity_id": None,
        }

    lid = str(lead_id).strip()
    for attempt in range(2):
        try:
            if attempt > 0:
                invalidate_salesforce_session()
                sf = get_salesforce()
            return _convert_lead_execute(sf, lid)
        except Exception as e:
            if attempt == 0 and _salesforce_session_should_retry(e):
                print(
                    "[Lead] Salesforce session invalid; clearing cache and retrying convert once...",
                    file=sys.stderr,
                )
                continue
            err = str(e)
            print(f"[Lead ERROR] convert_lead: {err}", file=sys.stderr)
            return {
                "success": False,
                "error": err,
                "account_id": None,
                "contact_id": None,
                "opportunity_id": None,
            }

    return {
        "success": False,
        "error": "Convert failed after session retry",
        "account_id": None,
        "contact_id": None,
        "opportunity_id": None,
    }


