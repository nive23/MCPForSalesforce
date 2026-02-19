"""
Salesforce MCP Tools Module
Contains all Salesforce operation tools organized by functionality
"""
from .accounts import get_account_tools, handle_account_tool_call
from .contacts import get_contact_tools, handle_contact_tool_call
from .leads import get_lead_tools, handle_lead_tool_call
from .campaigns import get_campaign_tools, handle_campaign_tool_call
from .opportunities import get_opportunity_tools, handle_opportunity_tool_call
from .tasks import get_task_tools, handle_task_tool_call
from .notes import get_note_tools, handle_note_tool_call
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
]

