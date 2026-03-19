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
        },
        {
            "name": "SALESFORCE_GET_OPPORTUNITY",
            "description": "Retrieves a specific opportunity by ID from Salesforce, returning all available fields.",
            "inputSchema": {"type": "object", "properties": {"opportunity_id": {"type": "string"}, "fields": {"type": "string"}}, "required": ["opportunity_id"]}
        },
        {
            "name": "SALESFORCE_LIST_OPPORTUNITIES",
            "description": "Lists opportunities from Salesforce using SOQL query.",
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}
        },
        {
            "name": "SALESFORCE_SEARCH_OPPORTUNITIES",
            "description": "Search for Salesforce opportunities using name, account, stage, amount, close date, or status.",
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "account_name": {"type": "string"}, "stage_name": {"type": "string"}, "amount_min": {"type": "number"}, "amount_max": {"type": "number"}, "close_date_from": {"type": "string"}, "close_date_to": {"type": "string"}, "is_won": {"type": "boolean"}, "is_closed": {"type": "boolean"}, "lead_source": {"type": "string"}, "limit": {"type": "integer"}, "fields": {"type": "string"}}
            }
        },
        {
            "name": "SALESFORCE_UPDATE_OPPORTUNITY",
            "description": "Updates an existing opportunity in Salesforce with the specified changes.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "opportunity_id": {"type": "string"},
                    "name": {"type": "string"}, "type": {"type": "string"}, "amount": {"type": "number"},
                    "close_date": {"type": "string"}, "stage_name": {"type": "string"}, "account_id": {"type": "string"},
                    "next_step": {"type": "string"}, "description": {"type": "string"}, "lead_source": {"type": "string"},
                    "probability": {"type": "number"}, "pricebook2_id": {"type": "string"}, "custom_fields": {"type": "object"}
                },
                "required": ["opportunity_id"]
            }
        }
    ]

def handle_opportunity_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle opportunity-related tool calls"""
    sf = get_salesforce()
    if tool_name == "SALESFORCE_CREATE_OPPORTUNITY":
        return create_opportunity(sf, arguments)
    if tool_name == "SALESFORCE_GET_OPPORTUNITY":
        return get_opportunity(sf, arguments)
    if tool_name == "SALESFORCE_LIST_OPPORTUNITIES":
        return list_opportunities(sf, arguments)
    if tool_name == "SALESFORCE_SEARCH_OPPORTUNITIES":
        return search_opportunities(sf, arguments)
    if tool_name == "SALESFORCE_UPDATE_OPPORTUNITY":
        return update_opportunity(sf, arguments)
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
        return {"success": False, "error": error_msg}


def get_opportunity(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        opp_id = arguments.get("opportunity_id")
        if not opp_id:
            raise ValueError("opportunity_id is required")
        opp_sf = SFType("Opportunity", sf.session_id, sf.sf_instance)
        rec = opp_sf.get(opp_id)
        return {"success": True, "record": rec}
    except Exception as e:
        print(f"[Opportunity ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def list_opportunities(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        query = arguments.get("query") or "SELECT Id, Name, StageName, Amount, CloseDate FROM Opportunity LIMIT 2000"
        result = sf.query(str(query).strip())
        return {"success": True, "records": result.get("records", []), "totalSize": result.get("totalSize", 0), "done": result.get("done", True), "nextRecordsUrl": result.get("nextRecordsUrl")}
    except Exception as e:
        print(f"[Opportunity ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def search_opportunities(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        limit = min(int(arguments.get("limit", 50)), 200)
        fields = arguments.get("fields") or "Id, Name, StageName, Amount, CloseDate, AccountId"
        where = []
        def esc(s): return str(s).replace("'", "''")
        if arguments.get("name"):
            where.append(f"Name LIKE '%{esc(arguments['name'])}%'")
        if arguments.get("stage_name"):
            where.append(f"StageName = '{esc(arguments['stage_name'])}'")
        if arguments.get("amount_min") is not None:
            where.append(f"Amount >= {arguments['amount_min']}")
        if arguments.get("amount_max") is not None:
            where.append(f"Amount <= {arguments['amount_max']}")
        if arguments.get("close_date_from"):
            where.append(f"CloseDate >= {repr(arguments['close_date_from'])}")
        if arguments.get("close_date_to"):
            where.append(f"CloseDate <= {repr(arguments['close_date_to'])}")
        if arguments.get("is_won") is not None:
            where.append(f"IsWon = {str(arguments['is_won']).lower()}")
        if arguments.get("is_closed") is not None:
            where.append(f"IsClosed = {str(arguments['is_closed']).lower()}")
        if arguments.get("lead_source"):
            where.append(f"LeadSource = '{esc(arguments['lead_source'])}'")
        if arguments.get("account_name"):
            where.append(f"AccountId IN (SELECT Id FROM Account WHERE Name LIKE '%{esc(arguments['account_name'])}%')")
        where_clause = " AND ".join(where) if where else "Id != null"
        result = sf.query(f"SELECT {fields} FROM Opportunity WHERE {where_clause} LIMIT {limit}")
        return {"success": True, "records": result.get("records", []), "totalSize": result.get("totalSize", 0)}
    except Exception as e:
        print(f"[Opportunity ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


OPP_UPDATE_MAP = {"name": "Name", "type": "Type", "amount": "Amount", "close_date": "CloseDate", "stage_name": "StageName", "account_id": "AccountId", "next_step": "NextStep", "description": "Description", "lead_source": "LeadSource", "probability": "Probability", "pricebook2_id": "Pricebook2Id"}


def update_opportunity(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        opp_id = arguments.get("opportunity_id")
        if not opp_id:
            raise ValueError("opportunity_id is required")
        update_data = {}
        for k, sf_field in OPP_UPDATE_MAP.items():
            v = arguments.get(k)
            if v is not None:
                update_data[sf_field] = v
        custom = arguments.get("custom_fields", {})
        if custom:
            update_data.update(custom)
        if not update_data:
            return {"success": True, "message": "No fields to update"}
        opp_sf = SFType("Opportunity", sf.session_id, sf.sf_instance)
        opp_sf.update(opp_id, update_data)
        return {"success": True, "opportunity_id": opp_id, "message": "Opportunity updated"}
    except Exception as e:
        print(f"[Opportunity ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


