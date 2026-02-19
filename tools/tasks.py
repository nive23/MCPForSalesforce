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
            "description": "Creates a new task in Salesforce to track activities, to-dos, and follow-ups related to contacts, leads, or opportunities.",
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
                    "who_id": {
                        "type": "string",
                        "description": "Contact or Lead ID (WhoId)"
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
        }
    ]

def handle_task_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle task-related tool calls"""
    sf = get_salesforce()
    
    if tool_name == "SALESFORCE_CREATE_TASK":
        return create_task(sf, arguments)
    elif tool_name == "SALESFORCE_COMPLETE_TASK":
        return complete_task(sf, arguments)
    else:
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
        
        # Add optional fields
        optional_fields = [
            "status", "priority", "activity_date", "description",
            "who_id", "what_id", "owner_id", "is_reminder_set",
            "reminder_date_time"
        ]
        
        for field in optional_fields:
            value = arguments.get(field)
            if value is not None:
                # Convert field name to Salesforce API name
                sf_field = field[0].upper() + field[1:] if field else field
                # Handle special cases
                if field == "activity_date":
                    sf_field = "ActivityDate"
                elif field == "who_id":
                    sf_field = "WhoId"
                elif field == "what_id":
                    sf_field = "WhatId"
                elif field == "owner_id":
                    sf_field = "OwnerId"
                elif field == "is_reminder_set":
                    sf_field = "IsReminderSet"
                elif field == "reminder_date_time":
                    sf_field = "ReminderDateTime"
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
        return {
            "success": False,
            "error": error_msg
        }

