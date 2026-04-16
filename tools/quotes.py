"""
Quote Operations
Handles Salesforce Quote creation from opportunities, detail payloads for UI review,
and accept/reject status updates.
"""
import os
import sys
from typing import Any, Dict, List, Optional

from simple_salesforce import SFType

from salesforce_config import get_salesforce

# Picklist values for Quote.Status (override if your org uses different API values)
QUOTE_STATUS_ACCEPTED = os.getenv("SF_QUOTE_STATUS_ACCEPTED", "Accepted").strip() or "Accepted"
QUOTE_STATUS_REJECTED = os.getenv("SF_QUOTE_STATUS_REJECTED", "Rejected").strip() or "Rejected"


def _soql_escape(s: str) -> str:
    return str(s).replace("'", "''")


def get_quote_tools() -> List[Dict[str, Any]]:
    """Return list of quote-related MCP tools"""
    return [
        {
            "name": "create_quote_from_opportunity",
            "description": (
                "Create a standard Quote and QuoteLineItems from an Opportunity's line items. "
                "Returns full quote and line details plus instructions for the user to accept or reject "
                f"in the UI; then call SALESFORCE_ACCEPT_QUOTE or SALESFORCE_REJECT_QUOTE (Status → "
                f"'{QUOTE_STATUS_ACCEPTED}' / '{QUOTE_STATUS_REJECTED}'). "
                f"Override picklist values with env SF_QUOTE_STATUS_ACCEPTED / SF_QUOTE_STATUS_REJECTED."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "opportunity_id": {
                        "type": "string",
                        "description": "The Salesforce Opportunity Id (15 or 18 characters)",
                    },
                    "opportunityId": {"type": "string", "description": "Same as opportunity_id"},
                },
                "required": [],
            },
        },
        {
            "name": "SALESFORCE_CREATE_QUOTE_FROM_OPPORTUNITY",
            "description": "Same as create_quote_from_opportunity (normalized MCP name).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "opportunity_id": {"type": "string"},
                    "opportunityId": {"type": "string"},
                },
                "required": [],
            },
        },
        {
            "name": "SALESFORCE_ACCEPT_QUOTE",
            "description": (
                f"Set Quote.Status to accepted value (default '{QUOTE_STATUS_ACCEPTED}') after the user "
                "approves the quote in the UI."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_id": {"type": "string", "description": "Quote Id from create_quote response"},
                    "quoteId": {"type": "string"},
                },
                "required": [],
            },
        },
        {
            "name": "SALESFORCE_REJECT_QUOTE",
            "description": (
                f"Set Quote.Status to rejected value (default '{QUOTE_STATUS_REJECTED}') after the user "
                "rejects the quote in the UI."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_id": {"type": "string", "description": "Quote Id from create_quote response"},
                    "quoteId": {"type": "string"},
                },
                "required": [],
            },
        },
    ]


