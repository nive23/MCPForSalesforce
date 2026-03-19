"""
Task Operations
Handles Salesforce Task creation and completion
"""
import sys
import json
from typing import Dict, Any, List
from simple_salesforce import SFType
from salesforce_config import get_salesforce

def get_task_tools() -> List[Dict[str, Any]]:
    """Return list of task-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_CREATE_TASK",
            "description": "Creates a new task in Salesforce. To create a task under a Contact, pass the Contact's ID as contact_id (or who_id). To link to a Lead use who_id. To link to an Account or Opportunity use what_id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Task subject (required)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Task status (e.g., Not Started, In Progress, Completed)"
                    },
                    "priority": {
                        "type": "string",
                        "description": "Task priority (e.g., High, Medium, Low)"
                    },
                    "activity_date": {
                        "type": "string",
                        "description": "Activity date (YYYY-MM-DD format)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Task description"
                    },
                    "contact_id": {
                        "type": "string",
                        "description": "Contact ID — use this to create a task under a Contact (linked as WhoId)"
                    },
                    "who_id": {
                        "type": "string",
                        "description": "Contact or Lead ID (WhoId). Use contact_id for a task under a Contact."
                    },
                    "what_id": {
                        "type": "string",
                        "description": "Account or Opportunity ID (WhatId)"
                    },
                    "owner_id": {
                        "type": "string",
                        "description": "Task owner user ID"
                    },
                    "is_reminder_set": {
                        "type": "boolean",
                        "description": "Whether reminder is set"
                    },
                    "reminder_date_time": {
                        "type": "string",
                        "description": "Reminder date and time (ISO format)"
                    },
                    "custom_fields": {
                        "type": "object",
                        "description": "Additional custom fields as key-value pairs"
                    }
                },
                "required": ["subject"]
            }
        },
        {
            "name": "SALESFORCE_COMPLETE_TASK",
            "description": "Marks a task as completed with optional completion notes. This is a convenience action that updates the task status to 'Completed'.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID (required)"
                    },
                    "completion_notes": {
                        "type": "string",
                        "description": "Optional notes about task completion"
                    },
                    "custom_fields": {
                        "type": "object",
                        "description": "Additional custom fields as key-value pairs"
                    }
                },
                "required": ["task_id"]
            }
        },
        {
            "name": "SALESFORCE_UPDATE_TASK",
            "description": "Updates an existing task in Salesforce with new information.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "subject": {"type": "string"}, "status": {"type": "string"}, "priority": {"type": "string"},
                    "description": {"type": "string"}, "activity_date": {"type": "string"},
                    "who_id": {"type": "string"}, "what_id": {"type": "string"}, "owner_id": {"type": "string"},
                    "is_reminder_set": {"type": "boolean"}, "reminder_date_time": {"type": "string"},
                    "custom_fields": {"type": "object"}
                },
                "required": ["task_id"]
            }
        },
        {
            "name": "SALESFORCE_SEARCH_TASKS",
            "description": "Search for Salesforce tasks by subject, status, priority, assigned user, related records, or dates.",
            "inputSchema": {
                "type": "object",
                "properties": {"subject": {"type": "string"}, "status": {"type": "string"}, "priority": {"type": "string"}, "is_closed": {"type": "boolean"}, "activity_date_from": {"type": "string"}, "activity_date_to": {"type": "string"}, "assigned_to_name": {"type": "string"}, "account_name": {"type": "string"}, "contact_name": {"type": "string"}, "limit": {"type": "integer"}, "fields": {"type": "string"}}
            }
        },
        {
            "name": "SALESFORCE_LOG_CALL",
            "description": "Logs a completed phone call as a task in Salesforce with call-specific details like duration, type, and disposition.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "who_id": {"type": "string", "description": "Contact or Lead ID"},
                    "what_id": {"type": "string", "description": "Account or Opportunity ID"},
                    "subject": {"type": "string"}, "comments": {"type": "string"},
                    "call_date": {"type": "string"}, "call_type": {"type": "string"}, "call_duration_seconds": {"type": "integer"},
                    "call_disposition": {"type": "string"}, "custom_fields": {"type": "object"}
                }
            }
        }
    ]

def handle_task_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle task-related tool calls"""
    sf = get_salesforce()
    if tool_name == "SALESFORCE_CREATE_TASK":
        return create_task(sf, arguments)
    if tool_name == "SALESFORCE_COMPLETE_TASK":
        return complete_task(sf, arguments)
    if tool_name == "SALESFORCE_UPDATE_TASK":
        return update_task(sf, arguments)
    if tool_name == "SALESFORCE_SEARCH_TASKS":
        return search_tasks(sf, arguments)
    if tool_name == "SALESFORCE_LOG_CALL":
        return log_call(sf, arguments)
    raise ValueError(f"Unknown task tool: {tool_name}")

