"""
SOQL Operations
Executes SOQL queries against Salesforce
"""
import sys
from typing import Dict, Any, List
from salesforce_config import get_salesforce


def get_soql_tools() -> List[Dict[str, Any]]:
    """Return list of SOQL-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_RUN_SOQL_QUERY",
            "description": "Executes a SOQL query against Salesforce data. Returns records matching the query with pagination support.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SOQL query string (required)"
                    }
                },
                "required": ["query"]
            }
        }
    ]


def handle_soql_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle SOQL-related tool calls"""
    sf = get_salesforce()
    if tool_name == "SALESFORCE_RUN_SOQL_QUERY":
        return run_soql_query(sf, arguments)
    raise ValueError(f"Unknown SOQL tool: {tool_name}")


def run_soql_query(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a SOQL query"""
    try:
        query = arguments.get("query")
        if not query or not str(query).strip():
            raise ValueError("query is required")
        result = sf.query(str(query).strip())
        return {
            "success": True,
            "records": result.get("records", []),
            "totalSize": result.get("totalSize", 0),
            "done": result.get("done", True),
            "nextRecordsUrl": result.get("nextRecordsUrl"),
        }
    except Exception as e:
        error_msg = str(e)
        print(f"[SOQL ERROR] {error_msg}", file=sys.stderr)
        return {"success": False, "error": error_msg}
