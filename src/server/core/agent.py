from google.adk.agents import Agent
from google.adk.tools import google_search

from .tools import get_async_tools
from .prompts import create_prompt
from .tools.callbacks import after_tool_callback

async def get_agent_async(client_id: str, memories=None):
    """Creates an ADK Agent equipped with MCP tools and tool logging asynchronously"""
    all_tools = [google_search] + await get_async_tools(client_id)
    
    agent = Agent(
        name="luna",
        model="gemini-2.5-flash-live-preview",
        description="A multimodal AI agent that can monitor video streams, answer questions, provide information, and assist with various tasks including UI automation. Has persistent memory capabilities and learns from usage patterns to provide proactive suggestions.",
        instruction="You are a helpful desktop voice assistant named Luna.",
        tools=all_tools,
        # after_tool_callback=after_tool_callback
    )
    
    return agent

async def get_text_agent_async(client_id: str, memories=None):
    """Creates text-only ADK Agent for overlay processing - raw LLM without tools"""
    agent = Agent(
        name="text_luna",
        model="gemini-2.5-flash", 
        description="Text processing agent for Luna AI overlay system. Raw LLM for text processing without external tools.",
        instruction=create_prompt(memories),
        tools=[],
        after_tool_callback=after_tool_callback
    )
    
    return agent