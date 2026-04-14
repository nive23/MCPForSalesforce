"""
FastAPI-based Salesforce MCP Server for Azure App Service
Uses FastAPI to properly implement MCP protocol endpoints
Modular structure with separate modules for each functionality
"""
import sys
import os
import json
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import configuration
from salesforce_config import get_salesforce

# Import all tool modules
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
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[REQUEST] {request.method} {request.url.path}", file=sys.stderr)
    response = await call_next(request)
    print(f"[RESPONSE] {request.method} {request.url.path} -> {response.status_code}", file=sys.stderr)
    return response

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def get_all_tools() -> list:
    """Get all available MCP tools from all modules"""
    tools = []
    tools.extend(get_account_tools())
    tools.extend(get_contact_tools())
    tools.extend(get_lead_tools())
    tools.extend(get_campaign_tools())
    tools.extend(get_opportunity_tools())
    tools.extend(get_task_tools())
    tools.extend(get_note_tools())
    tools.extend(get_quote_tools())
    tools.extend(get_soql_tools())
    tools.extend(get_report_tools())
    tools.extend(get_user_tools())
    tools.extend(get_email_tools())
    return tools

def handle_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Route tool calls to appropriate handler"""
    account_tools = ["SALESFORCE_CREATE_ACCOUNT", "get_accounts", "SALESFORCE_DELETE_ACCOUNT", "SALESFORCE_GET_ACCOUNT", "SALESFORCE_LIST_ACCOUNTS", "SALESFORCE_SEARCH_ACCOUNTS", "SALESFORCE_UPDATE_ACCOUNT"]
    if tool_name in account_tools:
        return handle_account_tool_call(tool_name, arguments)
    contact_tools = ["SALESFORCE_CREATE_CONTACT", "SALESFORCE_ADD_CONTACT_TO_CAMPAIGN", "SALESFORCE_DELETE_CONTACT", "SALESFORCE_GET_CONTACT", "SALESFORCE_LIST_CONTACTS", "SALESFORCE_SEARCH_CONTACTS", "SALESFORCE_UPDATE_CONTACT"]
    if tool_name in contact_tools:
        return handle_contact_tool_call(tool_name, arguments)
    lead_tools = ["SALESFORCE_CREATE_LEAD", "SALESFORCE_ADD_LEAD_TO_CAMPAIGN", "SALESFORCE_DELETE_LEAD", "SALESFORCE_GET_LEAD", "SALESFORCE_LIST_LEADS", "SALESFORCE_SEARCH_LEADS", "SALESFORCE_UPDATE_LEAD", "SALESFORCE_CONVERT_LEAD"]
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
    if tool_name == "create_quote_from_opportunity":
        return handle_quote_tool_call(tool_name, arguments)
    if tool_name == "SALESFORCE_RUN_SOQL_QUERY":
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
async def root():
    """Root endpoint - Health check and transport info"""
    return {
        "status": "ok",
        "server": "salesforce-azure",
        "version": "1.0.0",
        "protocol": "MCP",
        "transport": "SSE",
        "sse_endpoint": "/sse",
        "message_endpoint": "POST /",
        "boomi_compatible": True
    }

@app.get("/sse")
async def sse_endpoint(request: Request):
    """
    SSE (Server-Sent Events) endpoint for MCP protocol
    This is the primary transport endpoint for Boomi integration
    """
    print("[MCP] SSE connection established", file=sys.stderr)
    
    async def event_stream():
        # Send initial connection message in MCP format
        init_message = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        yield f"data: {json.dumps(init_message)}\n\n"
        
        # Keep connection alive with periodic pings
        while True:
            await asyncio.sleep(30)
            ping_message = {
                "jsonrpc": "2.0",
                "method": "ping",
                "params": {}
            }
            yield f"data: {json.dumps(ping_message)}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.post("/register")
async def register():
    """MCP server registration endpoint"""
    print("[MCP] Register endpoint called", file=sys.stderr)
    return {
        "status": "registered",
        "server": "salesforce-azure",
        "version": "1.0.0"
    }

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
        except:
            # Try form data
            form = await request.form()
            body = dict(form)
        
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
                content={
                    "error": "Missing required parameter: opportunity_id",
                    "message": "Please provide opportunity_id in the request"
                }
            )
        
        print(f"[Boomi] Creating quote for opportunity: {opportunity_id}", file=sys.stderr)
        
        # Call the MCP tool logic
        result = handle_quote_tool_call("create_quote_from_opportunity", {"opportunity_id": opportunity_id})
        
        # Return in REST API format (not MCP format)
        if result.get("errorMessage"):
            return JSONResponse(
                status_code=500,
                content={
                    "error": result["errorMessage"],
                    "success": False
                }
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": result
            }
        )
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Boomi ERROR] {error_msg}", file=sys.stderr)
        return JSONResponse(
            status_code=500,
            content={
                "error": error_msg,
                "success": False
            }
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
        except:
            body = {}
        
        limit = int(body.get("limit", body.get("Limit", 5)))
        if limit < 1 or limit > 100:
            limit = 5
        
        print(f"[Boomi] Fetching {limit} accounts...", file=sys.stderr)
        result = handle_account_tool_call("get_accounts", {"limit": limit})
        
        if not result.get("success"):
            return JSONResponse(
                status_code=500,
                content={
                    "error": result.get("error", "Unknown error"),
                    "success": False
                }
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": result.get("accounts", []),
                "count": result.get("count", 0)
            }
        )
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Boomi ERROR] {error_msg}", file=sys.stderr)
        return JSONResponse(
            status_code=500,
            content={
                "error": error_msg,
                "success": False
            }
        )

@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource():
    """OAuth protected resource discovery"""
    print("[MCP] OAuth protected resource endpoint called", file=sys.stderr)
    return {
        "resource": "salesforce-azure",
        "scopes_supported": []
    }

@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server():
    """OAuth authorization server discovery"""
    print("[MCP] OAuth authorization server endpoint called", file=sys.stderr)
    return {
        "issuer": "salesforce-azure",
        "authorization_endpoint": None,
        "token_endpoint": None
    }

@app.post("/")
@app.post("")
async def mcp_request(request: Request):
    """Handle MCP protocol requests"""
    print(f"[MCP] POST / received", file=sys.stderr)
    try:
        # Try to get JSON body
        try:
            body = await request.json()
        except Exception as json_error:
            print(f"[MCP ERROR] Failed to parse JSON: {json_error}", file=sys.stderr)
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": "Parse error"
                    }
                }
            )
        
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        print(f"[MCP] Received request: {method} (id: {request_id})", file=sys.stderr)
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "salesforce-azure",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            # Get all tools from all modules
            all_tools = get_all_tools()
            
            # Convert to MCP format
            mcp_tools = []
            for tool in all_tools:
                mcp_tool = {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": tool["inputSchema"]
                }
                mcp_tools.append(mcp_tool)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": mcp_tools
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if not tool_name:
                raise ValueError("Tool name is required")
            
            # Call the appropriate tool handler
            result = handle_tool_call(tool_name, arguments)
            
            # Format response based on result structure
            if isinstance(result, dict) and "success" in result:
                # Tool returned a structured result
                if result.get("success"):
                    response_text = json.dumps(result, indent=2)
                else:
                    # Error occurred
                    error_msg = result.get("error", "Unknown error")
                    raise ValueError(error_msg)
            else:
                # Tool returned raw result (like quote logic)
                response_text = json.dumps(result, indent=2)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": response_text
                        }
                    ]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
    
    except Exception as e:
        error_msg = str(e)
        import traceback
        print(f"[MCP ERROR] {error_msg}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        request_id = None
        if 'body' in locals():
            request_id = body.get("id")
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": error_msg
                }
            }
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


