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
                    "is_active": {"type": "boolean", "description": "Whether campaign is active"},
                    "number_sent": {"type": "number", "description": "Number sent"},
                    "expected_response": {"type": "number", "description": "Expected response"},
                    "custom_fields": {
                        "type": "object",
                        "description": "Additional custom fields as key-value pairs"
                    }
                },
                "required": ["name"]
            }
        },
        {
            "name": "SALESFORCE_DELETE_CAMPAIGN",
            "description": "Permanently deletes a campaign from Salesforce. This action cannot be undone.",
            "inputSchema": {
                "type": "object",
                "properties": {"campaign_id": {"type": "string", "description": "Campaign ID (required)"}},
                "required": ["campaign_id"]
            }
        },
        {
            "name": "SALESFORCE_GET_CAMPAIGN",
            "description": "Retrieves a specific campaign by ID from Salesforce, returning all available fields.",
            "inputSchema": {
                "type": "object",
                "properties": {"campaign_id": {"type": "string", "description": "Campaign ID (required)"}},
                "required": ["campaign_id"]
            }
        },
        {
            "name": "SALESFORCE_LIST_CAMPAIGNS",
            "description": "Lists campaigns from Salesforce using SOQL query.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "SOQL query"}}
            }
        },
        {
            "name": "SALESFORCE_SEARCH_CAMPAIGNS",
            "description": "Search for Salesforce campaigns using name, type, status, date range, or active status.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "status": {"type": "string"},
                    "is_active": {"type": "boolean"},
                    "start_date_from": {"type": "string"},
                    "start_date_to": {"type": "string"},
                    "limit": {"type": "integer"},
                    "fields": {"type": "string"}
                }
            }
        },
        {
            "name": "SALESFORCE_UPDATE_CAMPAIGN",
            "description": "Updates an existing campaign in Salesforce with the specified changes.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID (required)"},
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "status": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "is_active": {"type": "boolean"},
                    "parent_id": {"type": "string"},
                    "actual_cost": {"type": "number"},
                    "budgeted_cost": {"type": "number"},
                    "expected_revenue": {"type": "number"},
                    "expected_response": {"type": "number"},
                    "number_sent": {"type": "number"},
                    "description": {"type": "string"},
                    "custom_fields": {"type": "object"}
                },
                "required": ["campaign_id"]
            }
        },
        {
            "name": "SALESFORCE_REMOVE_FROM_CAMPAIGN",
            "description": "Removes a lead or contact from a campaign by deleting the CampaignMember record. Provide either campaign_member_id, or both campaign_id and member_id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID (required when using member_id)"},
                    "member_id": {"type": "string", "description": "Lead or Contact ID"},
                    "campaign_member_id": {"type": "string", "description": "CampaignMember record ID (use this or campaign_id+member_id)"}
                }
            }
        }
    ]

