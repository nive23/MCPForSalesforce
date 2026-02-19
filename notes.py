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
        }
    ]

def handle_note_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle note-related tool calls"""
    sf = get_salesforce()
    
    if tool_name == "SALESFORCE_CREATE_NOTE":
        return create_note(sf, arguments)
    else:
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
        return {
            "success": False,
            "error": error_msg
        }

