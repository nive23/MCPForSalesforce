"""
Opportunity Operations
Handles Salesforce Opportunity creation
"""
import sys
import json
from typing import Dict, Any, List
from simple_salesforce import SFType
from salesforce_config import get_salesforce

def get_opportunity_tools() -> List[Dict[str, Any]]:
    """Return list of opportunity-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_CREATE_OPPORTUNITY",
            "description": "Creates a new opportunity in Salesforce with the specified information.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Opportunity name (required)"
                    },
                    "close_date": {
                        "type": "string",
                        "description": "Close date (YYYY-MM-DD format) (required)"
                    },
                    "stage_name": {
                        "type": "string",
                        "description": "Opportunity stage (e.g., Prospecting, Qualification, Closed Won) (required)"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Opportunity amount"
                    },
                    "type": {
                        "type": "string",
                        "description": "Opportunity type"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Associated account ID"
                    },
                    "contact_id": {
                        "type": "string",
                        "description": "Primary contact ID"
                    },
                    "lead_source": {
                        "type": "string",
                        "description": "Lead source"
                    },
                    "probability": {
                        "type": "number",
                        "description": "Probability percentage (0-100)"
                    },
                    "next_step": {
                        "type": "string",
                        "description": "Next step"
                    },
                    "description": {
                        "type": "string",
                        "description": "Opportunity description"
                    },
                    "pricebook2_id": {
                        "type": "string",
                        "description": "Pricebook ID"
                    },
                    "custom_fields": {
                        "type": "object",
                        "description": "Additional custom fields as key-value pairs"
                    }
                },
                "required": ["name", "close_date", "stage_name"]
            }
        }
    ]

def handle_opportunity_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle opportunity-related tool calls"""
    sf = get_salesforce()
    
    if tool_name == "SALESFORCE_CREATE_OPPORTUNITY":
        return create_opportunity(sf, arguments)
    else:
        raise ValueError(f"Unknown opportunity tool: {tool_name}")

def create_opportunity(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new opportunity in Salesforce"""
    try:
        # Extract required fields
        name = arguments.get("name")
        close_date = arguments.get("close_date")
        stage_name = arguments.get("stage_name")
        
        if not name:
            raise ValueError("Opportunity name is required")
        if not close_date:
            raise ValueError("Close date is required")
        if not stage_name:
            raise ValueError("Stage name is required")
        
        # Build opportunity data
        opportunity_data = {
            "Name": name,
            "CloseDate": close_date,
            "StageName": stage_name
        }
        
        # Add optional fields
        optional_fields = [
            "amount", "type", "account_id", "contact_id", "lead_source",
            "probability", "next_step", "description", "pricebook2_id"
        ]
        
        for field in optional_fields:
            value = arguments.get(field)
            if value is not None:
                # Convert field name to Salesforce API name
                sf_field = field[0].upper() + field[1:] if field else field
                # Handle special cases
                if field == "type":
                    sf_field = "Type"
                elif field == "account_id":
                    sf_field = "AccountId"
                elif field == "contact_id":
                    sf_field = "ContactId"
                elif field == "lead_source":
                    sf_field = "LeadSource"
                elif field == "close_date":
                    sf_field = "CloseDate"
                elif field == "stage_name":
                    sf_field = "StageName"
                elif field == "next_step":
                    sf_field = "NextStep"
                elif field == "pricebook2_id":
                    sf_field = "Pricebook2Id"
                opportunity_data[sf_field] = value
        
        # Add custom fields
        custom_fields = arguments.get("custom_fields", {})
        if custom_fields:
            opportunity_data.update(custom_fields)
        
        # Create opportunity
        opportunity_sf = SFType('Opportunity', sf.session_id, sf.sf_instance)
        result = opportunity_sf.create(opportunity_data)
        
        opportunity_id = result["id"]
        print(f"[Opportunity] Created opportunity: {opportunity_id}", file=sys.stderr)
        
        return {
            "success": True,
            "opportunity_id": opportunity_id,
            "message": f"Opportunity '{name}' created successfully"
        }
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Opportunity ERROR] {error_msg}", file=sys.stderr)
        return {
            "success": False,
            "error": error_msg
        }

