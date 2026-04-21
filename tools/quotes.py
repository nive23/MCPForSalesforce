"""
Quote Operations
Handles Salesforce Quote creation from opportunities, detail payloads for UI review,
and accept/reject status updates.
"""
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from simple_salesforce import SFType

from salesforce_config import get_salesforce

# Picklist values for Quote.Status (override if your org uses different API values)
QUOTE_STATUS_ACCEPTED = os.getenv("SF_QUOTE_STATUS_ACCEPTED", "Accepted").strip() or "Accepted"
QUOTE_STATUS_REJECTED = os.getenv("SF_QUOTE_STATUS_REJECTED", "Rejected").strip() or "Rejected"
# Optional extra Product2 field in SOQL for org-specific SKU (e.g. SKU__c). Must be API-safe.
_PRODUCT_SKU_CUSTOM_FIELD = os.getenv("SF_PRODUCT_SKU_CUSTOM_FIELD", "").strip()
# Comma-separated Product2 API names, first populated wins (before heuristic fallback). Example:
# SF_PRODUCT_SKU_FIELDS=SKU_Id__c,StockKeepingUnit,ProductCode
_SF_PRODUCT_SKU_FIELDS_RAW = os.getenv("SF_PRODUCT_SKU_FIELDS", "").strip()
_API_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
# When true (default), QuoteLineItem SOQL tries Product2.SKU__c and retries without it if the org has no field.
_AUTO_PROBE_PRODUCT2_SKU__C = (
    os.getenv("SF_DISABLE_AUTO_SKU__C", "").strip().lower() not in ("1", "true", "yes")
)
_DEFAULT_PROBE_SKU_FIELD = "SKU__c"


def _parse_env_csv_api_names(raw: str) -> List[str]:
    out: List[str] = []
    for part in raw.split(","):
        name = part.strip()
        if name and _API_NAME_RE.match(name):
            out.append(name)
    return out


def _product2_sku_field_names() -> List[str]:
    """Product2 fields to SELECT for SKU (deduped, stable order)."""
    seen: set = set()
    out: List[str] = []
    for name in _parse_env_csv_api_names(_SF_PRODUCT_SKU_FIELDS_RAW):
        if name not in seen:
            seen.add(name)
            out.append(name)
    if _PRODUCT_SKU_CUSTOM_FIELD and _API_NAME_RE.match(_PRODUCT_SKU_CUSTOM_FIELD):
        c = _PRODUCT_SKU_CUSTOM_FIELD
        if c not in seen:
            out.insert(0, c)
            seen.add(c)
    for d in ("StockKeepingUnit", "ProductCode"):
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _product2_sku_names_for_query(probe_sku_c: bool) -> List[str]:
    """Field API names on Product2 to SELECT; optionally prepend SKU__c for orgs that define it."""
    names = list(_product2_sku_field_names())
    if probe_sku_c and _DEFAULT_PROBE_SKU_FIELD not in names:
        names.insert(0, _DEFAULT_PROBE_SKU_FIELD)
    return names


def _product2_sku_select_fragment_from_names(field_names: List[str]) -> str:
    parts = ["PricebookEntry.Product2.Id", "PricebookEntry.Product2.Name"]
    for f in field_names:
        parts.append(f"PricebookEntry.Product2.{f}")
    return ", ".join(parts)


