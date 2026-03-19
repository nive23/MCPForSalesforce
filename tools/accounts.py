"""
Account Operations
Handles Salesforce Account creation and retrieval
"""
import sys
import json
from typing import Dict, Any, List
from simple_salesforce import SFType
from salesforce_config import get_salesforce

def get_account_tools() -> List[Dict[str, Any]]:
    """Return list of account-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_CREATE_ACCOUNT",
            "description": "Creates a new account in Salesforce with the specified information.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Account name (required)"
                    },
                    "type": {
                        "type": "string",
                        "description": "Type of account (e.g., Customer, Partner, Prospect)"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Phone number"
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
                        "description": "Annual revenue"
                    },
                    "number_of_employees": {
                        "type": "integer",
                        "description": "Number of employees"
                    },
                    "description": {
                        "type": "string",
                        "description": "Account description"
                    },
                    "billing_street": {
                        "type": "string",
                        "description": "Billing street address"
                    },
                    "billing_city": {
                        "type": "string",
                        "description": "Billing city"
                    },
                    "billing_state": {
                        "type": "string",
                        "description": "Billing state"
                    },
                    "billing_postal_code": {
                        "type": "string",
                        "description": "Billing postal code"
                    },
                    "billing_country": {
                        "type": "string",
                        "description": "Billing country"
                    },
                    "shipping_street": {
                        "type": "string",
                        "description": "Shipping street address"
                    },
                    "shipping_city": {
                        "type": "string",
                        "description": "Shipping city"
                    },
                    "shipping_state": {
                        "type": "string",
                        "description": "Shipping state"
                    },
                    "shipping_postal_code": {
                        "type": "string",
                        "description": "Shipping postal code"
                    },
                    "shipping_country": {
                        "type": "string",
                        "description": "Shipping country"
                    },
                    "account_source": {
                        "type": "string",
                        "description": "Account source"
                    },
                    "fax": {
                        "type": "string",
                        "description": "Fax number"
                    },
                    "sic_desc": {
                        "type": "string",
                        "description": "SIC description"
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "Parent account ID"
                    },
                    "custom_fields": {
                        "type": "object",
                        "description": "Additional custom fields as key-value pairs"
                    }
                },
                "required": ["name"]
            }
        },
        {
            "name": "get_accounts",
            "description": "Fetch Salesforce Accounts. Returns list of account names and IDs.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of accounts to return (default: 5, max: 100)",
                        "default": 5
                    }
                }
            }
        },
        {
            "name": "SALESFORCE_DELETE_ACCOUNT",
            "description": "Permanently deletes an account from Salesforce. This action cannot be undone.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "Account ID (required)"}
                },
                "required": ["account_id"]
            }
        },
        {
            "name": "SALESFORCE_GET_ACCOUNT",
            "description": "Retrieves a specific account by ID from Salesforce, returning all available fields.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "Account ID (required)"}
                },
                "required": ["account_id"]
            }
        },
        {
            "name": "SALESFORCE_LIST_ACCOUNTS",
            "description": "Lists accounts from Salesforce using SOQL query, allowing flexible filtering, sorting, and field selection.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SOQL query (e.g. SELECT Id, Name FROM Account LIMIT 100)"}
                }
            }
        },
        {
            "name": "SALESFORCE_SEARCH_ACCOUNTS",
            "description": "Search for Salesforce accounts using criteria like name, industry, type, location.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "industry": {"type": "string"},
                    "phone": {"type": "string"},
                    "website": {"type": "string"},
                    "billing_city": {"type": "string"},
                    "billing_state": {"type": "string"},
                    "billing_country": {"type": "string"},
                    "limit": {"type": "integer", "description": "Max results (default 50)"},
                    "fields": {"type": "string", "description": "Comma-separated field names"}
                }
            }
        },
        {
            "name": "SALESFORCE_UPDATE_ACCOUNT",
            "description": "Updates an existing account in Salesforce with the specified changes.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "Account ID (required)"},
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "phone": {"type": "string"},
                    "website": {"type": "string"},
                    "industry": {"type": "string"},
                    "sic_desc": {"type": "string"},
                    "parent_id": {"type": "string"},
                    "description": {"type": "string"},
                    "billing_city": {"type": "string"},
                    "billing_state": {"type": "string"},
                    "billing_street": {"type": "string"},
                    "billing_country": {"type": "string"},
                    "billing_postal_code": {"type": "string"},
                    "shipping_city": {"type": "string"},
                    "shipping_state": {"type": "string"},
                    "shipping_street": {"type": "string"},
                    "shipping_country": {"type": "string"},
                    "shipping_postal_code": {"type": "string"},
                    "account_source": {"type": "string"},
                    "annual_revenue": {"type": "number"},
                    "number_of_employees": {"type": "integer"},
                    "fax": {"type": "string"},
                    "custom_fields": {"type": "object"}
                },
                "required": ["account_id"]
            }
        }
    ]

def handle_account_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle account-related tool calls"""
    sf = get_salesforce()
    if tool_name == "SALESFORCE_CREATE_ACCOUNT":
        return create_account(sf, arguments)
    if tool_name == "get_accounts":
        return get_accounts(sf, arguments)
    if tool_name == "SALESFORCE_DELETE_ACCOUNT":
        return delete_account(sf, arguments)
    if tool_name == "SALESFORCE_GET_ACCOUNT":
        return get_account(sf, arguments)
    if tool_name == "SALESFORCE_LIST_ACCOUNTS":
        return list_accounts(sf, arguments)
    if tool_name == "SALESFORCE_SEARCH_ACCOUNTS":
        return search_accounts(sf, arguments)
    if tool_name == "SALESFORCE_UPDATE_ACCOUNT":
        return update_account(sf, arguments)
    raise ValueError(f"Unknown account tool: {tool_name}")

