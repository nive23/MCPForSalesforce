"""
Campaign Operations
Handles Salesforce Campaign creation
"""
import sys
import json
from typing import Dict, Any, List
from simple_salesforce import SFType
from salesforce_config import get_salesforce

def get_campaign_tools() -> List[Dict[str, Any]]:
    """Return list of campaign-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_CREATE_CAMPAIGN",
            "description": "Creates a new campaign in Salesforce with the specified information.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Campaign name (required)"
                    },
                    "type": {
                        "type": "string",
                        "description": "Campaign type (e.g., Conference, Webinar, Email)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Campaign status (e.g., Planned, In Progress, Completed)"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Campaign start date (YYYY-MM-DD format)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Campaign end date (YYYY-MM-DD format)"
                    },
                    "budgeted_cost": {
                        "type": "number",
                        "description": "Budgeted cost"
                    },
                    "actual_cost": {
                        "type": "number",
                        "description": "Actual cost"
                    },
                    "expected_revenue": {
                        "type": "number",
                        "description": "Expected revenue"
                    },
                    "description": {
                        "type": "string",
                        "description": "Campaign description"
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "Parent campaign ID"
                    },
                    "custom_fields": {
                        "type": "object",
                        "description": "Additional custom fields as key-value pairs"
                    }
                },
                "required": ["name"]
            }
        }
    ]

def handle_campaign_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle campaign-related tool calls"""
    sf = get_salesforce()
    
    if tool_name == "SALESFORCE_CREATE_CAMPAIGN":
        return create_campaign(sf, arguments)
    else:
        raise ValueError(f"Unknown campaign tool: {tool_name}")

def create_campaign(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new campaign in Salesforce"""
    try:
        # Extract required fields
        name = arguments.get("name")
        if not name:
            raise ValueError("Campaign name is required")
        
        # Build campaign data
        campaign_data = {
            "Name": name
        }
        
        # Add optional fields
        optional_fields = [
            "type", "status", "start_date", "end_date", "budgeted_cost",
            "actual_cost", "expected_revenue", "description", "parent_id"
        ]
        
        for field in optional_fields:
            value = arguments.get(field)
            if value is not None:
                # Convert field name to Salesforce API name
                sf_field = field[0].upper() + field[1:] if field else field
                # Handle special cases
                if field == "type":
                    sf_field = "Type"
                elif field == "start_date":
                    sf_field = "StartDate"
                elif field == "end_date":
                    sf_field = "EndDate"
                elif field == "budgeted_cost":
                    sf_field = "BudgetedCost"
                elif field == "actual_cost":
                    sf_field = "ActualCost"
                elif field == "expected_revenue":
                    sf_field = "ExpectedRevenue"
                elif field == "parent_id":
                    sf_field = "ParentId"
                campaign_data[sf_field] = value
        
        # Add custom fields
        custom_fields = arguments.get("custom_fields", {})
        if custom_fields:
            campaign_data.update(custom_fields)
        
        # Create campaign
        campaign_sf = SFType('Campaign', sf.session_id, sf.sf_instance)
        result = campaign_sf.create(campaign_data)
        
        campaign_id = result["id"]
        print(f"[Campaign] Created campaign: {campaign_id}", file=sys.stderr)
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "message": f"Campaign '{name}' created successfully"
        }
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Campaign ERROR] {error_msg}", file=sys.stderr)
        return {
            "success": False,
            "error": error_msg
        }

