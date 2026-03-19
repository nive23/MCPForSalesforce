"""
Lead Operations
Handles Salesforce Lead creation and campaign membership
"""
import sys
import json
from typing import Dict, Any, List
from simple_salesforce import SFType
from salesforce_config import get_salesforce

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
                        "description": "Company name (required)"
                    },
                    "first_name": {
                        "type": "string",
                        "description": "Lead first name"
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address"
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
                        "description": "Annual revenue (e.g., 10000)"
                    },
                    "product_description": {
                        "type": "string",
                        "description": "Product description - stored in custom field Product_Description__c (e.g., One Basic Laptop Bundle). Always pass this when the user asks for product description."
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
                "required": ["last_name", "company"]
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
            "description": "Retrieves a specific lead by ID from Salesforce, returning all available fields.",
            "inputSchema": {"type": "object", "properties": {"lead_id": {"type": "string"}}, "required": ["lead_id"]}
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
        }
    ]

def handle_lead_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle lead-related tool calls"""
    sf = get_salesforce()
    if tool_name == "SALESFORCE_CREATE_LEAD":
        return create_lead(sf, arguments)
    if tool_name == "SALESFORCE_ADD_LEAD_TO_CAMPAIGN":
        return add_lead_to_campaign(sf, arguments)
    if tool_name == "SALESFORCE_DELETE_LEAD":
        return delete_lead(sf, arguments)
    if tool_name == "SALESFORCE_GET_LEAD":
        return get_lead(sf, arguments)
    if tool_name == "SALESFORCE_LIST_LEADS":
        return list_leads(sf, arguments)
    if tool_name == "SALESFORCE_SEARCH_LEADS":
        return search_leads(sf, arguments)
    if tool_name == "SALESFORCE_UPDATE_LEAD":
        return update_lead(sf, arguments)
    raise ValueError(f"Unknown lead tool: {tool_name}")

def create_lead(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new lead in Salesforce"""
    try:
        # Extract required fields
        last_name = arguments.get("last_name")
        company = arguments.get("company")
        
        if not last_name:
            raise ValueError("Lead last name is required")
        if not company:
            raise ValueError("Company name is required")
        
        # Build lead data
        lead_data = {
            "LastName": last_name,
            "Company": company
        }
        
        # Add optional fields
        optional_fields = [
            "first_name", "email", "phone", "title", "rating", "status",
            "lead_source", "street", "city", "state", "postal_code",
            "country", "website", "industry", "annual_revenue"
        ]
        
        for field in optional_fields:
            value = arguments.get(field)
            if value is not None:
                # Convert field name to Salesforce API name
                sf_field = field[0].upper() + field[1:] if field else field
                # Handle special cases
                if field == "first_name":
                    sf_field = "FirstName"
                elif field == "last_name":
                    sf_field = "LastName"
                elif field == "lead_source":
                    sf_field = "LeadSource"
                elif field == "postal_code":
                    sf_field = "PostalCode"
                elif field == "annual_revenue":
                    sf_field = "AnnualRevenue"
                lead_data[sf_field] = value
        
        # Add custom fields first
        custom_fields = arguments.get("custom_fields", {})
        if custom_fields:
            lead_data.update(custom_fields)
        
        # Product description -> custom field Product_Description__c (set after custom_fields so it is never overwritten)
        product_description = arguments.get("product_description") or arguments.get("Product_Description__c")
        if product_description is not None and str(product_description).strip():
            lead_data["Product_Description__c"] = str(product_description).strip()
        
        # Create lead
        lead_sf = SFType('Lead', sf.session_id, sf.sf_instance)
        result = lead_sf.create(lead_data)
        
        lead_id = result["id"]
        print(f"[Lead] Created lead: {lead_id}", file=sys.stderr)
        
        return {
            "success": True,
            "lead_id": lead_id,
            "message": f"Lead '{last_name}' from '{company}' created successfully"
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
    try:
        lead_id = arguments.get("lead_id")
        if not lead_id:
            raise ValueError("lead_id is required")
        lead_sf = SFType("Lead", sf.session_id, sf.sf_instance)
        rec = lead_sf.get(lead_id)
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