def _normalize_quote_id_args(arguments: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(arguments or {})
    if out.get("quote_id") and str(out["quote_id"]).strip():
        out["quote_id"] = str(out["quote_id"]).strip()
        return out
    for alt in ("quoteId", "QuoteId", "id", "Id"):
        v = out.get(alt)
        if v is not None and str(v).strip():
            out["quote_id"] = str(v).strip()
            break
    return out


def _normalize_opportunity_id(arguments: Dict[str, Any]) -> Optional[str]:
    oid = arguments.get("opportunity_id") or arguments.get("opportunityId")
    if oid is None or not str(oid).strip():
        return None
    return str(oid).strip()


def handle_quote_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle quote-related tool calls"""
    sf = get_salesforce()
    t = str(tool_name).strip()

    if t in ("create_quote_from_opportunity", "SALESFORCE_CREATE_QUOTE_FROM_OPPORTUNITY"):
        opportunity_id = _normalize_opportunity_id(arguments if isinstance(arguments, dict) else {})
        if not opportunity_id:
            return {
                "success": False,
                "errorMessage": "Opportunity ID is required",
                "error": "Opportunity ID is required",
            }
        return create_quote_logic(sf, opportunity_id)

    if t == "SALESFORCE_ACCEPT_QUOTE":
        return set_quote_status_tool(sf, _normalize_quote_id_args(arguments), QUOTE_STATUS_ACCEPTED)

    if t == "SALESFORCE_REJECT_QUOTE":
        return set_quote_status_tool(sf, _normalize_quote_id_args(arguments), QUOTE_STATUS_REJECTED)

    raise ValueError(f"Unknown quote tool: {tool_name}")


def set_quote_status_tool(sf: Any, arguments: Dict[str, Any], status: str) -> Dict[str, Any]:
    """Update Quote.Status after user accept/reject in UI."""
    try:
        qid = arguments.get("quote_id")
        if not qid or not str(qid).strip():
            return {
                "success": False,
                "error": "quote_id is required",
                "errorMessage": "quote_id is required",
            }
        qid = str(qid).strip()
        if not qid.startswith("0Q0"):
            return {
                "success": False,
                "error": f"Invalid Quote Id (expected 0Q0 prefix): {qid}",
                "errorMessage": f"Invalid Quote Id: {qid}",
            }

        quote_sf = SFType("Quote", sf.session_id, sf.sf_instance)
        quote_sf.update(qid, {"Status": status})

        snap = _fetch_quote_snapshot(sf, qid)
        print(f"[Quote] Updated Quote {qid} Status={status}", file=sys.stderr)
        return {
            "success": True,
            "quote_id": qid,
            "status": status,
            "quote": snap.get("quote"),
            "message": f"Quote status set to {status}.",
        }
    except Exception as e:
        err = str(e)
        print(f"[Quote ERROR] set_quote_status: {err}", file=sys.stderr)
        return {"success": False, "error": err, "errorMessage": err}


def _fetch_quote_snapshot(sf: Any, quote_id: str) -> Dict[str, Any]:
    esc = _soql_escape(quote_id)
    q_quote = (
        "SELECT Id, Name, Status, QuoteNumber, TotalPrice, Subtotal, ExpirationDate, "
        "OpportunityId, Pricebook2Id, CreatedDate, LastModifiedDate "
        f"FROM Quote WHERE Id = '{esc}' LIMIT 1"
    )
    qr = sf.query(q_quote)
    qrecs = qr.get("records") or []
    quote_row = qrecs[0] if qrecs else None

    q_li = (
        "SELECT Id, LineNumber, Quantity, UnitPrice, ListPrice, Subtotal, Discount, TotalPrice, "
        "Description, PricebookEntry.Product2.Name, PricebookEntry.Product2.ProductCode "
        f"FROM QuoteLineItem WHERE QuoteId = '{esc}' ORDER BY LineNumber, CreatedDate"
    )
    lr = sf.query(q_li)
    lines = lr.get("records") or []

    line_details: List[Dict[str, Any]] = []
    for row in lines:
        pbe = row.get("PricebookEntry") or {}
        p2 = pbe.get("Product2") if isinstance(pbe.get("Product2"), dict) else {}
        line_details.append(
            {
                "Id": row.get("Id"),
                "LineNumber": row.get("LineNumber"),
                "Quantity": row.get("Quantity"),
                "UnitPrice": row.get("UnitPrice"),
                "ListPrice": row.get("ListPrice"),
                "Subtotal": row.get("Subtotal"),
                "Discount": row.get("Discount"),
                "TotalPrice": row.get("TotalPrice"),
                "Description": row.get("Description"),
                "ProductName": p2.get("Name") if isinstance(p2, dict) else None,
                "ProductCode": p2.get("ProductCode") if isinstance(p2, dict) else None,
            }
        )

    return {"quote": quote_row, "quote_line_details": line_details}


def create_quote_logic(sf: Any, opportunity_id: str) -> Dict[str, Any]:
    """
    Create Quote + QuoteLineItems from Opportunity OLIs; return details for UI review
    and instructions to accept/reject via MCP tools.
    """
    result: Dict[str, Any] = {
        "success": False,
        "quoteId": None,
        "opportunityId": None,
        "opportunityName": None,
        "accountId": None,
        "accountName": None,
        "accountPhone": None,
        "accountIndustry": None,
        "quoteLineCount": 0,
        "quoteLines": [],
        "quote": None,
        "quote_line_details": [],
        "ui_prompt_for_user": None,
        "next_tools": None,
        "errorMessage": None,
        "error": None,
    }

    try:
        oid = str(opportunity_id).strip()
        if not (oid.startswith("006") and len(oid) >= 15):
            raise ValueError(f"Invalid Opportunity ID format: {opportunity_id}")

        esc_opp = _soql_escape(oid)

        opp_query = f"""
            SELECT Id, Name, AccountId, Account.Name, Account.Phone, Account.Industry, Pricebook2Id
            FROM Opportunity
            WHERE Id = '{esc_opp}'
            LIMIT 1
        """
        opp_result = sf.query(opp_query)

        if not opp_result.get("records"):
            raise ValueError(f"Opportunity with Id {opportunity_id} not found")

        opp = opp_result["records"][0]

        if not opp.get("Pricebook2Id"):
            raise ValueError("Opportunity must have a Pricebook assigned")

        quote_name = f"{opp['Name']} - Quote"
        quote_data = {
            "Name": quote_name,
            "OpportunityId": opp["Id"],
            "Pricebook2Id": opp["Pricebook2Id"],
        }

        quote_sf = SFType("Quote", sf.session_id, sf.sf_instance)
        quote_result = quote_sf.create(quote_data)
        quote_id = quote_result["id"]

        result["quoteId"] = quote_id
        result["opportunityId"] = opp["Id"]
        result["opportunityName"] = opp["Name"]

        account = opp.get("Account")
        if account and isinstance(account, dict):
            result["accountId"] = account.get("Id") or opp.get("AccountId")
            result["accountName"] = account.get("Name")
            result["accountPhone"] = account.get("Phone")
            result["accountIndustry"] = account.get("Industry")
        else:
            result["accountId"] = opp.get("AccountId")

        esc_opp_inner = _soql_escape(opp["Id"])
        oli_query = f"""
            SELECT Id, Quantity, UnitPrice, PricebookEntryId,
                   PricebookEntry.UnitPrice, PricebookEntry.Product2.Name
            FROM OpportunityLineItem
            WHERE OpportunityId = '{esc_opp_inner}'
        """
        oli_result = sf.query(oli_query)

        created_line_summaries: List[Dict[str, Any]] = []
        if oli_result.get("records"):
            qli_sf = SFType("QuoteLineItem", sf.session_id, sf.sf_instance)
            for oli in oli_result["records"]:
                pricebook_entry_id = oli.get("PricebookEntryId")
                if not pricebook_entry_id:
                    continue

                qli_data = {
                    "QuoteId": quote_id,
                    "PricebookEntryId": pricebook_entry_id,
                    "Quantity": oli.get("Quantity", 0),
                    "UnitPrice": oli.get("UnitPrice", 0),
                }
                qli_res = qli_sf.create(qli_data)
                qli_id = qli_res.get("id")
                result["quoteLineCount"] += 1

                pbe = oli.get("PricebookEntry") or {}
                p2 = pbe.get("Product2") if isinstance(pbe.get("Product2"), dict) else {}
                created_line_summaries.append(
                    {
                        "quote_line_item_id": qli_id,
                        "opportunity_line_item_id": oli.get("Id"),
                        "quantity": oli.get("Quantity"),
                        "unit_price": oli.get("UnitPrice"),
                        "product_name": (p2 or {}).get("Name"),
                    }
                )

        result["quoteLines"] = created_line_summaries

        snap = _fetch_quote_snapshot(sf, quote_id)
        result["quote"] = snap.get("quote")
        result["quote_line_details"] = snap.get("quote_line_details") or []

        result["ui_prompt_for_user"] = (
            "Review the quote summary and line items above. "
            "When the user decides in the UI: if they **accept**, call tool **SALESFORCE_ACCEPT_QUOTE** "
            f"with quote_id **{quote_id}** (sets Status to '{QUOTE_STATUS_ACCEPTED}'). "
            "If they **reject**, call **SALESFORCE_REJECT_QUOTE** with the same quote_id "
            f"(sets Status to '{QUOTE_STATUS_REJECTED}')."
        )
        result["next_tools"] = {
            "on_user_accept": {
                "tool": "SALESFORCE_ACCEPT_QUOTE",
                "arguments": {"quote_id": quote_id},
            },
            "on_user_reject": {
                "tool": "SALESFORCE_REJECT_QUOTE",
                "arguments": {"quote_id": quote_id},
            },
        }

        result["success"] = True
        print(f"[Quote] Created quote {quote_id} for Opp {opp['Id']} ({result['quoteLineCount']} lines)", file=sys.stderr)

    except Exception as e:
        result["errorMessage"] = str(e)
        result["error"] = str(e)
        print(f"[Quote ERROR] {e}", file=sys.stderr)

    return result