def _soql_error_suggests_missing_sku_c(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "sku__c" not in msg:
        return False
    return any(
        t in msg
        for t in (
            "invalid_field",
            "invalid field",
            "no such column",
            "unknown_field",
            "could not resolve",
            "malformed_query",
        )
    )


def _soql_escape(s: str) -> str:
    return str(s).replace("'", "''")


def _is_salesforce_id(s: str) -> bool:
    """True for typical 15- or 18-character Salesforce record ids."""
    if not s or len(s) not in (15, 18):
        return False
    return bool(re.match(r"^[a-zA-Z0-9]{15}$|^[a-zA-Z0-9]{18}$", s))


def _empty_snap_for_apex() -> Dict[str, Any]:
    return {
        "opportunity_id": None,
        "opportunity_name": None,
        "opportunity_account": {},
        "quote_line_details": [],
    }


def _quote_id_for_opportunity(sf: Any, opportunity_id: str) -> Optional[str]:
    """Most recently modified Quote on this Opportunity (common when user passes Opp Id by mistake)."""
    esc = _soql_escape(opportunity_id)
    soql = (
        f"SELECT Id FROM Quote WHERE OpportunityId = '{esc}' "
        "ORDER BY LastModifiedDate DESC LIMIT 1"
    )
    rows = _soql_query_all_records(sf, soql)
    if not rows:
        return None
    rid = rows[0].get("Id")
    return str(rid).strip() if rid else None


def _fetch_opportunity_minimal_for_apex(sf: Any, opportunity_id: str) -> Dict[str, Any]:
    """Opportunity + Account fields for quoteResult when no Quote exists (or for error context)."""
    esc = _soql_escape(opportunity_id)
    q = (
        "SELECT Id, Name, AccountId, Account.Name, Account.Phone, Account.Industry "
        f"FROM Opportunity WHERE Id = '{esc}' LIMIT 1"
    )
    try:
        qr = sf.query(q)
    except Exception:
        return _empty_snap_for_apex()
    recs = qr.get("records") or []
    if not recs:
        return _empty_snap_for_apex()
    opp = recs[0]
    acc = opp.get("Account") if isinstance(opp.get("Account"), dict) else {}
    oa = {
        "account_id": opp.get("AccountId") or acc.get("Id"),
        "account_name": acc.get("Name"),
        "account_phone": acc.get("Phone"),
        "account_industry": acc.get("Industry"),
    }
    return {
        "opportunity_id": opp.get("Id"),
        "opportunity_name": opp.get("Name"),
        "opportunity_account": oa,
        "quote_line_details": [],
    }


def _soql_query_all_records(sf: Any, soql: str) -> List[Dict[str, Any]]:
    """Return every SOQL row (uses query_all so all batches beyond 2000 rows are included)."""
    fn = getattr(sf, "query_all", None)
    if callable(fn):
        out = fn(soql)
        return list(out.get("records") or [])
    out = sf.query(soql)
    return list(out.get("records") or [])


def _opportunity_summary_from_quote_row(quote_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Opportunity Id + Name from the Quote's Opportunity lookup."""
    empty = {"opportunity_id": None, "opportunity_name": None}
    if not quote_row or not isinstance(quote_row, dict):
        return dict(empty)
    opp = quote_row.get("Opportunity")
    if not isinstance(opp, dict):
        return {
            "opportunity_id": quote_row.get("OpportunityId"),
            "opportunity_name": None,
        }
    # Ignore relationship "attributes" wrapper; Name/Id live on the same dict.
    name = opp.get("Name")
    oid = opp.get("Id") or quote_row.get("OpportunityId")
    return {
        "opportunity_id": oid,
        "opportunity_name": name,
    }


def _enrich_opportunity_summary(sf: Any, summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    If Name is missing (some clients/API paths omit nested Opportunity on Quote), load Opportunity by Id.
    """
    out = dict(summary or {})
    oid = out.get("opportunity_id")
    if not oid or str(oid).strip() == "":
        return out
    if out.get("opportunity_name") is not None and str(out.get("opportunity_name")).strip() != "":
        return out
    try:
        esc = _soql_escape(str(oid).strip())
        r2 = sf.query(f"SELECT Id, Name FROM Opportunity WHERE Id = '{esc}' LIMIT 1")
        recs = r2.get("records") or []
        if recs:
            out["opportunity_id"] = recs[0].get("Id") or oid
            out["opportunity_name"] = recs[0].get("Name")
    except Exception as ex:
        print(f"[Quote] Opportunity lookup fallback failed: {ex}", file=sys.stderr)
    return out


def _enrich_account_summary(sf: Any, quote_row: Optional[Dict[str, Any]], oa: Dict[str, Any]) -> Dict[str, Any]:
    """
    If Account.Name is missing on the nested relationship, load Account by Id (Opportunity.AccountId or oa).
    """
    out = dict(oa or {})
    aid = out.get("account_id")
    if not aid or str(aid).strip() == "":
        if isinstance(quote_row, dict):
            opp = quote_row.get("Opportunity")
            if isinstance(opp, dict):
                aid = opp.get("AccountId") or aid
                out["account_id"] = aid
    if not aid or str(aid).strip() == "":
        return out
    if out.get("account_name") is not None and str(out.get("account_name")).strip() != "":
        return out
    try:
        esc = _soql_escape(str(aid).strip())
        r2 = sf.query(
            f"SELECT Id, Name, Phone, Industry FROM Account WHERE Id = '{esc}' LIMIT 1"
        )
        recs = r2.get("records") or []
        if recs:
            a = recs[0]
            out["account_id"] = a.get("Id") or aid
            out["account_name"] = a.get("Name")
            if out.get("account_phone") is None:
                out["account_phone"] = a.get("Phone")
            if out.get("account_industry") is None:
                out["account_industry"] = a.get("Industry")
    except Exception as ex:
        print(f"[Quote] Account lookup fallback failed: {ex}", file=sys.stderr)
    return out


def _opportunity_account_from_quote_row(quote_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Account on the Quote's Opportunity (Id, Name, Phone, Industry)."""
    empty = {
        "account_id": None,
        "account_name": None,
        "account_phone": None,
        "account_industry": None,
    }
    if not quote_row or not isinstance(quote_row, dict):
        return dict(empty)
    opp = quote_row.get("Opportunity")
    if not isinstance(opp, dict):
        return dict(empty)
    acc = opp.get("Account")
    if isinstance(acc, dict):
        return {
            "account_id": acc.get("Id") or opp.get("AccountId"),
            "account_name": acc.get("Name"),
            "account_phone": acc.get("Phone"),
            "account_industry": acc.get("Industry"),
        }
    return {
        "account_id": opp.get("AccountId"),
        "account_name": None,
        "account_phone": None,
        "account_industry": None,
    }


def _collect_product2_sku_candidates(
    p2: Dict[str, Any],
    field_names: Optional[List[str]] = None,
) -> Dict[str, str]:
    if not isinstance(p2, dict):
        return {}
    names = field_names if field_names is not None else _product2_sku_field_names()
    out: Dict[str, str] = {}
    for fname in names:
        v = p2.get(fname)
        if v is not None and str(v).strip():
            out[fname] = str(v).strip()
    return out


def _pick_sku_from_candidates(candidates: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (sku_value, source_field_api_name).
    If SF_PRODUCT_SKU_FIELDS is set: first listed field with a value wins.
    Otherwise: legacy custom field if present, else prefer values containing 'sku-',
    else the longest string (full org SKUs often longer than short ProductCode).
    """
    if not candidates:
        return None, None
    explicit = _parse_env_csv_api_names(_SF_PRODUCT_SKU_FIELDS_RAW)
    for fname in explicit:
        if fname in candidates:
            return candidates[fname], fname
    lf = _PRODUCT_SKU_CUSTOM_FIELD
    if lf and lf in candidates:
        return candidates[lf], lf
    # Common org field (matches Apex Product2.SKU__c) — only used when present in SOQL/candidates.
    if _DEFAULT_PROBE_SKU_FIELD in candidates:
        return candidates[_DEFAULT_PROBE_SKU_FIELD], _DEFAULT_PROBE_SKU_FIELD
    items = list(candidates.items())
    for fname, val in items:
        if "sku-" in val.lower():
            return val, fname
    fname, val = max(items, key=lambda kv: len(kv[1]))
    return val, fname


def _resolved_product_sku_bundle(
    p2: Dict[str, Any],
    field_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """sku + which Product2 field won + all non-empty candidate values for debugging."""
    cand = _collect_product2_sku_candidates(p2, field_names=field_names)
    sku, src = _pick_sku_from_candidates(cand)
    return {"sku": sku, "sku_source_field": src, "sku_candidates": cand}


def _quote_line_product_sku_rows(line_details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compact list of product2 Id + SKU per quote line (sent on create and on status update)."""
    out: List[Dict[str, Any]] = []
    for row in line_details:
        out.append(
            {
                "quote_line_item_id": row.get("Id"),
                "product2_id": row.get("Product2Id"),
                "product_name": row.get("ProductName"),
                "product_code": row.get("ProductCode"),
                "stock_keeping_unit": row.get("StockKeepingUnit"),
                "sku": row.get("sku"),
                "sku_source_field": row.get("sku_source_field"),
                "sku_candidates": row.get("sku_candidates"),
            }
        )
    return out


def _apex_sku_id_from_line(line: Dict[str, Any]) -> Optional[str]:
    """Match Apex QuoteLineResponse.skuId (Product2.SKU__c) when that field is queried."""
    cand = line.get("sku_candidates") if isinstance(line.get("sku_candidates"), dict) else {}
    if cand.get("SKU__c") is not None and str(cand["SKU__c"]).strip():
        return str(cand["SKU__c"]).strip()
    v = line.get("sku")
    if v is not None and str(v).strip():
        return str(v).strip()
    return None


def _apex_quote_line_response(line: Dict[str, Any]) -> Dict[str, Any]:
    """One row matching Apex QuoteLineResponse (InvocableVariable names)."""
    return {
        "skuId": _apex_sku_id_from_line(line),
        "listPrice": line.get("ListPrice"),
        "salesPrice": line.get("UnitPrice"),
        "quantity": line.get("Quantity"),
    }


def _apex_quote_result_payload(
    quote_id: Optional[str],
    snap: Dict[str, Any],
    *,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Payload aligned with Apex CreateQuoteFromOpportunity.QuoteResult / QuoteLineResponse.
    On success, errorMessage is None. Include Product2.SKU__c in SOQL via SF_PRODUCT_SKU_FIELDS
    or SF_PRODUCT_SKU_CUSTOM_FIELD. SKU__c is auto-queried when present on Product2.
    """
    oa = snap.get("opportunity_account") if isinstance(snap.get("opportunity_account"), dict) else {}
    details = snap.get("quote_line_details") if isinstance(snap.get("quote_line_details"), list) else []
    quote_lines = [_apex_quote_line_response(row) for row in details if isinstance(row, dict)]
    return {
        "quoteId": quote_id,
        "opportunityId": snap.get("opportunity_id"),
        "opportunityName": snap.get("opportunity_name"),
        "accountId": oa.get("account_id"),
        "accountName": oa.get("account_name"),
        "accountPhone": oa.get("account_phone"),
        "accountIndustry": oa.get("account_industry"),
        "quoteLineCount": len(quote_lines),
        "quoteLines": quote_lines,
        "errorMessage": error_message,
    }


def _format_quote_lines_for_ui(line_details: List[Dict[str, Any]]) -> str:
    """Plain-text table of every quote line for UI / Claude (no omitted rows)."""
    if not line_details:
        return "(No quote line items)"
    lines_out = [
        "Line# | Product | Product2 Id | SKU | Qty | Unit price | Subtotal | Total",
        "------|---------|---------------|-----|-----|-------------|----------|------",
    ]
    for row in line_details:
        ln = row.get("LineNumber")
        if ln is None:
            ln = "-"
        name = row.get("ProductName") or row.get("Description") or "(no name)"
        name = str(name).replace("|", "/")
        pid = row.get("Product2Id") or "-"
        sku = row.get("sku") or row.get("StockKeepingUnit") or row.get("ProductCode") or "-"
        sku = str(sku).replace("|", "/")
        pid = str(pid).replace("|", "/")
        lines_out.append(
            f"{ln} | {name} | {pid} | {sku} | {row.get('Quantity')} | {row.get('UnitPrice')} | "
            f"{row.get('Subtotal')} | {row.get('TotalPrice')}"
        )
    return "\n".join(lines_out)


def get_quote_tools() -> List[Dict[str, Any]]:
    """Return list of quote-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_SET_QUOTE_STATUS",
            "description": (
                "**Use this after the user accepts or rejects a quote.** Sets Quote.Status. "
                "Arguments: quote_id (or quoteId, or opportunity_id / opportunityId), decision = 'accept' or 'reject' "
                "(also accepted: approved / rejected). Same as SALESFORCE_ACCEPT_QUOTE / SALESFORCE_REJECT_QUOTE. "
                "**quote_id may be an Opportunity Id (006...)** — the server uses the most recently modified Quote "
                "on that Opportunity. Every response includes **quoteResult** (Apex-aligned): quoteId, "
                "opportunityId, opportunityName, accountId, accountName, accountPhone, accountIndustry, "
                "quoteLineCount, quoteLines[{skuId, listPrice, salesPrice, quantity}], errorMessage. "
                "Product2.SKU__c is queried automatically when the field exists; set SF_DISABLE_AUTO_SKU__C=1 "
                "if your org has no SKU__c. Other SKU API names: SF_PRODUCT_SKU_FIELDS or SF_PRODUCT_SKU_CUSTOM_FIELD."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_id": {
                        "type": "string",
                        "description": "Quote Id (0Q0..., 15/18 chars) or Opportunity Id (006...); latest Quote on Opp is used",
                    },
                    "quoteId": {"type": "string"},
                    "opportunity_id": {
                        "type": "string",
                        "description": "Optional if quote_id set; otherwise same as passing 006... as quote_id",
                    },
                    "opportunityId": {"type": "string"},
                    "decision": {
                        "type": "string",
                        "description": "accept | reject (case-insensitive; accept also allows approve/approved)",
                    },
                    "status": {
                        "type": "string",
                        "description": "Optional synonym for decision: accept or reject",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "create_quote_from_opportunity",
            "description": (
                "Create a standard Quote and QuoteLineItems from an Opportunity's line items. "
                "Returns full quote and line details plus instructions for the user to accept or reject "
                f"in the UI; then call **SALESFORCE_SET_QUOTE_STATUS** with quote_id (0Q0... or the same 006... "
                f"Opportunity Id) and decision 'accept' or 'reject' (Status → '{QUOTE_STATUS_ACCEPTED}' / "
                f"'{QUOTE_STATUS_REJECTED}'). "
                "Aliases: SALESFORCE_ACCEPT_QUOTE / SALESFORCE_REJECT_QUOTE. "
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
            "description": (
                "Same as create_quote_from_opportunity. After creation, use SALESFORCE_SET_QUOTE_STATUS "
                "to accept or reject."
            ),
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
                "approves the quote in the UI. **quote_id** may be Quote Id (0Q0...) or Opportunity Id (006...). "
                "Response always includes **quoteResult** (Apex CreateQuoteFromOpportunity.QuoteResult shape)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_id": {
                        "type": "string",
                        "description": "Quote Id (0Q0...) or Opportunity Id (006...); latest Quote on Opp is used",
                    },
                    "quoteId": {"type": "string"},
                    "opportunity_id": {"type": "string"},
                    "opportunityId": {"type": "string"},
                },
                "required": [],
            },
        },
        {
            "name": "SALESFORCE_REJECT_QUOTE",
            "description": (
                f"Set Quote.Status to rejected value (default '{QUOTE_STATUS_REJECTED}') after the user "
                "rejects the quote in the UI. quote_id may be 0Q0... or 006... (latest Quote). "
                "Response includes **quoteResult** (Apex-aligned)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_id": {
                        "type": "string",
                        "description": "Quote Id (0Q0...) or Opportunity Id (006...); latest Quote on Opp is used",
                    },
                    "quoteId": {"type": "string"},
                    "opportunity_id": {"type": "string"},
                    "opportunityId": {"type": "string"},
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
    if not out.get("quote_id"):
        oid = out.get("opportunity_id") or out.get("opportunityId")
        if oid is not None and str(oid).strip():
            out["quote_id"] = str(oid).strip()
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

    if t == "SALESFORCE_SET_QUOTE_STATUS":
        return set_quote_status_by_decision(sf, _normalize_quote_id_args(arguments))

    if t == "SALESFORCE_ACCEPT_QUOTE":
        return set_quote_status_tool(sf, _normalize_quote_id_args(arguments), QUOTE_STATUS_ACCEPTED)

    if t == "SALESFORCE_REJECT_QUOTE":
        return set_quote_status_tool(sf, _normalize_quote_id_args(arguments), QUOTE_STATUS_REJECTED)

    raise ValueError(f"Unknown quote tool: {tool_name}")


def set_quote_status_by_decision(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve decision accept/reject and delegate to set_quote_status_tool."""
    raw = (
        arguments.get("decision")
        or arguments.get("status")
        or arguments.get("action")
        or ""
    )
    d = str(raw).strip().lower()
    if d in ("accept", "accepted", "approve", "approved", "yes", "ok", "true", "1"):
        return set_quote_status_tool(sf, _normalize_quote_id_args(arguments), QUOTE_STATUS_ACCEPTED)
    if d in ("reject", "rejected", "deny", "denied", "decline", "declined", "no", "false", "0"):
        return set_quote_status_tool(sf, _normalize_quote_id_args(arguments), QUOTE_STATUS_REJECTED)
    return {
        "success": False,
        "error": (
            "SALESFORCE_SET_QUOTE_STATUS requires decision (or status) of 'accept' or 'reject' "
            f"(got {raw!r})."
        ),
        "errorMessage": "decision must be accept or reject",
        "quoteResult": _apex_quote_result_payload(
            None, _empty_snap_for_apex(), error_message="decision must be accept or reject"
        ),
    }


def set_quote_status_tool(sf: Any, arguments: Dict[str, Any], status: str) -> Dict[str, Any]:
    """Update Quote.Status after user accept/reject in UI."""
    args = _normalize_quote_id_args(arguments if isinstance(arguments, dict) else {})
    raw_in = args.get("quote_id")
    if not raw_in or not str(raw_in).strip():
        err = (
            "quote_id (or quoteId) is required. Use a Quote Id (0Q0...) or Opportunity Id (006...); "
            "opportunity_id is accepted if quote_id is omitted."
        )
        qr = _apex_quote_result_payload(None, _empty_snap_for_apex(), error_message=err)
        return {"success": False, "error": err, "errorMessage": err, "quoteResult": qr}

    raw = str(raw_in).strip()
    resolved_from_opportunity_id: Optional[str] = None
    qid: Optional[str] = None

    if raw.startswith("0Q0") and _is_salesforce_id(raw):
        qid = raw
    elif raw.startswith("006") and _is_salesforce_id(raw):
        resolved_from_opportunity_id = raw
        qid = _quote_id_for_opportunity(sf, raw)
        if not qid:
            snap_opp = _fetch_opportunity_minimal_for_apex(sf, raw)
            err = (
                f"No Quote found on Opportunity {raw}. Create a quote for this opportunity first, "
                "then call accept again (Opportunity Id is accepted and resolves to the latest Quote)."
            )
            return {
                "success": False,
                "error": err,
                "errorMessage": err,
                "opportunity_id": raw,
                "quoteResult": _apex_quote_result_payload(None, snap_opp, error_message=err),
            }
    else:
        err = (
            f"Invalid Id {raw!r}: pass a Quote Id (0Q0..., 15 or 18 chars) or an Opportunity Id "
            f"(006..., 15 or 18 chars). The server resolves the most recently modified Quote on that Opportunity."
        )
        return {
            "success": False,
            "error": err,
            "errorMessage": err,
            "quoteResult": _apex_quote_result_payload(None, _empty_snap_for_apex(), error_message=err),
        }

    try:
        quote_sf = SFType("Quote", sf.session_id, sf.sf_instance)
        quote_sf.update(qid, {"Status": status})

        snap = _fetch_quote_snapshot(sf, qid)
        oa = snap.get("opportunity_account") or {}
        sku_rows = snap.get("quote_line_product_skus") or []
        oid = snap.get("opportunity_id")
        oname = snap.get("opportunity_name")
        print(f"[Quote] Updated Quote {qid} Status={status}", file=sys.stderr)
        out: Dict[str, Any] = {
            "success": True,
            "quote_id": qid,
            "status": status,
            "quote": snap.get("quote"),
            "opportunity_id": oid,
            "opportunity_name": oname,
            "OpportunityId": oid,
            "OpportunityName": oname,
            "opportunity": snap.get("opportunity") or {"id": oid, "name": oname},
            "ui_opportunity_header": snap.get("ui_opportunity_header"),
            "quote_line_details": snap.get("quote_line_details"),
            "quote_line_details_count": snap.get("quote_line_details_count"),
            "quote_line_product_skus": sku_rows,
            "ui_formatted_quote_lines": snap.get("ui_formatted_quote_lines"),
            "opportunity_account": oa,
            "account": snap.get("account") or {"id": oa.get("account_id"), "name": oa.get("account_name")},
            "AccountId": snap.get("AccountId") or oa.get("account_id"),
            "AccountName": snap.get("AccountName") or oa.get("account_name"),
            "ui_account_header": snap.get("ui_account_header"),
            "accountId": oa.get("account_id"),
            "accountName": oa.get("account_name"),
            "accountPhone": oa.get("account_phone"),
            "accountIndustry": oa.get("account_industry"),
            "message": f"Quote status set to {status}.",
            "quoteResult": _apex_quote_result_payload(qid, snap, error_message=None),
        }
        if resolved_from_opportunity_id:
            out["quote_id_resolved_from_opportunity_id"] = resolved_from_opportunity_id
        if str(status).strip() == str(QUOTE_STATUS_ACCEPTED).strip():
            out["product_skus_on_accept"] = sku_rows
            acc_line = snap.get("ui_account_header") or (
                f"Account: {oa.get('account_name') or '(n/a)'}  |  Account Id: {oa.get('account_id') or '(n/a)'}"
            )
            out["ui_quote_acceptance_header"] = (
                f"{acc_line}\n"
                f"{snap.get('ui_opportunity_header') or ''}\n"
                f"Quote: {snap.get('quote', {}).get('Name') if isinstance(snap.get('quote'), dict) else ''}  |  "
                f"Quote Id: {qid}  |  Quote Number: "
                f"{(snap.get('quote') or {}).get('QuoteNumber') if isinstance(snap.get('quote'), dict) else ''}  |  "
                f"Status: {status}"
            ).strip()
        return out
    except Exception as e:
        err = str(e)
        print(f"[Quote ERROR] set_quote_status: {err}", file=sys.stderr)
        snap_fb: Dict[str, Any] = _empty_snap_for_apex()
        try:
            snap_fb = _fetch_quote_snapshot(sf, qid)
        except Exception:
            if resolved_from_opportunity_id:
                try:
                    snap_fb = _fetch_opportunity_minimal_for_apex(sf, resolved_from_opportunity_id)
                except Exception:
                    pass
        return {
            "success": False,
            "error": err,
            "errorMessage": err,
            "quote_id": qid,
            "quoteResult": _apex_quote_result_payload(qid, snap_fb, error_message=err),
        }


def _fetch_quote_snapshot(sf: Any, quote_id: str) -> Dict[str, Any]:
    esc = _soql_escape(quote_id)
    q_quote = (
        "SELECT Id, Name, Status, QuoteNumber, TotalPrice, Subtotal, ExpirationDate, "
        "OpportunityId, Opportunity.Id, Opportunity.Name, "
        "Opportunity.AccountId, Opportunity.Account.Name, Opportunity.Account.Phone, "
        "Opportunity.Account.Industry, Pricebook2Id, CreatedDate, LastModifiedDate "
        f"FROM Quote WHERE Id = '{esc}' LIMIT 1"
    )
    qr = sf.query(q_quote)
    qrecs = qr.get("records") or []
    quote_row = qrecs[0] if qrecs else None

    p2_names = _product2_sku_names_for_query(probe_sku_c=_AUTO_PROBE_PRODUCT2_SKU__C)
    p2_fields = _product2_sku_select_fragment_from_names(p2_names)
    q_li = (
        "SELECT Id, LineNumber, Quantity, UnitPrice, ListPrice, Subtotal, Discount, TotalPrice, "
        f"Description, {p2_fields} "
        f"FROM QuoteLineItem WHERE QuoteId = '{esc}' ORDER BY LineNumber, CreatedDate"
    )
    try:
        lines = _soql_query_all_records(sf, q_li)
    except Exception as e1:
        if _AUTO_PROBE_PRODUCT2_SKU__C and _DEFAULT_PROBE_SKU_FIELD in p2_names and _soql_error_suggests_missing_sku_c(
            e1
        ):
            print(
                f"[Quote] QuoteLineItem SOQL omitting {_DEFAULT_PROBE_SKU_FIELD} (org has no field): {e1}",
                file=sys.stderr,
            )
            p2_names = _product2_sku_names_for_query(probe_sku_c=False)
            p2_fields = _product2_sku_select_fragment_from_names(p2_names)
            q_li = (
                "SELECT Id, LineNumber, Quantity, UnitPrice, ListPrice, Subtotal, Discount, TotalPrice, "
                f"Description, {p2_fields} "
                f"FROM QuoteLineItem WHERE QuoteId = '{esc}' ORDER BY LineNumber, CreatedDate"
            )
            lines = _soql_query_all_records(sf, q_li)
        else:
            raise

    line_details: List[Dict[str, Any]] = []
    for row in lines:
        pbe = row.get("PricebookEntry") or {}
        p2 = pbe.get("Product2") if isinstance(pbe.get("Product2"), dict) else {}
        sku_bundle = (
            _resolved_product_sku_bundle(p2, field_names=p2_names) if isinstance(p2, dict) else {}
        )
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
                "Product2Id": p2.get("Id") if isinstance(p2, dict) else None,
                "ProductName": p2.get("Name") if isinstance(p2, dict) else None,
                "ProductCode": p2.get("ProductCode") if isinstance(p2, dict) else None,
                "StockKeepingUnit": p2.get("StockKeepingUnit") if isinstance(p2, dict) else None,
                "sku": sku_bundle.get("sku"),
                "sku_source_field": sku_bundle.get("sku_source_field"),
                "sku_candidates": sku_bundle.get("sku_candidates"),
            }
        )

    oa = _enrich_account_summary(sf, quote_row, _opportunity_account_from_quote_row(quote_row))
    osum = _enrich_opportunity_summary(sf, _opportunity_summary_from_quote_row(quote_row))
    oid = osum.get("opportunity_id")
    oname = osum.get("opportunity_name")
    ui_opp = ""
    if oid or oname:
        ui_opp = f"Opportunity: {oname or '(name unavailable)'}  |  Opportunity Id: {oid or '(id unavailable)'}"
    acc_id = oa.get("account_id")
    acc_name = oa.get("account_name")
    ui_acc = ""
    if acc_id or acc_name:
        ui_acc = f"Account: {acc_name or '(name unavailable)'}  |  Account Id: {acc_id or '(id unavailable)'}"
    return {
        "quote": quote_row,
        "quote_line_details": line_details,
        "quote_line_details_count": len(line_details),
        "quote_line_product_skus": _quote_line_product_sku_rows(line_details),
        "ui_formatted_quote_lines": _format_quote_lines_for_ui(line_details),
        "opportunity_account": oa,
        "account": {"id": acc_id, "name": acc_name},
        "AccountId": acc_id,
        "AccountName": acc_name,
        "ui_account_header": ui_acc or None,
        "opportunity_id": oid,
        "opportunity_name": oname,
        "OpportunityId": oid,
        "OpportunityName": oname,
        "opportunity": {"id": oid, "name": oname},
        "ui_opportunity_header": ui_opp or None,
    }


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
        "quote_line_details_count": 0,
        "quote_line_product_skus": [],
        "ui_formatted_quote_lines": None,
        "opportunity_account": None,
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
        oli_rows = _soql_query_all_records(sf, oli_query)

        created_line_summaries: List[Dict[str, Any]] = []
        if oli_rows:
            qli_sf = SFType("QuoteLineItem", sf.session_id, sf.sf_instance)
            for oli in oli_rows:
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
        result["quote_line_details_count"] = snap.get("quote_line_details_count") or len(
            result["quote_line_details"]
        )
        result["ui_formatted_quote_lines"] = snap.get("ui_formatted_quote_lines") or _format_quote_lines_for_ui(
            result["quote_line_details"]
        )
        result["quote_line_product_skus"] = snap.get("quote_line_product_skus") or []
        result["opportunity_id"] = snap.get("opportunity_id")
        result["opportunity_name"] = snap.get("opportunity_name")
        result["OpportunityId"] = snap.get("OpportunityId")
        result["OpportunityName"] = snap.get("OpportunityName")
        result["opportunity"] = snap.get("opportunity")
        result["ui_opportunity_header"] = snap.get("ui_opportunity_header")
        result["account"] = snap.get("account")
        result["AccountId"] = snap.get("AccountId")
        result["AccountName"] = snap.get("AccountName")
        result["ui_account_header"] = snap.get("ui_account_header")
        oa_snap = snap.get("opportunity_account") or {}
        result["opportunity_account"] = oa_snap
        for src, dst in (
            ("account_id", "accountId"),
            ("account_name", "accountName"),
            ("account_phone", "accountPhone"),
            ("account_industry", "accountIndustry"),
        ):
            v = oa_snap.get(src)
            if v is not None:
                result[dst] = v

        if result["quoteLineCount"] != result["quote_line_details_count"]:
            result["quote_line_count_mismatch_warning"] = (
                f"Created {result['quoteLineCount']} line(s) from the opportunity but SOQL returned "
                f"{result['quote_line_details_count']} quote line detail row(s); verify in Salesforce."
            )

        accept_patch = {"Status": QUOTE_STATUS_ACCEPTED}
        reject_patch = {"Status": QUOTE_STATUS_REJECTED}
        result["fallback_update_via_sobject_tool"] = {
            "tool": "SALESFORCE_UPDATE_SOBJECT",
            "note": (
                "Registered at the top of tools/list. Use when quote-specific tools are missing from the MCP client."
            ),
            "on_user_accept": {
                "sobject_type": "Quote",
                "record_id": quote_id,
                "fields": accept_patch,
            },
            "on_user_reject": {
                "sobject_type": "Quote",
                "record_id": quote_id,
                "fields": reject_patch,
            },
        }
        result["ui_prompt_for_user"] = (
            "Display **every** quote line to the user: use the full `ui_formatted_quote_lines` text "
            "(or the `quote_line_details` array) and **do not** summarize or omit rows. "
            "Then ask them to accept or reject. "
            "**Prefer** tool **SALESFORCE_UPDATE_SOBJECT** (usually listed first): "
            f"arguments `sobject_type`: \"Quote\", `record_id`: \"{quote_id}\", `fields`: "
            f"{json.dumps(accept_patch)} for accept, or `fields`: {json.dumps(reject_patch)} for reject. "
            "If those tools appear in tools/list, you may instead use **SALESFORCE_SET_QUOTE_STATUS** "
            "(decision accept/reject) or SALESFORCE_ACCEPT_QUOTE / SALESFORCE_REJECT_QUOTE."
        )
        result["next_tools"] = {
            "on_user_accept": {
                "tool": "SALESFORCE_UPDATE_SOBJECT",
                "arguments": {
                    "sobject_type": "Quote",
                    "record_id": quote_id,
                    "fields": accept_patch,
                },
            },
            "on_user_reject": {
                "tool": "SALESFORCE_UPDATE_SOBJECT",
                "arguments": {
                    "sobject_type": "Quote",
                    "record_id": quote_id,
                    "fields": reject_patch,
                },
            },
            "optional_quote_specific_tools": {
                "set_status": "SALESFORCE_SET_QUOTE_STATUS",
                "accept": "SALESFORCE_ACCEPT_QUOTE",
                "reject": "SALESFORCE_REJECT_QUOTE",
            },
        }
        result["mcp_tool_names_for_quote_status"] = [
            "SALESFORCE_UPDATE_SOBJECT",
            "SALESFORCE_SET_QUOTE_STATUS",
            "SALESFORCE_ACCEPT_QUOTE",
            "SALESFORCE_REJECT_QUOTE",
        ]

        result["success"] = True
        print(f"[Quote] Created quote {quote_id} for Opp {opp['Id']} ({result['quoteLineCount']} lines)", file=sys.stderr)

    except Exception as e:
        result["errorMessage"] = str(e)
        result["error"] = str(e)
        print(f"[Quote ERROR] {e}", file=sys.stderr)

    return result

