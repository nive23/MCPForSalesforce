"""
FastAPI-based Salesforce MCP Server for Azure App Service
Uses FastAPI to properly implement MCP protocol endpoints
Modular structure with separate modules for each functionality
"""
import sys
import os
import json
import asyncio
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import configuration
from salesforce_config import get_salesforce

# Import all tool modules
from tools.leads import LEAD_CONVERT_BUILD, diagnose_lead_convert_health
from tools import (
    get_account_tools, handle_account_tool_call,
    get_contact_tools, handle_contact_tool_call,
    get_lead_tools, handle_lead_tool_call,
    get_campaign_tools, handle_campaign_tool_call,
    get_opportunity_tools, handle_opportunity_tool_call,
    get_task_tools, handle_task_tool_call,
    get_note_tools, handle_note_tool_call,
    get_quote_tools, handle_quote_tool_call,
    get_soql_tools, handle_soql_tool_call,
    get_report_tools, handle_report_tool_call,
    get_user_tools, handle_user_tool_call,
    get_email_tools, handle_email_tool_call,
)

# -------------------------------------------------
# Azure Configuration
# -------------------------------------------------
port = int(os.getenv("PORT", 8000))
host = os.getenv("HOST", "0.0.0.0")

# -------------------------------------------------
# FastAPI App
# -------------------------------------------------
app = FastAPI(title="Salesforce MCP Server")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-Id"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[REQUEST] {request.method} {request.url.path}", file=sys.stderr)
    response = await call_next(request)
    print(f"[RESPONSE] {request.method} {request.url.path} -> {response.status_code}", file=sys.stderr)
    return response


