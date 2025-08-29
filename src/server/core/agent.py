from google.adk.agents import Agent
from google.adk.tools import google_search
from dotenv import load_dotenv

from .tools import get_async_tools
from .prompts import luna_prompt
from .tools.callbacks import after_tool_callback

async def get_agent_async(memories=None):
    """Creates an ADK Agent equipped with MCP tools and tool logging asynchronously"""
    
    load_dotenv()
    
    all_tools = [google_search] + await get_async_tools()
    
    instruction = luna_prompt
    if memories and len(memories) > 0:
        memory_context = "\n\nCONTEXT - STORED MEMORIES:\n"
        memory_context += "You have access to the following memories from previous interactions. Use this context to provide more personalized and relevant assistance:\n"
        for memory in memories:
            confidence = memory.get('confidence', 0.0)
            memory_text = memory.get('memory', '')
            memory_context += f"- {memory_text} (confidence: {confidence:.2f})\n"
        memory_context += "\nUse these memories to better understand the user's preferences and provide more relevant assistance.\n"
        instruction = luna_prompt + memory_context
    
    agent = Agent(
        name="luna",
        model="gemini-2.5-flash-live-preview",
        description="A multimodal AI agent that can monitor video streams, answer questions, provide information, and assist with various tasks including UI automation. Has persistent memory capabilities and learns from usage patterns to provide proactive suggestions.",
        instruction=instruction,
        tools=all_tools,
        # after_tool_callback=after_tool_callback
    )
    
    return agent

async def get_text_agent_async(memories=None):
    """Creates text-only ADK Agent for overlay processing - raw LLM without tools"""
    
    load_dotenv()
    
    instruction = luna_prompt
    if memories and len(memories) > 0:
        memory_context = "\n\nCONTEXT - STORED MEMORIES:\n"
        memory_context += "You have access to the following memories from previous interactions. Use this context to provide more personalized and relevant assistance:\n"
        for memory in memories:
            confidence = memory.get('confidence', 0.0)
            memory_text = memory.get('memory', '')
            memory_context += f"- {memory_text} (confidence: {confidence:.2f})\n"
        memory_context += "\nUse these memories to better understand the user's preferences and provide more relevant assistance.\n"
        instruction = luna_prompt + memory_context
    
    agent = Agent(
        name="text_luna",
        model="gemini-2.5-flash", 
        description="Text processing agent for Luna AI overlay system. Raw LLM for text processing without external tools.",
        instruction=instruction, 
        tools=[],
        after_tool_callback=after_tool_callback
    )
    
    return agent