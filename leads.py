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
        }
    ]

def handle_lead_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle lead-related tool calls"""
    sf = get_salesforce()
    
    if tool_name == "SALESFORCE_CREATE_LEAD":
        return create_lead(sf, arguments)
    elif tool_name == "SALESFORCE_ADD_LEAD_TO_CAMPAIGN":
        return add_lead_to_campaign(sf, arguments)
    else:
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
            "country", "website", "industry"
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
                lead_data[sf_field] = value
        
        # Add custom fields
        custom_fields = arguments.get("custom_fields", {})
        if custom_fields:
            lead_data.update(custom_fields)
        
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
    """Add a lead to a campaign"""
    try:
        lead_id = arguments.get("lead_id")
        campaign_id = arguments.get("campaign_id")
        
        if not lead_id:
            raise ValueError("Lead ID is required")
        if not campaign_id:
            raise ValueError("Campaign ID is required")
        
        # Build campaign member data
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
        return {
            "success": False,
            "error": error_msg
        }

