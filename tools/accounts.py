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
        }
    ]

def handle_account_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle account-related tool calls"""
    sf = get_salesforce()
    
    if tool_name == "SALESFORCE_CREATE_ACCOUNT":
        return create_account(sf, arguments)
    elif tool_name == "get_accounts":
        return get_accounts(sf, arguments)
    else:
        raise ValueError(f"Unknown account tool: {tool_name}")

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
        
        # Add optional fields
        optional_fields = [
            "type", "phone", "website", "industry", "annual_revenue",
            "number_of_employees", "description", "billing_street",
            "billing_city", "billing_state", "billing_postal_code",
            "billing_country", "shipping_street", "shipping_city",
            "shipping_state", "shipping_postal_code", "shipping_country",
            "account_source", "fax", "sic_desc", "parent_id"
        ]
        
        for field in optional_fields:
            value = arguments.get(field)
            if value is not None:
                # Convert field name to Salesforce API name (capitalize first letter)
                sf_field = field[0].upper() + field[1:] if field else field
                # Handle special cases
                if field == "type":
                    sf_field = "Type"
                elif field == "account_source":
                    sf_field = "AccountSource"
                elif field == "parent_id":
                    sf_field = "ParentId"
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
        
        print(f"[Accounts] Fetching {limit} accounts...", file=sys.stderr)
        result = sf.query(f"SELECT Id, Name FROM Account LIMIT {limit}")
        accounts = result.get("records", [])
        
        return {
            "success": True,
            "accounts": accounts,
            "count": len(accounts)
        }
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Accounts ERROR] {error_msg}", file=sys.stderr)
        return {
            "success": False,
            "error": error_msg
        }

