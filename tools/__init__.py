"""
Salesforce MCP Tools Module
Contains all Salesforce operation tools organized by functionality
"""
import os
import sys

from .accounts import get_account_tools, handle_account_tool_call
from .contacts import get_contact_tools, handle_contact_tool_call
from .leads import get_lead_tools, handle_lead_tool_call
from .campaigns import get_campaign_tools, handle_campaign_tool_call
from .opportunities import get_opportunity_tools, handle_opportunity_tool_call
from .tasks import get_task_tools, handle_task_tool_call
from .soql import get_soql_tools, handle_soql_tool_call
from .reports import get_report_tools, handle_report_tool_call
from .user import get_user_tools, handle_user_tool_call
from .email import get_email_tools, handle_email_tool_call

def _load_note_tools():
    # 1) Normal import (tools/notes.py)
    try:
        from .notes import get_note_tools, handle_note_tool_call
        return get_note_tools, handle_note_tool_call
    except ModuleNotFoundError:
        pass
    # 2) Case sensitivity: on Linux, file might be Notes.py (e.g. from Windows Git)
    import importlib.util
    _tools_dir = os.path.dirname(os.path.abspath(__file__))
    for name in ("notes", "Notes"):
        path = os.path.join(_tools_dir, f"{name}.py")
        if os.path.isfile(path):
            try:
                spec = importlib.util.spec_from_file_location(f"tools.{name}", path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    return mod.get_note_tools, mod.handle_note_tool_call
            except Exception:
                pass
    return None

_note_handlers = _load_note_tools()
if _note_handlers is not None:
    get_note_tools, handle_note_tool_call = _note_handlers
else:
    _tools_dir = os.path.dirname(os.path.abspath(__file__))
    _contents = sorted(os.listdir(_tools_dir)) if os.path.isdir(_tools_dir) else []
    print(
        f"[tools] notes module not found; contents of tools/: {_contents}",
        file=sys.stderr,
    )
    def get_note_tools():
        return []

    def handle_note_tool_call(*args, **kwargs):
        return {"error": "Note tools not available (tools/notes.py missing in deployment)"}

from .quotes import get_quote_tools, handle_quote_tool_call

__all__ = [
    'get_account_tools', 'handle_account_tool_call',
    'get_contact_tools', 'handle_contact_tool_call',
    'get_lead_tools', 'handle_lead_tool_call',
    'get_campaign_tools', 'handle_campaign_tool_call',
    'get_opportunity_tools', 'handle_opportunity_tool_call',
    'get_task_tools', 'handle_task_tool_call',
    'get_note_tools', 'handle_note_tool_call',
    'get_quote_tools', 'handle_quote_tool_call',
    'get_soql_tools', 'handle_soql_tool_call',
    'get_report_tools', 'handle_report_tool_call',
    'get_user_tools', 'handle_user_tool_call',
    'get_email_tools', 'handle_email_tool_call',
]


