"""
User Operations
Retrieve current or specific user info
"""
import sys
from typing import Dict, Any, List
from salesforce_config import get_salesforce


def get_user_tools() -> List[Dict[str, Any]]:
    """Return list of user-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_GET_USER_INFO",
            "description": "Retrieves information about the current user or a specific user in Salesforce.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID (omit for current user)"},
                    "include_permissions": {"type": "boolean", "description": "Include permission set info"}
                }
            }
        }
    ]


def handle_user_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle user-related tool calls"""
    sf = get_salesforce()
    if tool_name == "SALESFORCE_GET_USER_INFO":
        return get_user_info(sf, arguments)
    raise ValueError(f"Unknown user tool: {tool_name}")


def get_user_info(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        user_id = arguments.get("user_id")
        if user_id:
            result = sf.query(f"SELECT Id, Username, Name, Email, UserType, ProfileId, IsActive FROM User WHERE Id = '{str(user_id).replace(chr(39), chr(39)+chr(39))}' LIMIT 1")
        else:
            try:
                identity = sf.restful("oauth2/userinfo")
                if identity:
                    uid = identity.get("user_id") or identity.get("sub")
                    if uid:
                        result = sf.query(f"SELECT Id, Username, Name, Email, UserType, ProfileId, IsActive FROM User WHERE Id = '{str(uid).replace(chr(39), chr(39)+chr(39))}' LIMIT 1")
                    else:
                        result = {"records": [identity]}
                else:
                    result = {"records": []}
            except Exception:
                result = {"records": []}
        recs = result.get("records", [])
        rec = recs[0] if recs else (result if isinstance(result, dict) and "user_id" in result else {})
        return {"success": True, "record": rec}
    except Exception as e:
        print(f"[User ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}
