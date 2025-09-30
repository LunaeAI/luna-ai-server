
import json
import logging
from google.genai import Client
from google.genai import types as genai_types

from ..core.prompts import create_analysis_prompt
from .websocket_communication import send_websocket_command

logger = logging.getLogger(__name__)

async def analyze_behavior(memories_data, tools_data, client_id):
    """
    Analyze user behavior based on past memories and tool usage.
    Formats data for analysis and sends analysis request via WebSocket.
    """
    try:
        analysis_data = {
            "tool_executions": tools_data,
            "stored_memories": memories_data
        }
        
        # Generate analysis prompt
        prompt, response_schema, system_instruction = create_analysis_prompt(analysis_data)
        
        # Create Gemini client and make API call
        genai_client = Client(vertexai=False)
        
        # Prepare the content for the API call
        contents = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text=prompt)]
        )
        
        # Make the async API call to Gemini
        response = await genai_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_schema=response_schema,
                response_mime_type="application/json"
            )
        )
        
        # Parse the JSON response
        response_text = response.text
        response_data = json.loads(response_text)
        memory_modifications = response_data.get("memory_modifications", [])

        logger.info(f"[CLIENT:{client_id}] Behavior analysis response: {json.dumps(response_data)}")
        
        # Process each memory modification via WebSocket commands
        for modification in memory_modifications:
            action = modification.get("action")
            memory_id = modification.get("id")
            memory_text = modification.get("memory")
            
            if action == "create" and memory_text:
                # Create new memory
                await send_websocket_command(
                    "memory_request", 
                    "save", 
                    {"text": memory_text, "confidence": 0.5}, 
                    client_id
                )
                logger.info(f"[CLIENT:{client_id}] Created new memory from behavior analysis: {memory_text}")
                
            elif action == "reinforce" and memory_id:
                # Reinforce existing memory
                await send_websocket_command(
                    "memory_request", 
                    "reinforce", 
                    {"id": str(memory_id), "factor": 0.1}, 
                    client_id
                )
                logger.info(f"[CLIENT:{client_id}] Reinforced memory {memory_id} from behavior analysis")
                
            elif action == "weaken" and memory_id:
                # Weaken existing memory
                await send_websocket_command(
                    "memory_request", 
                    "weaken", 
                    {"id": str(memory_id), "factor": 0.1, "autoCleanupThreshold": 0.1}, 
                    client_id
                )
                logger.info(f"[CLIENT:{client_id}] Weakened memory {memory_id} from behavior analysis")
                
            elif action == "update_content" and memory_id and memory_text:
                # Update existing memory content
                await send_websocket_command(
                    "memory_request", 
                    "update", 
                    {"id": str(memory_id), "updates": {"text": memory_text}}, 
                    client_id
                )
                logger.info(f"[CLIENT:{client_id}] Updated memory {memory_id} content from behavior analysis")
        
        logger.info(f"[CLIENT:{client_id}] Behavior analysis completed, processed {len(memory_modifications)} memory modifications")
        
    except Exception as e:
        logger.error(f"[CLIENT:{client_id}] Behavior analysis failed: {e}")