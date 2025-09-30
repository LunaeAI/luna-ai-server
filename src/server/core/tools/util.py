#!/usr/bin/env python3
"""
Utility tools for Luna AI Agent
Core utility functions and tool coordination
"""

import logging
from datetime import datetime, timezone

# Import tools from separate modules
from .memory_tools import memory_tools
from .reminder_tools import reminder_tools
from .workspace_tools import workspace_tools
from .browser_tools import browser_tools

logger = logging.getLogger(__name__)

def get_current_datetime() -> str:
    """
    Get the current date and time in UTC timezone for reminder scheduling.
    Use this tool whenever you need to know the current time for scheduling reminders,
    calculating relative times (like "in 2 hours", "tomorrow", "next week"), or 
    understanding temporal context.
    
    IMPORTANT: This returns UTC time for consistency with reminder system requirements.
    When creating reminders, use this UTC time as your base and add time offsets to get 
    the trigger_time in the correct "YYYY-MM-DDTHH:MM:SSZ" format.
    
    Returns:
        str: Current datetime in UTC ISO format ending with 'Z' (e.g., "2025-08-18T19:30:00Z")
        
    Example:
        - get_current_datetime() -> "2025-08-18T19:30:00Z"
        - For "remind me in 2 hours": add 2 hours to get "2025-08-18T21:30:00Z"
        - For "remind me tomorrow at 9 AM UTC": next day at "2025-08-19T09:00:00Z"
    """
    # Get current UTC time
    current_time = datetime.now(timezone.utc)
    # Return in UTC ISO format with 'Z' suffix
    return current_time.isoformat().replace('+00:00', 'Z')

def stop_streaming(function_name: str):
    """Stop the streaming

    Args:
        function_name: The name of the streaming function to stop.
    """
    pass

def end_conversation_session():
    """End the current conversation session gracefully when the user indicates they are finished.
    
    Use this tool when you detect that the user's conversation has naturally concluded. 
    Look for these conversational cues:
    
    **Clear Ending Signals:**
    - "Thanks, that's all I needed"
    - "Perfect, goodbye" / "Bye" / "See you later"
    - "That solved my problem, thank you"
    - "I'm done for now" / "I'm all set"
    - "Great, I have everything I need"
    
    **Satisfaction & Closure:**
    - User expresses satisfaction with your help
    - Problem has been completely resolved
    - User thanks you and doesn't ask follow-up questions
    - User indicates they're leaving or ending the session
    
    **When NOT to use:**
    - User asks follow-up questions
    - User seems to want to continue the conversation
    - You're in the middle of a multi-step task
    - User hasn't expressed satisfaction or closure
    
    This will mark the session for graceful closure after you finish your current response.
    The session will end after you complete your turn (e.g., saying "You're welcome, goodbye!").
    """
    return "Session marked for graceful closure after current response completes."


# Export the core utility tools along with imported tools
util_tools = [
    get_current_datetime,
    stop_streaming,
    end_conversation_session,
] + memory_tools + reminder_tools + workspace_tools + browser_tools