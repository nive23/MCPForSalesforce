"""
Contact Operations
Handles Salesforce Contact creation and campaign membership
"""
import sys
import json
from typing import Dict, Any, List
from simple_salesforce import SFType
from salesforce_config import get_salesforce

def get_contact_tools() -> List[Dict[str, Any]]:
    """Return list of contact-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_CREATE_CONTACT",
            "description": "Creates a new contact in Salesforce with the specified information.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "last_name": {
                        "type": "string",
                        "description": "Contact last name (required)"
                    },
                    "first_name": {
                        "type": "string",
                        "description": "Contact first name"
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Phone number"
                    },
                    "mobile_phone": {
                        "type": "string",
                        "description": "Mobile phone number"
                    },
                    "title": {
                        "type": "string",
                        "description": "Job title"
                    },
                    "department": {
                        "type": "string",
                        "description": "Department"
                    },
                    "birthdate": {
                        "type": "string",
                        "description": "Birthdate (YYYY-MM-DD format)"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Associated account ID"
                    },
                    "lead_source": {
                        "type": "string",
                        "description": "Lead source"
                    },
                    "mailing_street": {
                        "type": "string",
                        "description": "Mailing street address"
                    },
                    "mailing_city": {
                        "type": "string",
                        "description": "Mailing city"
                    },
                    "mailing_state": {
                        "type": "string",
                        "description": "Mailing state"
                    },
                    "mailing_postal_code": {
                        "type": "string",
                        "description": "Mailing postal code"
                    },
                    "mailing_country": {
                        "type": "string",
                        "description": "Mailing country"
                    },
                    "custom_fields": {
                        "type": "object",
                        "description": "Additional custom fields as key-value pairs"
                    }
                },
                "required": ["last_name"]
            }
        },
        {
            "name": "SALESFORCE_ADD_CONTACT_TO_CAMPAIGN",
            "description": "Adds a contact to a campaign by creating a CampaignMember record, allowing you to track campaign engagement.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "contact_id": {
                        "type": "string",
                        "description": "Contact ID (required)"
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
                "required": ["contact_id", "campaign_id"]
            }
        }
    ]

def handle_contact_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle contact-related tool calls"""
    sf = get_salesforce()
    
    if tool_name == "SALESFORCE_CREATE_CONTACT":
        return create_contact(sf, arguments)
    elif tool_name == "SALESFORCE_ADD_CONTACT_TO_CAMPAIGN":
        return add_contact_to_campaign(sf, arguments)
    else:
        raise ValueError(f"Unknown contact tool: {tool_name}")

def create_contact(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new contact in Salesforce"""
    try:
        # Extract required fields
        last_name = arguments.get("last_name")
        if not last_name:
            raise ValueError("Contact last name is required")
        
        # Build contact data
        contact_data = {
            "LastName": last_name
        }
        
        # Add optional fields
        optional_fields = [
            "first_name", "email", "phone", "mobile_phone", "title",
            "department", "birthdate", "account_id", "lead_source",
            "mailing_street", "mailing_city", "mailing_state",
            "mailing_postal_code", "mailing_country"
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
                elif field == "account_id":
                    sf_field = "AccountId"
                elif field == "lead_source":
                    sf_field = "LeadSource"
                elif field == "mobile_phone":
                    sf_field = "MobilePhone"
                elif field == "mailing_street":
                    sf_field = "MailingStreet"
                elif field == "mailing_city":
                    sf_field = "MailingCity"
                elif field == "mailing_state":
                    sf_field = "MailingState"
                elif field == "mailing_postal_code":
                    sf_field = "MailingPostalCode"
                elif field == "mailing_country":
                    sf_field = "MailingCountry"
                contact_data[sf_field] = value
        
        # Add custom fields
        custom_fields = arguments.get("custom_fields", {})
        if custom_fields:
            contact_data.update(custom_fields)
        
        # Create contact
        contact_sf = SFType('Contact', sf.session_id, sf.sf_instance)
        result = contact_sf.create(contact_data)
        
        contact_id = result["id"]
        print(f"[Contact] Created contact: {contact_id}", file=sys.stderr)
        
        return {
            "success": True,
            "contact_id": contact_id,
            "message": f"Contact '{last_name}' created successfully"
        }
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Contact ERROR] {error_msg}", file=sys.stderr)
        return {
            "success": False,
            "error": error_msg
        }

def add_contact_to_campaign(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Add a contact to a campaign"""
    try:
        contact_id = arguments.get("contact_id")
        campaign_id = arguments.get("campaign_id")
        
        if not contact_id:
            raise ValueError("Contact ID is required")
        if not campaign_id:
            raise ValueError("Campaign ID is required")
        
        # Build campaign member data
        member_data = {
            "ContactId": contact_id,
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
        print(f"[CampaignMember] Added contact {contact_id} to campaign {campaign_id}", file=sys.stderr)
        
        return {
            "success": True,
            "campaign_member_id": member_id,
            "contact_id": contact_id,
            "campaign_id": campaign_id,
            "message": "Contact added to campaign successfully"
        }
    
    except Exception as e:
        error_msg = str(e)
        print(f"[CampaignMember ERROR] {error_msg}", file=sys.stderr)
        return {
            "success": False,
            "error": error_msg
        }

