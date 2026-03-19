"""
Report Operations
List and run Salesforce reports
"""
import sys
from typing import Dict, Any, List
from salesforce_config import get_salesforce


def get_report_tools() -> List[Dict[str, Any]]:
    """Return list of report-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_LIST_REPORTS",
            "description": "Lists all reports available in Salesforce with basic metadata including name, ID, and URLs.",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "SALESFORCE_RUN_REPORT",
            "description": "Runs a report and returns the results. Results are in a nested structure (factMap, reportExtendedMetadata).",
            "inputSchema": {
                "type": "object",
                "properties": {"report_id": {"type": "string", "description": "Report ID (required)"}},
                "required": ["report_id"]
            }
        }
    ]


def handle_report_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle report-related tool calls"""
    sf = get_salesforce()
    if tool_name == "SALESFORCE_LIST_REPORTS":
        return list_reports(sf, arguments)
    if tool_name == "SALESFORCE_RUN_REPORT":
        return run_report(sf, arguments)
    raise ValueError(f"Unknown report tool: {tool_name}")


def list_reports(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = sf.query("SELECT Id, Name, DeveloperName, FolderName FROM Report LIMIT 2000")
        records = result.get("records", [])
        return {"success": True, "records": records, "totalSize": result.get("totalSize", 0)}
    except Exception as e:
        print(f"[Report ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def run_report(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        report_id = arguments.get("report_id")
        if not report_id:
            raise ValueError("report_id is required")
        path = f"analytics/reports/{report_id}"
        data = sf.restful(path)
        return {"success": True, "report_id": report_id, "factMap": data.get("factMap", {}), "reportExtendedMetadata": data.get("reportExtendedMetadata"), "reportMetadata": data.get("reportMetadata")}
    except Exception as e:
        print(f"[Report ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}
