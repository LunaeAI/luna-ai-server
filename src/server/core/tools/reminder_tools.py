#!/usr/bin/env python3
"""
Reminder management tools for Luna AI Agent
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from google.adk.tools import ToolContext

from ...util.websocket_communication import send_websocket_command
import json
import logging

logger = logging.getLogger(__name__)

async def save_reminder(tool_context: ToolContext, title: str, description: str, trigger_time: str, repeat_pattern: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new reminder for the user that will trigger at the specified time. If a repeat pattern is not explicitly stated (e.g. weekly), assume the user means a one-shot reminder.
    
    Use this tool when the user asks you to remind them of something at a specific time.
    IMPORTANT: Always call get_current_datetime() first to get the current time as reference
    when parsing relative time expressions like "in 2 hours", "tomorrow", "next week".
    
    Args:
        title: Brief title for the reminder (e.g., "call mom", "take medication")
        description: More detailed description of what to remind about
        trigger_time: When to trigger the reminder in UTC ISO 8601 format ending with 'Z' (e.g., "2025-08-18T18:00:00Z")
        repeat_pattern: Optional repeat pattern: "daily", "weekly", "monthly", or None for one-shot
        tool_context: ADK ToolContext containing client_id in state
        
    Returns:
        dict: {"status": "success|error", "reminder": reminder_object, "message": Optional[error_message]}
        
    Examples:
        - User: "Remind me to call my mom at 6 PM"
        - First call get_current_datetime() to know today's date
        - save_reminder("call mom", "Call mom", "2025-08-18T18:00:00Z")
        
        - User: "Remind me to take my vitamins every morning at 8 AM"
        - save_reminder("take vitamins", "Take daily vitamins", "2025-08-19T08:00:00Z", "daily")
        
        - User: "Remind me in 2 hours to check my email"
        - First call get_current_datetime() to get current time, then add 2 hours
        - save_reminder("check email", "Check email", "2025-08-18T16:30:00Z")
    """
    client_id = tool_context.state.get("client_id")
    
    try:
        # Parse UTC ISO 8601 format (must end with 'Z')
        if not trigger_time.endswith('Z'):
            return {"status": "error", "message": "trigger_time must be in UTC format ending with 'Z' (e.g., '2025-08-18T18:00:00Z')"}
        
        trigger_datetime = datetime.fromisoformat(trigger_time.replace('Z', '+00:00'))
        current_datetime = datetime.now(timezone.utc)
        
        if not repeat_pattern and trigger_datetime <= current_datetime:
            return {"status": "error", "message": "Cannot set reminder for a time in the past. Please choose a future date and time. Current time: " + current_datetime.isoformat() + ", Trigger time: " + trigger_time}
            
    except ValueError:
        return {"status": "error", "message": "Invalid datetime format. Use UTC ISO 8601 format ending with 'Z' (e.g., '2025-08-18T18:00:00Z')"}
    
    reminder_data = {
        "title": title,
        "description": description,
        "trigger_time": trigger_time,
        "type": "repeatable" if repeat_pattern else "one-shot",
        "repeat_pattern": repeat_pattern,
    }
    
    result = await send_websocket_command("reminder_request", "save", reminder_data, client_id)

    logger.info(f"Save reminder result: {json.dumps(result)}")

    return result


