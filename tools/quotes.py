"""
Quote Operations
Handles Salesforce Quote creation from opportunities
"""
import sys
import json
from typing import Dict, Any, List
from simple_salesforce import SFType
from salesforce_config import get_salesforce

def get_quote_tools() -> List[Dict[str, Any]]:
    """Return list of quote-related MCP tools"""
    return [
        {
            "name": "create_quote_from_opportunity",
            "description": "Create a Standard Quote and Quote Line Items from an Opportunity.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "opportunity_id": {
                        "type": "string",
                        "description": "The Salesforce Opportunity ID (required)"
                    }
                },
                "required": ["opportunity_id"]
            }
        }
    ]

def handle_quote_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle quote-related tool calls"""
    sf = get_salesforce()
    
    if tool_name == "create_quote_from_opportunity":
        opportunity_id = arguments.get("opportunity_id")
        if not opportunity_id:
            raise ValueError("Opportunity ID is required")
        return create_quote_logic(opportunity_id)
    else:
        raise ValueError(f"Unknown quote tool: {tool_name}")

def create_quote_logic(opportunity_id: str) -> Dict[str, Any]:
    """Create quote logic (same as original)"""
    result = {
        "quoteId": None,
        "opportunityId": None,
        "opportunityName": None,
        "accountId": None,
        "accountName": None,
        "accountPhone": None,
        "accountIndustry": None,
        "quoteLineCount": 0,
        "quoteLines": [],
        "errorMessage": None
    }
    
    try:
        if not opportunity_id.startswith("006"):
            raise ValueError(f"Invalid Opportunity ID format: {opportunity_id}")
        
        sf = get_salesforce()
        
        # Fetch Opportunity
        opp_query = f"""
            SELECT Id, Name, AccountId, Account.Name, Account.Phone, Account.Industry, Pricebook2Id
            FROM Opportunity
            WHERE Id = '{opportunity_id}'
            LIMIT 1
        """
        opp_result = sf.query(opp_query)
        
        if not opp_result.get("records"):
            raise ValueError(f"Opportunity with Id {opportunity_id} not found")
        
        opp = opp_result["records"][0]
        
        if not opp.get("Pricebook2Id"):
            raise ValueError("Opportunity must have a Pricebook assigned")
        
        # Create Quote
        quote_name = f"{opp['Name']} - Quote"
        quote_data = {
            "Name": quote_name,
            "OpportunityId": opp["Id"],
            "Pricebook2Id": opp["Pricebook2Id"]
        }
        
        quote_sf = SFType('Quote', sf.session_id, sf.sf_instance)
        quote_result = quote_sf.create(quote_data)
        quote_id = quote_result["id"]
        
        result["quoteId"] = quote_id
        result["opportunityId"] = opp["Id"]
        result["opportunityName"] = opp["Name"]
        
        # Handle Account
        account = opp.get("Account")
        if account and isinstance(account, dict):
            result["accountId"] = account.get("Id") or opp.get("AccountId")
            result["accountName"] = account.get("Name")
            result["accountPhone"] = account.get("Phone")
            result["accountIndustry"] = account.get("Industry")
        else:
            result["accountId"] = opp.get("AccountId")
        
        # Fetch and create Quote Line Items
        oli_query = f"""
            SELECT Id, Quantity, UnitPrice, PricebookEntryId, 
                   PricebookEntry.UnitPrice, Product2.SKU__c
            FROM OpportunityLineItem
            WHERE OpportunityId = '{opp["Id"]}'
        """
        oli_result = sf.query(oli_query)
        
        if oli_result.get("records"):
            for oli in oli_result["records"]:
                pricebook_entry_id = oli.get("PricebookEntryId")
                if not pricebook_entry_id:
                    continue
                
                qli_data = {
                    "QuoteId": quote_id,
                    "PricebookEntryId": pricebook_entry_id,
                    "Quantity": oli.get("Quantity", 0),
                    "UnitPrice": oli.get("UnitPrice", 0)
                }
                
                qli_sf = SFType('QuoteLineItem', sf.session_id, sf.sf_instance)
                qli_sf.create(qli_data)
                
                result["quoteLineCount"] += 1
        
    except Exception as e:
        result["errorMessage"] = str(e)
        print(f"[Quote ERROR] {e}", file=sys.stderr)
    
    return result


