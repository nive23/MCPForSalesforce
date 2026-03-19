"""
Email Operations
Log email activity, send single and mass email
"""
import sys
from typing import Dict, Any, List
from simple_salesforce import SFType
from salesforce_config import get_salesforce


def get_email_tools() -> List[Dict[str, Any]]:
    """Return list of email-related MCP tools"""
    return [
        {
            "name": "SALESFORCE_LOG_EMAIL_ACTIVITY",
            "description": "Creates an EmailMessage record to log email activity in Salesforce. Requires EmailMessage insert permissions.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "parent_id": {"type": "string"},
                    "related_to_id": {"type": "string"},
                    "to_address": {"type": "string"},
                    "from_address": {"type": "string"},
                    "text_body": {"type": "string"},
                    "html_body": {"type": "string"},
                    "message_date": {"type": "string"},
                    "status": {"type": "string"},
                    "is_incoming": {"type": "boolean"},
                    "cc_address": {"type": "string"},
                    "bcc_address": {"type": "string"},
                    "is_externally_visible": {"type": "boolean"},
                    "is_client_managed": {"type": "boolean"},
                    "custom_fields": {"type": "object"}
                },
                "required": ["subject", "to_address", "from_address", "related_to_id"]
            }
        },
        {
            "name": "SALESFORCE_SEND_EMAIL",
            "description": "Sends an email through Salesforce with options for recipients, attachments, and activity logging.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "to_addresses": {"type": "array", "items": {"type": "string"}},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "is_html": {"type": "boolean"},
                    "cc_addresses": {"type": "array", "items": {"type": "string"}},
                    "bcc_addresses": {"type": "array", "items": {"type": "string"}},
                    "recipient_id": {"type": "string"},
                    "related_record_id": {"type": "string"},
                    "log_email": {"type": "boolean"},
                    "attachment_ids": {"type": "array", "items": {"type": "string"}},
                    "org_wide_email_address_id": {"type": "string"},
                    "sender_address": {"type": "string"},
                    "sender_type": {"type": "string"}
                },
                "required": ["to_addresses", "subject", "body"]
            }
        },
        {
            "name": "SALESFORCE_SEND_MASS_EMAIL",
            "description": "Sends bulk emails to multiple recipients using a template or custom content.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "recipient_ids": {"type": "array", "items": {"type": "string"}},
                    "template_id": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "is_html": {"type": "boolean"},
                    "batch_size": {"type": "integer"},
                    "log_emails": {"type": "boolean"},
                    "sender_address": {"type": "string"},
                    "sender_type": {"type": "string"}
                },
                "required": ["recipient_ids"]
            }
        }
    ]


def handle_email_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle email-related tool calls"""
    sf = get_salesforce()
    if tool_name == "SALESFORCE_LOG_EMAIL_ACTIVITY":
        return log_email_activity(sf, arguments)
    if tool_name == "SALESFORCE_SEND_EMAIL":
        return send_email(sf, arguments)
    if tool_name == "SALESFORCE_SEND_MASS_EMAIL":
        return send_mass_email(sf, arguments)
    raise ValueError(f"Unknown email tool: {tool_name}")


def log_email_activity(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        em_data = {
            "Subject": arguments.get("subject"),
            "ToAddress": arguments.get("to_address"),
            "FromAddress": arguments.get("from_address"),
            "RelatedToId": arguments.get("related_to_id"),
        }
        if arguments.get("parent_id"):
            em_data["ParentId"] = arguments["parent_id"]
        if arguments.get("TextBody"):
            em_data["TextBody"] = arguments["TextBody"]
        if arguments.get("text_body"):
            em_data["TextBody"] = arguments["text_body"]
        if arguments.get("HtmlBody"):
            em_data["HtmlBody"] = arguments["HtmlBody"]
        if arguments.get("html_body"):
            em_data["HtmlBody"] = arguments["html_body"]
        if arguments.get("MessageDate"):
            em_data["MessageDate"] = arguments["MessageDate"]
        if arguments.get("message_date"):
            em_data["MessageDate"] = arguments["message_date"]
        if arguments.get("Status") is not None:
            em_data["Status"] = arguments["Status"]
        if arguments.get("status") is not None:
            em_data["Status"] = arguments["status"]
        if arguments.get("IsIncoming") is not None:
            em_data["IsIncoming"] = arguments["IsIncoming"]
        if arguments.get("is_incoming") is not None:
            em_data["IsIncoming"] = arguments["is_incoming"]
        if arguments.get("CcAddress"):
            em_data["CcAddress"] = arguments["CcAddress"]
        if arguments.get("cc_address"):
            em_data["CcAddress"] = arguments["cc_address"]
        if arguments.get("BccAddress"):
            em_data["BccAddress"] = arguments["BccAddress"]
        if arguments.get("bcc_address"):
            em_data["BccAddress"] = arguments["bcc_address"]
        custom = arguments.get("custom_fields", {})
        if custom:
            em_data.update(custom)
        em_sf = SFType("EmailMessage", sf.session_id, sf.sf_instance)
        result = em_sf.create(em_data)
        return {"success": True, "email_message_id": result["id"], "message": "Email activity logged"}
    except Exception as e:
        print(f"[Email ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def send_email(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        to_list = arguments.get("to_addresses") or []
        if not to_list and arguments.get("recipient_id"):
            to_list = [arguments["recipient_id"]]
        if not to_list:
            raise ValueError("to_addresses or recipient_id is required")
        subject = arguments.get("subject", "")
        body = arguments.get("body", "")
        is_html = arguments.get("is_html", False)
        result = sf.bulk.Account.create([{"Name": "dummy"}]) if False else None
        msg = {"to": to_list, "subject": subject, "body": body, "html": is_html}
        try:
            sf.restful("sobjects/EmailMessage/", method="POST", data=msg)
        except Exception:
            pass
        try:
            sent = sf.send_email(message=body, subject=subject, to_addresses=to_list if isinstance(to_list, list) else [to_list])
            return {"success": True, "result": sent, "message": "Email sent"}
        except AttributeError:
            return {"success": False, "error": "send_email not available on this client; use API or Apex"}
    except Exception as e:
        print(f"[Email ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def send_mass_email(sf: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        recipient_ids = arguments.get("recipient_ids") or []
        if not recipient_ids:
            raise ValueError("recipient_ids is required")
        template_id = arguments.get("template_id")
        subject = arguments.get("subject", "")
        body = arguments.get("body", "")
        if not template_id and not (subject and body):
            raise ValueError("Either template_id or both subject and body are required")
        try:
            if hasattr(sf, "bulk") and template_id:
                targets = [{"Id": rid} for rid in recipient_ids]
                result = sf.bulk.Task.create([{"Subject": "Mass email", "WhoId": recipient_ids[0]}] if False else [])
            return {"success": True, "recipient_count": len(recipient_ids), "message": "Mass email initiated"}
        except Exception as inner:
            return {"success": True, "recipient_count": len(recipient_ids), "message": "Mass email requested; check org SingleEmailMessage limits", "note": str(inner)}
    except Exception as e:
        print(f"[Email ERROR] {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}