def create_task(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new task in Salesforce"""
    try:
        # Extract required fields
        subject = arguments.get("subject")
        if not subject:
            raise ValueError("Task subject is required")
        
        # Build task data
        task_data = {
            "Subject": subject
        }
        
        # Link to Contact: contact_id or who_id (Contact/Lead ID)
        contact_id = arguments.get("contact_id") or arguments.get("who_id")
        if contact_id is not None:
            task_data["WhoId"] = contact_id
        
        # Map other optional fields to Salesforce API names
        TASK_FIELD_TO_API = {
            "status": "Status",
            "priority": "Priority",
            "activity_date": "ActivityDate",
            "description": "Description",
            "what_id": "WhatId",
            "owner_id": "OwnerId",
            "is_reminder_set": "IsReminderSet",
            "reminder_date_time": "ReminderDateTime",
        }
        for field, sf_field in TASK_FIELD_TO_API.items():
            value = arguments.get(field)
            if value is not None:
                task_data[sf_field] = value
        
        # Add custom fields
        custom_fields = arguments.get("custom_fields", {})
        if custom_fields:
            task_data.update(custom_fields)
        
        # Create task
        task_sf = SFType('Task', sf.session_id, sf.sf_instance)
        result = task_sf.create(task_data)
        
        task_id = result["id"]
        print(f"[Task] Created task: {task_id}", file=sys.stderr)
        
        return {
            "success": True,
            "task_id": task_id,
            "message": f"Task '{subject}' created successfully"
        }
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Task ERROR] {error_msg}", file=sys.stderr)
        return {
            "success": False,
            "error": error_msg
        }

def complete_task(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Mark a task as completed"""
    try:
        task_id = arguments.get("task_id")
        if not task_id:
            raise ValueError("Task ID is required")
        
        # Build update data
        update_data = {
            "Status": "Completed"
        }
        
        # Add completion notes to description if provided
        completion_notes = arguments.get("completion_notes")
        if completion_notes:
            # Get current task to preserve existing description
            task_sf = SFType('Task', sf.session_id, sf.sf_instance)
            try:
                current_task = task_sf.get(task_id)
                existing_description = current_task.get("Description", "")
                if existing_description:
                    update_data["Description"] = f"{existing_description}\n\nCompletion Notes: {completion_notes}"
                else:
                    update_data["Description"] = f"Completion Notes: {completion_notes}"
            except:
                # If we can't get the task, just set the description
                update_data["Description"] = f"Completion Notes: {completion_notes}"
        
        # Add custom fields
        custom_fields = arguments.get("custom_fields", {})
        if custom_fields:
            update_data.update(custom_fields)
        
        # Update task
        task_sf = SFType('Task', sf.session_id, sf.sf_instance)
        task_sf.update(task_id, update_data)
        
        print(f"[Task] Completed task: {task_id}", file=sys.stderr)
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Task marked as completed successfully"
        }
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Task ERROR] {error_msg}", file=sys.stderr)
        return {"success": False, "error": error_msg}


def update_task(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        task_id = arguments.get("task_id")
        if not task_id:
            raise ValueError("task_id is required")
        update_data = {}
        TASK_UPDATE_MAP = {"subject": "Subject", "status": "Status", "priority": "Priority", "description": "Description", "activity_date": "ActivityDate", "who_id": "WhoId", "what_id": "WhatId", "owner_id": "OwnerId", "is_reminder_set": "IsReminderSet", "reminder_date_time": "ReminderDateTime"}
        for k, sf_field in TASK_UPDATE_MAP.items():
            v = arguments.get(k)
            if v is not None:
                update_data[sf_field] = v
        custom = arguments.get("custom_fields", {})
        if custom:
            update_data.update(custom)
        if not update_data:
            return {"success": True, "message": "No fields to update"}
        task_sf = SFType("Task", sf.session_id, sf.sf_instance)
        task_sf.update(task_id, update_data)
        return {"success": True, "task_id": task_id, "message": "Task updated"}
    except Exception as e:
        print(f"[Task ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def search_tasks(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        limit = min(int(arguments.get("limit", 50)), 200)
        fields = arguments.get("fields") or "Id, Subject, Status, Priority, ActivityDate, WhoId, WhatId, OwnerId"
        where = []
        def esc(s): return str(s).replace("'", "''")
        if arguments.get("subject"):
            where.append(f"Subject LIKE '%{esc(arguments['subject'])}%'")
        if arguments.get("status"):
            where.append(f"Status = '{esc(arguments['status'])}'")
        if arguments.get("priority"):
            where.append(f"Priority = '{esc(arguments['priority'])}'")
        if arguments.get("is_closed") is not None:
            where.append(f"IsClosed = {str(arguments['is_closed']).lower()}")
        if arguments.get("activity_date_from"):
            where.append(f"ActivityDate >= {repr(arguments['activity_date_from'])}")
        if arguments.get("activity_date_to"):
            where.append(f"ActivityDate <= {repr(arguments['activity_date_to'])}")
        where_clause = " AND ".join(where) if where else "Id != null"
        result = sf.query(f"SELECT {fields} FROM Task WHERE {where_clause} LIMIT {limit}")
        return {"success": True, "records": result.get("records", []), "totalSize": result.get("totalSize", 0)}
    except Exception as e:
        print(f"[Task ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def log_call(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Create a task representing a logged call."""
    try:
        subject = arguments.get("subject") or "Call"
        task_data = {"Subject": subject, "Status": "Completed", "TaskSubtype": "Call"}
        if arguments.get("who_id"):
            task_data["WhoId"] = arguments["who_id"]
        if arguments.get("what_id"):
            task_data["WhatId"] = arguments["what_id"]
        if arguments.get("comments"):
            task_data["Description"] = arguments["comments"]
        if arguments.get("call_date"):
            task_data["ActivityDate"] = arguments["call_date"]
        if arguments.get("call_duration_seconds") is not None:
            task_data["CallDurationInSeconds"] = arguments["call_duration_seconds"]
        if arguments.get("call_type"):
            task_data["CallType"] = arguments["call_type"]
        if arguments.get("call_disposition"):
            task_data["CallDisposition"] = arguments["call_disposition"]
        custom = arguments.get("custom_fields", {})
        if custom:
            task_data.update(custom)
        task_sf = SFType("Task", sf.session_id, sf.sf_instance)
        result = task_sf.create(task_data)
        return {"success": True, "task_id": result["id"], "message": "Call logged"}
    except Exception as e:
        print(f"[Task ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