def handle_campaign_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle campaign-related tool calls"""
    sf = get_salesforce()
    if tool_name == "SALESFORCE_CREATE_CAMPAIGN":
        return create_campaign(sf, arguments)
    if tool_name == "SALESFORCE_DELETE_CAMPAIGN":
        return delete_campaign(sf, arguments)
    if tool_name == "SALESFORCE_GET_CAMPAIGN":
        return get_campaign(sf, arguments)
    if tool_name == "SALESFORCE_LIST_CAMPAIGNS":
        return list_campaigns(sf, arguments)
    if tool_name == "SALESFORCE_SEARCH_CAMPAIGNS":
        return search_campaigns(sf, arguments)
    if tool_name == "SALESFORCE_UPDATE_CAMPAIGN":
        return update_campaign(sf, arguments)
    if tool_name == "SALESFORCE_REMOVE_FROM_CAMPAIGN":
        return remove_from_campaign(sf, arguments)
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
            "actual_cost", "expected_revenue", "description", "parent_id",
            "is_active", "number_sent", "expected_response"
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
                elif field == "is_active":
                    sf_field = "IsActive"
                elif field == "number_sent":
                    sf_field = "NumberSent"
                elif field == "expected_response":
                    sf_field = "ExpectedResponse"
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
        return {"success": False, "error": error_msg}


def delete_campaign(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        campaign_id = arguments.get("campaign_id")
        if not campaign_id:
            raise ValueError("campaign_id is required")
        camp_sf = SFType("Campaign", sf.session_id, sf.sf_instance)
        camp_sf.delete(campaign_id)
        return {"success": True, "message": "Campaign deleted"}
    except Exception as e:
        print(f"[Campaign ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def get_campaign(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        campaign_id = arguments.get("campaign_id")
        if not campaign_id:
            raise ValueError("campaign_id is required")
        camp_sf = SFType("Campaign", sf.session_id, sf.sf_instance)
        rec = camp_sf.get(campaign_id)
        return {"success": True, "record": rec}
    except Exception as e:
        print(f"[Campaign ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def list_campaigns(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        query = arguments.get("query") or "SELECT Id, Name, Type, Status, StartDate, EndDate FROM Campaign LIMIT 2000"
        result = sf.query(str(query).strip())
        return {"success": True, "records": result.get("records", []), "totalSize": result.get("totalSize", 0), "done": result.get("done", True), "nextRecordsUrl": result.get("nextRecordsUrl")}
    except Exception as e:
        print(f"[Campaign ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def search_campaigns(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        limit = min(int(arguments.get("limit", 50)), 200)
        fields = arguments.get("fields") or "Id, Name, Type, Status, IsActive, StartDate, EndDate"
        where = []
        if arguments.get("name"):
            where.append(f"Name LIKE '%{str(arguments['name']).replace(chr(39), chr(39)+chr(39))}%'")
        if arguments.get("type"):
            where.append(f"Type = '{str(arguments['type']).replace(chr(39), chr(39)+chr(39))}'")
        if arguments.get("status"):
            where.append(f"Status = '{str(arguments['status']).replace(chr(39), chr(39)+chr(39))}'")
        if arguments.get("is_active") is not None:
            where.append(f"IsActive = {str(arguments['is_active']).lower()}")
        if arguments.get("start_date_from"):
            where.append(f"StartDate >= {repr(arguments['start_date_from'])}")
        if arguments.get("start_date_to"):
            where.append(f"StartDate <= {repr(arguments['start_date_to'])}")
        where_clause = " AND ".join(where) if where else "Id != null"
        result = sf.query(f"SELECT {fields} FROM Campaign WHERE {where_clause} LIMIT {limit}")
        return {"success": True, "records": result.get("records", []), "totalSize": result.get("totalSize", 0)}
    except Exception as e:
        print(f"[Campaign ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


CAMPAIGN_UPDATE_FIELDS = {
    "name": "Name", "type": "Type", "status": "Status", "start_date": "StartDate", "end_date": "EndDate",
    "is_active": "IsActive", "parent_id": "ParentId", "actual_cost": "ActualCost", "budgeted_cost": "BudgetedCost",
    "expected_revenue": "ExpectedRevenue", "expected_response": "ExpectedResponse", "number_sent": "NumberSent", "description": "Description",
}


def update_campaign(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        campaign_id = arguments.get("campaign_id")
        if not campaign_id:
            raise ValueError("campaign_id is required")
        update_data = {}
        for k, sf_field in CAMPAIGN_UPDATE_FIELDS.items():
            v = arguments.get(k)
            if v is not None:
                update_data[sf_field] = v
        custom = arguments.get("custom_fields", {})
        if custom:
            update_data.update(custom)
        if not update_data:
            return {"success": True, "message": "No fields to update"}
        camp_sf = SFType("Campaign", sf.session_id, sf.sf_instance)
        camp_sf.update(campaign_id, update_data)
        return {"success": True, "campaign_id": campaign_id, "message": "Campaign updated"}
    except Exception as e:
        print(f"[Campaign ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def remove_from_campaign(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        campaign_id = arguments.get("campaign_id")
        campaign_member_id = arguments.get("campaign_member_id")
        member_id = arguments.get("member_id")
        if campaign_member_id:
            mem_sf = SFType("CampaignMember", sf.session_id, sf.sf_instance)
            mem_sf.delete(campaign_member_id)
            return {"success": True, "message": "Removed from campaign"}
        if campaign_id and member_id:
            result = sf.query(f"SELECT Id FROM CampaignMember WHERE CampaignId = '{campaign_id}' AND (LeadId = '{member_id}' OR ContactId = '{member_id}') LIMIT 1")
            recs = result.get("records", [])
            if not recs:
                return {"success": False, "error": "No campaign member found for this lead/contact and campaign"}
            mem_sf = SFType("CampaignMember", sf.session_id, sf.sf_instance)
            mem_sf.delete(recs[0]["Id"])
            return {"success": True, "message": "Removed from campaign"}
        raise ValueError("Provide either campaign_member_id or both campaign_id and member_id")
    except Exception as e:
        print(f"[Campaign ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