async def get_reminders(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Retrieve all of the user's reminders to provide context or help manage them.
    
    Use this tool when:
    - User asks "What reminders do I have?"
    - User wants to see their scheduled reminders
    - You need context about existing reminders before creating new ones
    - User asks to modify or delete existing reminders
    
    Args:
        tool_context: ADK ToolContext containing client_id in state
        
    Returns:
        dict: {"status": "success|error", "reminders": List[reminder_objects], "message": Optional[error_message]}
        
    Example reminder object:
        {
            "id": "uuid-123",
            "title": "call mom",
            "description": "Call mom",
            "trigger_time": "2025-08-18T18:00:00Z",
            "type": "one-shot",
            "status": "active",
            "created_at": "2025-08-18T10:00:00Z"
        }
    """
    client_id = tool_context.state.get("client_id")
    
    result = await send_websocket_command("reminder_request", "list", {}, client_id)

    logger.info(f"Get reminders result: {json.dumps(result)}")
    
    return result
        

async def update_reminder(reminder_id: str, updates: Dict[str, Any], original_reminder: Optional[Dict[str, Any]], tool_context: ToolContext) -> Dict[str, Any]:
    """
    Update an existing reminder's properties.
    
    Use this tool when the user wants to modify an existing reminder.
    First call get_reminders() to see available reminders and their IDs.
    
    Args:
        reminder_id: The ID of the reminder to update
        updates: Dictionary of fields to update (title, description, trigger_time, status, etc.)
        original_reminder: Optional original reminder data (used for validation when updating trigger_time)
        tool_context: ADK ToolContext containing client_id in state
        
    Returns:
        dict: {"status": "success|error", "reminder": updated_reminder, "message": Optional[error_message]}
        
    Examples:
        - User: "Change my 6 PM reminder to 7 PM"
        - First get_reminders(), find the reminder, then:
        - update_reminder("uuid-123", {"trigger_time": "2025-08-18T19:00:00Z"}, original_reminder)
        
        - User: "Disable my daily vitamin reminder"
        - update_reminder("uuid-456", {"status": "inactive"})
    """
    try:
        client_id = tool_context.state.get("client_id")

        if "trigger_time" in updates:
            try:
                # Parse UTC ISO 8601 format (must end with 'Z')
                trigger_time_str = updates["trigger_time"]
                if not trigger_time_str.endswith('Z'):
                    return {"status": "error", "message": "trigger_time must be in UTC format ending with 'Z' (e.g., '2025-08-18T18:00:00Z')"}
                
                trigger_datetime = datetime.fromisoformat(trigger_time_str.replace('Z', '+00:00'))
                current_datetime = datetime.now(timezone.utc)
                
                is_one_shot = (original_reminder and 
                             original_reminder.get("type") == "one-shot" and 
                             not original_reminder.get("repeat_pattern"))
                
                if is_one_shot and trigger_datetime <= current_datetime:
                    return {"status": "error", "message": "Cannot set reminder for a time in the past. Please choose a future date and time."}
                    
            except ValueError:
                return {"status": "error", "message": "Invalid datetime format. Use UTC ISO 8601 format ending with 'Z' (e.g., '2025-08-18T18:00:00Z')"}
        
        request_data = {
            "reminder_id": reminder_id,
            "updates": updates
        }
        
        result = await send_websocket_command("reminder_request", "update", request_data, client_id)

        logger.info(f"Update reminder result: {json.dumps(result)}")

        return result
            
    except Exception as e:
        return {"status": "error", "message": f"Failed to update reminder: {str(e)}"}


async def delete_reminder(reminder_id: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Permanently delete a reminder.
    
    Use this tool when the user wants to remove a reminder completely.
    First call get_reminders() to see available reminders and their IDs.
    
    Args:
        reminder_id: The ID of the reminder to delete
        tool_context: ADK ToolContext containing client_id in state
        
    Returns:
        dict: {"status": "success|error", "message": Optional[error_message]}
        
    Examples:
        - User: "Delete my reminder about calling mom"
        - First get_reminders(), find the reminder, then:
        - delete_reminder("uuid-123")
    """
    try:
        client_id = tool_context.state.get("client_id")
        
        request_data = {"id": reminder_id}
        
        result = await send_websocket_command("reminder_request", "delete", request_data, client_id)

        logger.info(f"Delete reminder result: {json.dumps(result)}")

        return result
            
    except Exception as e:
        return {"status": "error", "message": f"Failed to delete reminder: {str(e)}"}


# Export reminder tools
reminder_tools = [
    save_reminder,
    get_reminders,
    update_reminder,
    delete_reminder
]
