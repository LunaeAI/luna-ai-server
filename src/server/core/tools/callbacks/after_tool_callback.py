"""
After-tool callback for logging tool executions via WebSocket
Uses ADK's ToolContext for client isolation
"""
from google.adk.tools import ToolContext
from google.adk.tools.base_tool import BaseTool
from typing import Dict, Any, Optional, Set
import asyncio

from ....util.websocket_communication import send_websocket_command

# Skip memory-related tools as they don't provide user behavioral insights
_SKIP_TOOLS = {
    "search_memory", "save_memory", "get_all_memories", "modify_memory",
    "delete_memory", "reinforce_memory", "weaken_memory", "clear_all_memories",
    "end_conversation_session", "get_memory_stats", "get_memory_by_id"
}


def after_tool_callback(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any
) -> Optional[Dict]:
    """
    WebSocket-based after_tool_callback for logging tool executions.
    Uses ADK's CallbackContext to access client_id for multi-client isolation.
    """

    if tool.name in _SKIP_TOOLS:
        return

    client_id = tool_context.state.get("client_id")

    asyncio.create_task(_log_tool_execution_async(tool, args, tool_response, client_id))


async def _log_tool_execution_async(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_response: Any,
    client_id: str
):
    """Asynchronously log tool execution via WebSocket"""

    execution_data = {
        "tool": tool.name,
        "arguments": args,
        "result": str(tool_response.content) if hasattr(tool_response, 'content') else str(tool_response),
    }

    try:
        await send_websocket_command("memory_request", "log_tool_execution", execution_data, client_id)
    except Exception:
        pass
