#!/usr/bin/env python3
"""
Utility tools for Luna AI Agent
Core utility functions and tool coordination
"""

from datetime import datetime

# Import tools from separate modules
from .memory_tools import memory_tools
from .reminder_tools import reminder_tools
from .workspace_tools import workspace_tools
from .browser_tools import browser_tools

def get_current_datetime() -> str:
    """
    Get the current date and time in ISO format using the system's local timezone.
    Use this tool whenever you need to know the current time for scheduling reminders,
    calculating relative times (like "in 2 hours", "tomorrow", "next week"), or 
    understanding temporal context.
    
    Returns:
        str: Current datetime in ISO format with local timezone (e.g., "2025-08-18T14:30:00-05:00")
        
    Example:
        - get_current_datetime() -> "2025-08-18T14:30:00-05:00"
        - Use this as reference for "remind me in 2 hours" -> add 2 hours to this time
        - Use this for "remind me tomorrow at 9 AM" -> next day at 9:00 AM
    """
    # Get current local time with timezone info
    current_time = datetime.now()
    # Return in ISO format with local timezone offset
    return current_time.isoformat()

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