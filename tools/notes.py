"""
Note Operations
Handles Salesforce Note creation
"""
import sys
import json
from typing import Dict, Any, List
from simple_salesforce import SFType
from salesforce_config import get_salesforce

def get_note_tools() -> List[Dict[str, Any]]:
    """Return list of note-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_CREATE_NOTE",
            "description": "Creates a new note attached to a Salesforce record with the specified title and content.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Note title (required)"
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "Parent record ID (Account, Contact, Opportunity, etc.) (required)"
                    },
                    "body": {
                        "type": "string",
                        "description": "Note content/body"
                    },
                    "owner_id": {
                        "type": "string",
                        "description": "Note owner user ID"
                    },
                    "is_private": {
                        "type": "boolean",
                        "description": "Whether the note is private"
                    },
                    "custom_fields": {
                        "type": "object",
                        "description": "Additional custom fields as key-value pairs"
                    }
                },
                "required": ["title", "parent_id"]
            }
        },
        {
            "name": "SALESFORCE_LIST_NOTES",
            "description": "Lists notes from Salesforce using SOQL query (Note and ContentNote objects).",
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}
        },
        {
            "name": "SALESFORCE_SEARCH_NOTES",
            "description": "Search for Salesforce notes by title, body, parent, owner, or creation date.",
            "inputSchema": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "body": {"type": "string"}, "limit": {"type": "integer"}, "fields": {"type": "string"}, "is_private": {"type": "boolean"}, "owner_name": {"type": "string"}, "parent_name": {"type": "string"}, "created_date_from": {"type": "string"}, "created_date_to": {"type": "string"}}
            }
        },
        {
            "name": "SALESFORCE_UPDATE_NOTE",
            "description": "Updates an existing note in Salesforce. Only provided fields will be updated.",
            "inputSchema": {"type": "object", "properties": {"note_id": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}, "owner_id": {"type": "string"}, "is_private": {"type": "boolean"}, "custom_fields": {"type": "object"}}, "required": ["note_id"]}
        }
    ]

def handle_note_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle note-related tool calls"""
    sf = get_salesforce()
    if tool_name == "SALESFORCE_CREATE_NOTE":
        return create_note(sf, arguments)
    if tool_name == "SALESFORCE_LIST_NOTES":
        return list_notes(sf, arguments)
    if tool_name == "SALESFORCE_SEARCH_NOTES":
        return search_notes(sf, arguments)
    if tool_name == "SALESFORCE_UPDATE_NOTE":
        return update_note(sf, arguments)
    raise ValueError(f"Unknown note tool: {tool_name}")

def create_note(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new note in Salesforce"""
    try:
        # Extract required fields
        title = arguments.get("title")
        parent_id = arguments.get("parent_id")
        
        if not title:
            raise ValueError("Note title is required")
        if not parent_id:
            raise ValueError("Parent record ID is required")
        
        # Build note data
        note_data = {
            "Title": title,
            "ParentId": parent_id
        }
        
        # Add optional fields
        optional_fields = [
            "body", "owner_id", "is_private"
        ]
        
        for field in optional_fields:
            value = arguments.get(field)
            if value is not None:
                # Convert field name to Salesforce API name
                sf_field = field[0].upper() + field[1:] if field else field
                # Handle special cases
                if field == "owner_id":
                    sf_field = "OwnerId"
                elif field == "is_private":
                    sf_field = "IsPrivate"
                note_data[sf_field] = value
        
        # Add custom fields
        custom_fields = arguments.get("custom_fields", {})
        if custom_fields:
            note_data.update(custom_fields)
        
        # Create note using Note object (more compatible than ContentNote)
        note_sf = SFType('Note', sf.session_id, sf.sf_instance)
        
        # Note object uses Body instead of body
        if "body" in note_data:
            note_data["Body"] = note_data.pop("body")
        
        result = note_sf.create(note_data)
        
        note_id = result["id"]
        print(f"[Note] Created note: {note_id}", file=sys.stderr)
        
        return {
            "success": True,
            "note_id": note_id,
            "message": f"Note '{title}' created successfully"
        }
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Note ERROR] {error_msg}", file=sys.stderr)
        return {"success": False, "error": error_msg}


def list_notes(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        query = arguments.get("query") or "SELECT Id, Title, ParentId, CreatedDate FROM Note LIMIT 2000"
        result = sf.query(str(query).strip())
        return {"success": True, "records": result.get("records", []), "totalSize": result.get("totalSize", 0), "done": result.get("done", True), "nextRecordsUrl": result.get("nextRecordsUrl")}
    except Exception as e:
        print(f"[Note ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def search_notes(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        limit = min(int(arguments.get("limit", 50)), 200)
        fields = arguments.get("fields") or "Id, Title, Body, ParentId, OwnerId, IsPrivate, CreatedDate"
        where = []
        def esc(s): return str(s).replace("'", "''")
        if arguments.get("title"):
            where.append(f"Title LIKE '%{esc(arguments['title'])}%'")
        if arguments.get("body"):
            where.append(f"Body LIKE '%{esc(arguments['body'])}%'")
        if arguments.get("is_private") is not None:
            where.append(f"IsPrivate = {str(arguments['is_private']).lower()}")
        if arguments.get("created_date_from"):
            where.append(f"CreatedDate >= {repr(arguments['created_date_from'])}")
        if arguments.get("created_date_to"):
            where.append(f"CreatedDate <= {repr(arguments['created_date_to'])}")
        where_clause = " AND ".join(where) if where else "Id != null"
        result = sf.query(f"SELECT {fields} FROM Note WHERE {where_clause} LIMIT {limit}")
        return {"success": True, "records": result.get("records", []), "totalSize": result.get("totalSize", 0)}
    except Exception as e:
        print(f"[Note ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def update_note(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        note_id = arguments.get("note_id")
        if not note_id:
            raise ValueError("note_id is required")
        update_data = {}
        if arguments.get("title") is not None:
            update_data["Title"] = arguments["title"]
        if arguments.get("body") is not None:
            update_data["Body"] = arguments["body"]
        if arguments.get("owner_id") is not None:
            update_data["OwnerId"] = arguments["owner_id"]
        if arguments.get("is_private") is not None:
            update_data["IsPrivate"] = arguments["is_private"]
        custom = arguments.get("custom_fields", {})
        if custom:
            update_data.update(custom)
        if not update_data:
            return {"success": True, "message": "No fields to update"}
        note_sf = SFType("Note", sf.session_id, sf.sf_instance)
        note_sf.update(note_id, update_data)
        return {"success": True, "note_id": note_id, "message": "Note updated"}
    except Exception as e:
        print(f"[Note ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}