# Map our snake_case field names to Salesforce Account API names (PascalCase)
ACCOUNT_FIELD_TO_API = {
    "type": "Type",
    "phone": "Phone",
    "website": "Website",
    "industry": "Industry",
    "annual_revenue": "AnnualRevenue",
    "number_of_employees": "NumberOfEmployees",
    "description": "Description",
    "billing_street": "BillingStreet",
    "billing_city": "BillingCity",
    "billing_state": "BillingState",
    "billing_postal_code": "BillingPostalCode",
    "billing_country": "BillingCountry",
    "shipping_street": "ShippingStreet",
    "shipping_city": "ShippingCity",
    "shipping_state": "ShippingState",
    "shipping_postal_code": "ShippingPostalCode",
    "shipping_country": "ShippingCountry",
    "account_source": "AccountSource",
    "fax": "Fax",
    "sic_desc": "SicDesc",
    "parent_id": "ParentId",
}

def create_account(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new account in Salesforce"""
    try:
        # Extract required fields
        name = arguments.get("name")
        if not name:
            raise ValueError("Account name is required")
        
        # Build account data
        account_data = {
            "Name": name
        }
        
        for field, sf_field in ACCOUNT_FIELD_TO_API.items():
            value = arguments.get(field)
            if value is not None:
                account_data[sf_field] = value
        
        # Add custom fields
        custom_fields = arguments.get("custom_fields", {})
        if custom_fields:
            account_data.update(custom_fields)
        
        # Create account
        account_sf = SFType('Account', sf.session_id, sf.sf_instance)
        result = account_sf.create(account_data)
        
        account_id = result["id"]
        print(f"[Account] Created account: {account_id}", file=sys.stderr)
        
        return {
            "success": True,
            "account_id": account_id,
            "message": f"Account '{name}' created successfully"
        }
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Account ERROR] {error_msg}", file=sys.stderr)
        return {
            "success": False,
            "error": error_msg
        }

def get_accounts(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch Salesforce accounts"""
    try:
        limit = arguments.get("limit", 5)
        if limit < 1 or limit > 100:
            limit = 5
        result = sf.query(f"SELECT Id, Name FROM Account LIMIT {limit}")
        accounts = result.get("records", [])
        return {"success": True, "accounts": accounts, "count": len(accounts)}
    except Exception as e:
        error_msg = str(e)
        print(f"[Accounts ERROR] {error_msg}", file=sys.stderr)
        return {"success": False, "error": error_msg}


def delete_account(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        account_id = arguments.get("account_id")
        if not account_id:
            raise ValueError("account_id is required")
        acc_sf = SFType("Account", sf.session_id, sf.sf_instance)
        acc_sf.delete(account_id)
        return {"success": True, "message": "Account deleted"}
    except Exception as e:
        print(f"[Account ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def get_account(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        account_id = arguments.get("account_id")
        if not account_id:
            raise ValueError("account_id is required")
        acc_sf = SFType("Account", sf.session_id, sf.sf_instance)
        rec = acc_sf.get(account_id)
        return {"success": True, "record": rec}
    except Exception as e:
        print(f"[Account ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def list_accounts(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        query = arguments.get("query")
        if not query:
            query = "SELECT Id, Name FROM Account LIMIT 2000"
        result = sf.query(str(query).strip())
        return {
            "success": True,
            "records": result.get("records", []),
            "totalSize": result.get("totalSize", 0),
            "done": result.get("done", True),
            "nextRecordsUrl": result.get("nextRecordsUrl"),
        }
    except Exception as e:
        print(f"[Accounts ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def _build_account_soql_where(params: Dict[str, Any]) -> List[str]:
    where = []
    if params.get("name"):
        where.append(f"Name LIKE '%{str(params['name']).replace(chr(39), chr(39)+chr(39))}%'")
    if params.get("type"):
        where.append(f"Type = '{str(params['type']).replace(chr(39), chr(39)+chr(39))}'")
    if params.get("industry"):
        where.append(f"Industry LIKE '%{str(params['industry']).replace(chr(39), chr(39)+chr(39))}%'")
    if params.get("phone"):
        where.append(f"Phone LIKE '%{str(params['phone']).replace(chr(39), chr(39)+chr(39))}%'")
    if params.get("website"):
        where.append(f"Website LIKE '%{str(params['website']).replace(chr(39), chr(39)+chr(39))}%'")
    if params.get("billing_city"):
        where.append(f"BillingCity LIKE '%{str(params['billing_city']).replace(chr(39), chr(39)+chr(39))}%'")
    if params.get("billing_state"):
        where.append(f"BillingState LIKE '%{str(params['billing_state']).replace(chr(39), chr(39)+chr(39))}%'")
    if params.get("billing_country"):
        where.append(f"BillingCountry LIKE '%{str(params['billing_country']).replace(chr(39), chr(39)+chr(39))}%'")
    return where


def search_accounts(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        limit = min(int(arguments.get("limit", 50)), 200)
        fields = arguments.get("fields") or "Id, Name, Type, Industry, Phone, BillingCity, BillingState, BillingCountry"
        where = _build_account_soql_where(arguments)
        where_clause = " AND ".join(where) if where else "Id != null"
        query = f"SELECT {fields} FROM Account WHERE {where_clause} LIMIT {limit}"
        result = sf.query(query)
        return {"success": True, "records": result.get("records", []), "totalSize": result.get("totalSize", 0)}
    except Exception as e:
        print(f"[Accounts ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def update_account(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        account_id = arguments.get("account_id")
        if not account_id:
            raise ValueError("account_id is required")
        update_data = {}
        for field, sf_field in ACCOUNT_FIELD_TO_API.items():
            if field == "parent_id":
                continue
            v = arguments.get(field)
            if v is not None:
                update_data[sf_field] = v
        if arguments.get("parent_id") is not None:
            update_data["ParentId"] = arguments["parent_id"]
        custom = arguments.get("custom_fields", {})
        if custom:
            update_data.update(custom)
        if not update_data:
            return {"success": True, "message": "No fields to update"}
        acc_sf = SFType("Account", sf.session_id, sf.sf_instance)
        acc_sf.update(account_id, update_data)
        return {"success": True, "account_id": account_id, "message": "Account updated"}
    except Exception as e:
        print(f"[Account ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