def _extract_ui_session_id(request: Request, body: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    UI correlation session: header, query string, or JSON (top-level / meta / params / tool arguments).
    If present on the request, echo the same value back on responses (see _merge_ui_session).
    """
    for h in (
        "x-session-id",
        "x-sessionid",
        "session-id",
        "x-ui-session-id",
        "x-correlation-session",
    ):
        v = request.headers.get(h)
        if v is not None and str(v).strip():
            return str(v).strip()
    for qk in ("sessionId", "session_id", "uiSessionId"):
        v = request.query_params.get(qk)
        if v is not None and str(v).strip():
            return str(v).strip()
    if body and isinstance(body, dict):
        for k in ("sessionId", "session_id", "uiSessionId"):
            v = body.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
        meta = body.get("meta")
        if isinstance(meta, dict):
            for k in ("sessionId", "session_id", "uiSessionId"):
                v = meta.get(k)
                if v is not None and str(v).strip():
                    return str(v).strip()
        params = body.get("params")
        if isinstance(params, dict):
            for k in ("sessionId", "session_id", "uiSessionId"):
                v = params.get(k)
                if v is not None and str(v).strip():
                    return str(v).strip()
            args = params.get("arguments")
            if isinstance(args, dict):
                for k in ("sessionId", "session_id", "uiSessionId"):
                    v = args.get(k)
                    if v is not None and str(v).strip():
                        return str(v).strip()
    return None


def _merge_ui_session(payload: Dict[str, Any], session_id: Optional[str]) -> Dict[str, Any]:
    """Attach sessionId to a JSON object when the client sent one (same key for UI)."""
    if session_id is not None and str(session_id).strip():
        payload = dict(payload)
        payload["sessionId"] = str(session_id).strip()
    return payload


@app.middleware("http")
async def ui_session_echo_header(request: Request, call_next):
    """Echo X-Session-Id on the HTTP response when the handler set request.state.ui_session_id."""
    response = await call_next(request)
    sid = getattr(request.state, "ui_session_id", None)
    if sid:
        response.headers["X-Session-Id"] = str(sid)
    return response


# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def get_all_tools() -> list:
    """Get all available MCP tools from all modules"""
    tools = []
    # SOQL module first: includes SALESFORCE_UPDATE_SOBJECT (generic Quote Status) for clients
    # that omit quote-specific tools from tools/list.
    tools.extend(get_soql_tools())
    tools.extend(get_quote_tools())
    tools.extend(get_account_tools())
    tools.extend(get_contact_tools())
    tools.extend(get_lead_tools())
    tools.extend(get_campaign_tools())
    tools.extend(get_opportunity_tools())
    tools.extend(get_task_tools())
    tools.extend(get_note_tools())
    tools.extend(get_report_tools())
    tools.extend(get_user_tools())
    tools.extend(get_email_tools())
    return tools

def _normalize_mcp_tool_name(name: str) -> str:
    """Strip whitespace, collapse spaces to underscores, uppercase SALESFORCE_* tools."""
    raw = str(name).strip() if name else ""
    if not raw:
        return raw
    compact = "_".join(raw.split()).replace("-", "_")
    if compact.upper().startswith("SALESFORCE_"):
        return compact.upper()
    return compact


def handle_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Route tool calls to appropriate handler"""
    tool_name = _normalize_mcp_tool_name(tool_name)
    account_tools = ["SALESFORCE_CREATE_ACCOUNT", "get_accounts", "SALESFORCE_DELETE_ACCOUNT", "SALESFORCE_GET_ACCOUNT", "SALESFORCE_LIST_ACCOUNTS", "SALESFORCE_SEARCH_ACCOUNTS", "SALESFORCE_UPDATE_ACCOUNT"]
    if tool_name in account_tools:
        return handle_account_tool_call(tool_name, arguments)
    contact_tools = ["SALESFORCE_CREATE_CONTACT", "SALESFORCE_ADD_CONTACT_TO_CAMPAIGN", "SALESFORCE_DELETE_CONTACT", "SALESFORCE_GET_CONTACT", "SALESFORCE_LIST_CONTACTS", "SALESFORCE_SEARCH_CONTACTS", "SALESFORCE_UPDATE_CONTACT"]
    if tool_name in contact_tools:
        return handle_contact_tool_call(tool_name, arguments)
    lead_tools = [
        "SALESFORCE_CREATE_LEAD",
        "SALESFORCE_ADD_LEAD_TO_CAMPAIGN",
        "SALESFORCE_DELETE_LEAD",
        "SALESFORCE_GET_LEAD",
        "SALESFORCE_GET_LEADS",
        "SALESFORCE_LIST_LEADS",
        "SALESFORCE_SEARCH_LEADS",
        "SALESFORCE_UPDATE_LEAD",
        "SALESFORCE_CONVERT_LEAD",
    ]
    if tool_name in lead_tools:
        return handle_lead_tool_call(tool_name, arguments)
    campaign_tools = ["SALESFORCE_CREATE_CAMPAIGN", "SALESFORCE_DELETE_CAMPAIGN", "SALESFORCE_GET_CAMPAIGN", "SALESFORCE_LIST_CAMPAIGNS", "SALESFORCE_SEARCH_CAMPAIGNS", "SALESFORCE_UPDATE_CAMPAIGN", "SALESFORCE_REMOVE_FROM_CAMPAIGN"]
    if tool_name in campaign_tools:
        return handle_campaign_tool_call(tool_name, arguments)
    opportunity_tools = ["SALESFORCE_CREATE_OPPORTUNITY", "SALESFORCE_GET_OPPORTUNITY", "SALESFORCE_LIST_OPPORTUNITIES", "SALESFORCE_SEARCH_OPPORTUNITIES", "SALESFORCE_UPDATE_OPPORTUNITY"]
    if tool_name in opportunity_tools:
        return handle_opportunity_tool_call(tool_name, arguments)
    task_tools = ["SALESFORCE_CREATE_TASK", "SALESFORCE_COMPLETE_TASK", "SALESFORCE_UPDATE_TASK", "SALESFORCE_SEARCH_TASKS", "SALESFORCE_LOG_CALL"]
    if tool_name in task_tools:
        return handle_task_tool_call(tool_name, arguments)
    note_tools = ["SALESFORCE_CREATE_NOTE", "SALESFORCE_LIST_NOTES", "SALESFORCE_SEARCH_NOTES", "SALESFORCE_UPDATE_NOTE"]
    if tool_name in note_tools:
        return handle_note_tool_call(tool_name, arguments)
    quote_tools = [
        "create_quote_from_opportunity",
        "SALESFORCE_CREATE_QUOTE_FROM_OPPORTUNITY",
        "SALESFORCE_SET_QUOTE_STATUS",
        "SALESFORCE_ACCEPT_QUOTE",
        "SALESFORCE_REJECT_QUOTE",
    ]
    if tool_name in quote_tools:
        return handle_quote_tool_call(tool_name, arguments)
    if tool_name in ("SALESFORCE_RUN_SOQL_QUERY", "SALESFORCE_UPDATE_SOBJECT"):
        return handle_soql_tool_call(tool_name, arguments)
    if tool_name in ["SALESFORCE_LIST_REPORTS", "SALESFORCE_RUN_REPORT"]:
        return handle_report_tool_call(tool_name, arguments)
    if tool_name == "SALESFORCE_GET_USER_INFO":
        return handle_user_tool_call(tool_name, arguments)
    if tool_name in ["SALESFORCE_LOG_EMAIL_ACTIVITY", "SALESFORCE_SEND_EMAIL", "SALESFORCE_SEND_MASS_EMAIL"]:
        return handle_email_tool_call(tool_name, arguments)
    raise ValueError(f"Unknown tool: {tool_name}")

# -------------------------------------------------
# MCP Protocol Endpoints
# -------------------------------------------------

@app.get("/")
async def root(request: Request):
    """Root endpoint - Health check and transport info"""
    sid = _extract_ui_session_id(request, None)
    request.state.ui_session_id = sid
    return _merge_ui_session(
        {
            "status": "ok",
            "server": "salesforce-azure",
            "version": "1.0.0",
            "lead_convert_build": LEAD_CONVERT_BUILD,
            "protocol": "MCP",
            "transport": "SSE",
            "sse_endpoint": "/sse",
            "message_endpoint": "POST /",
            "boomi_compatible": True,
        },
        sid,
    )

@app.get("/sse")
async def sse_endpoint(request: Request):
    """
    SSE (Server-Sent Events) endpoint for MCP protocol
    This is the primary transport endpoint for Boomi integration
    """
    print("[MCP] SSE connection established", file=sys.stderr)
    sid = _extract_ui_session_id(request, None)
    request.state.ui_session_id = sid

    async def event_stream():
        # Send initial connection message in MCP format
        init_message = _merge_ui_session(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
            sid,
        )
        yield f"data: {json.dumps(init_message)}\n\n"

        # Keep connection alive with periodic pings
        while True:
            await asyncio.sleep(30)
            ping_message = _merge_ui_session(
                {
                    "jsonrpc": "2.0",
                    "method": "ping",
                    "params": {},
                },
                sid,
            )
            yield f"data: {json.dumps(ping_message)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )

@app.post("/register")
async def register(request: Request):
    """MCP server registration endpoint"""
    print("[MCP] Register endpoint called", file=sys.stderr)
    sid = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            sid = _extract_ui_session_id(request, body)
    except Exception:
        sid = _extract_ui_session_id(request, None)
    request.state.ui_session_id = sid
    return _merge_ui_session(
        {
            "status": "registered",
            "server": "salesforce-azure",
            "version": "1.0.0",
        },
        sid,
    )

# -------------------------------------------------
# Boomi REST API Endpoints (REST wrapper for MCP tools)
# -------------------------------------------------

@app.post("/ws/rest/Generate_Quote/V1")
@app.get("/ws/rest/Generate_Quote/V1")
async def boomi_generate_quote(request: Request):
    """
    Boomi REST API endpoint for Generate Quote
    Wraps the MCP create_quote_from_opportunity tool
    """
    print("[Boomi] Generate_Quote endpoint called", file=sys.stderr)
    try:
        # Get request body (Boomi might send JSON or form data)
        try:
            if request.method == "POST":
                body = await request.json()
            else:
                # GET request - get params from query string
                body = dict(request.query_params)
        except Exception:
            # Try form data
            form = await request.form()
            body = dict(form)

        sid = _extract_ui_session_id(request, body if isinstance(body, dict) else None)
        request.state.ui_session_id = sid

        # Extract opportunity_id from various possible formats
        opportunity_id = (
            body.get("opportunity_id") or 
            body.get("opportunityId") or 
            body.get("OpportunityId") or
            body.get("opportunity") or
            body.get("id")
        )
        
        if not opportunity_id:
            return JSONResponse(
                status_code=400,
                content=_merge_ui_session(
                    {
                        "error": "Missing required parameter: opportunity_id",
                        "message": "Please provide opportunity_id in the request",
                    },
                    sid,
                ),
            )
        
        print(f"[Boomi] Creating quote for opportunity: {opportunity_id}", file=sys.stderr)
        
        # Call the MCP tool logic
        result = handle_quote_tool_call("create_quote_from_opportunity", {"opportunity_id": opportunity_id})
        
        # Return in REST API format (not MCP format)
        if result.get("errorMessage"):
            return JSONResponse(
                status_code=500,
                content=_merge_ui_session(
                    {
                        "error": result["errorMessage"],
                        "success": False,
                    },
                    sid,
                ),
            )

        return JSONResponse(
            status_code=200,
            content=_merge_ui_session(
                {
                    "success": True,
                    "data": result,
                },
                sid,
            ),
        )

    except Exception as e:
        error_msg = str(e)
        print(f"[Boomi ERROR] {error_msg}", file=sys.stderr)
        sid = _extract_ui_session_id(request, None)
        request.state.ui_session_id = sid
        return JSONResponse(
            status_code=500,
            content=_merge_ui_session(
                {
                    "error": error_msg,
                    "success": False,
                },
                sid,
            ),
        )

@app.get("/ws/rest/Get_Accounts/V1")
@app.post("/ws/rest/Get_Accounts/V1")
async def boomi_get_accounts(request: Request):
    """
    Boomi REST API endpoint for Get Accounts
    Wraps the MCP get_accounts tool
    """
    print("[Boomi] Get_Accounts endpoint called", file=sys.stderr)
    try:
        # Get limit from query params or body
        try:
            if request.method == "POST":
                body = await request.json()
            else:
                body = dict(request.query_params)
        except Exception:
            body = {}

        sid = _extract_ui_session_id(request, body if isinstance(body, dict) else None)
        request.state.ui_session_id = sid

        limit = int(body.get("limit", body.get("Limit", 5)))
        if limit < 1 or limit > 100:
            limit = 5
        
        print(f"[Boomi] Fetching {limit} accounts...", file=sys.stderr)
        result = handle_account_tool_call("get_accounts", {"limit": limit})
        
        if not result.get("success"):
            return JSONResponse(
                status_code=500,
                content=_merge_ui_session(
                    {
                        "error": result.get("error", "Unknown error"),
                        "success": False,
                    },
                    sid,
                ),
            )

        return JSONResponse(
            status_code=200,
            content=_merge_ui_session(
                {
                    "success": True,
                    "data": result.get("accounts", []),
                    "count": result.get("count", 0),
                },
                sid,
            ),
        )

    except Exception as e:
        error_msg = str(e)
        print(f"[Boomi ERROR] {error_msg}", file=sys.stderr)
        sid = _extract_ui_session_id(request, None)
        request.state.ui_session_id = sid
        return JSONResponse(
            status_code=500,
            content=_merge_ui_session(
                {
                    "error": error_msg,
                    "success": False,
                },
                sid,
            ),
        )

@app.get("/health/lead-convert")
async def health_lead_convert(request: Request):
    """Probe ConvertLeadRestApi reachability (does not require a valid lead Id)."""
    sid = _extract_ui_session_id(request, None)
    request.state.ui_session_id = sid
    try:
        sf = get_salesforce()
        lead_id = request.query_params.get("lead_id") or request.query_params.get("leadId")
        result = diagnose_lead_convert_health(sf, lead_id=lead_id)
        return JSONResponse(
            status_code=200 if result.get("success") else 503,
            content=_merge_ui_session(result, sid),
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=_merge_ui_session(
                {
                    "success": False,
                    "lead_convert_build": LEAD_CONVERT_BUILD,
                    "error": str(e),
                },
                sid,
            ),
        )


@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource(request: Request):
    """OAuth protected resource discovery"""
    print("[MCP] OAuth protected resource endpoint called", file=sys.stderr)
    sid = _extract_ui_session_id(request, None)
    request.state.ui_session_id = sid
    return _merge_ui_session(
        {
            "resource": "salesforce-azure",
            "scopes_supported": [],
        },
        sid,
    )

@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server(request: Request):
    """OAuth authorization server discovery"""
    print("[MCP] OAuth authorization server endpoint called", file=sys.stderr)
    sid = _extract_ui_session_id(request, None)
    request.state.ui_session_id = sid
    return _merge_ui_session(
        {
            "issuer": "salesforce-azure",
            "authorization_endpoint": None,
            "token_endpoint": None,
        },
        sid,
    )

@app.post("/")
@app.post("")
async def mcp_request(request: Request):
    """Handle MCP protocol requests"""
    print(f"[MCP] POST / received", file=sys.stderr)
    body: Optional[Dict[str, Any]] = None
    try:
        # Try to get JSON body
        try:
            body = await request.json()
        except Exception as json_error:
            print(f"[MCP ERROR] Failed to parse JSON: {json_error}", file=sys.stderr)
            sid = _extract_ui_session_id(request, None)
            request.state.ui_session_id = sid
            return JSONResponse(
                status_code=400,
                content=_merge_ui_session(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": "Parse error",
                        },
                    },
                    sid,
                ),
            )

        if not isinstance(body, dict):
            sid = _extract_ui_session_id(request, None)
            request.state.ui_session_id = sid
            return JSONResponse(
                status_code=400,
                content=_merge_ui_session(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": "Expected a JSON object body"},
                    },
                    sid,
                ),
            )

        sid = _extract_ui_session_id(request, body)
        request.state.ui_session_id = sid

        method = body.get("method")
        params = body.get("params", {})
        if not isinstance(params, dict):
            params = {}
        request_id = body.get("id")

        print(f"[MCP] Received request: {method} (id: {request_id})", file=sys.stderr)

        if method == "initialize":
            return _merge_ui_session(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                        },
                        "serverInfo": {
                            "name": "salesforce-azure",
                            "version": "1.0.0",
                        },
                    },
                },
                sid,
            )

        elif method == "tools/list":
            # Get all tools from all modules
            all_tools = get_all_tools()

            # Convert to MCP format
            mcp_tools = []
            for tool in all_tools:
                mcp_tool = {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": tool["inputSchema"],
                }
                mcp_tools.append(mcp_tool)

            return _merge_ui_session(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": mcp_tools,
                    },
                },
                sid,
            )

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments) if arguments.strip() else {}
                except Exception:
                    arguments = {}
            if arguments is None or not isinstance(arguments, dict):
                arguments = {}

            if not tool_name:
                raise ValueError("Tool name is required")

            # Call the appropriate tool handler
            result = handle_tool_call(tool_name, arguments)
            # Always return JSON in result.content, including {"success": false, "error": "..."}.
            # default=str avoids TypeError on datetimes/Decimals from Salesforce payloads.
            result_for_ui: Dict[str, Any] = dict(result) if isinstance(result, dict) else {"value": result}
            if sid:
                result_for_ui["sessionId"] = str(sid)
            response_text = json.dumps(result_for_ui, indent=2, default=str)

            result_obj: Dict[str, Any] = {
                "content": [
                    {
                        "type": "text",
                        "text": response_text,
                    }
                ],
            }
            if isinstance(result, dict) and result.get("success") is False:
                result_obj["isError"] = True
            if sid:
                result_obj["sessionId"] = str(sid)

            return _merge_ui_session(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result_obj,
                },
                sid,
            )

        else:
            return _merge_ui_session(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    },
                },
                sid,
            )

    except Exception as e:
        error_msg = str(e)
        import traceback

        print(f"[MCP ERROR] {error_msg}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        request_id = None
        if isinstance(body, dict):
            request_id = body.get("id")
        sid = _extract_ui_session_id(request, body if isinstance(body, dict) else None)
        request.state.ui_session_id = sid
        return JSONResponse(
            status_code=200,
            content=_merge_ui_session(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": error_msg,
                    },
                },
                sid,
            ),
        )

# -------------------------------------------------
# Entry Point
# -------------------------------------------------
if __name__ == "__main__":
    print("=" * 60, file=sys.stderr)
    print("Salesforce MCP Server - FastAPI (Azure)", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Starting server on {host}:{port}...", file=sys.stderr)
    print(f"Server URL: http://{host}:{port}", file=sys.stderr)
    print(f"Environment: Azure App Service", file=sys.stderr)
    print(f"Framework: FastAPI with MCP protocol", file=sys.stderr)
    print(f"Transport: SSE (Server-Sent Events) - Primary endpoint: /sse", file=sys.stderr)
    print(f"Transport: HTTP JSON-RPC - Fallback endpoint: POST /", file=sys.stderr)
    print(f"Boomi Compatible: SSE transport supported", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    # Load tools to verify imports
    try:
        all_tools = get_all_tools()
        print(f"[Config] Loaded {len(all_tools)} MCP tools", file=sys.stderr)
        for tool in all_tools:
            print(f"[Config]   - {tool['name']}", file=sys.stderr)
    except Exception as e:
        print(f"[Config ERROR] Failed to load tools: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
    
    print("=" * 60, file=sys.stderr)
    
    uvicorn.run(app, host=host, port=port, log_level="info")


