"""
WebSocketServer - Handles FastAPI setup, multi-client WebSocket connections, and message routing
"""
import json
import asyncio
import base64
import logging
import os
import uuid
import datetime
from typing import Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Query
import uvicorn
import httpx

from google.genai.types import Blob
from ..util.websocket_communication import set_websocket_connection, remove_websocket_connection, handle_websocket_response, get_mcp_queue
from .agent_runner import AgentRunner
from ..core.wake_word_detector import WakeWordDetector, WakeWordEvent, WakeWordStatus
from ...auth import get_user_from_token
from ...database import get_database_session, AgentUserContext
from ...database.models import User

logger = logging.getLogger(__name__)
class WebSocketServer:
    """Handles multi-client WebSocket connections and message routing for dual voice/text sessions"""
    
    def __init__(self):
        self.app = FastAPI(title="Luna AI Multi-Client Streaming Server")
        
        # Multi-client connection tracking 
        self.client_websockets: Dict[str, WebSocket] = {}
        self.client_runners: Dict[str, AgentRunner] = {}
        self.client_user_contexts: Dict[str, AgentUserContext] = {}  # Track minimal user context per client
        
        # Per-client session state tracking
        self.client_voice_sessions: Dict[str, bool] = {}
        self.client_text_sessions: Dict[str, bool] = {}
        self.client_voice_tasks: Dict[str, asyncio.Task] = {}
        self.client_text_tasks: Dict[str, asyncio.Task] = {}
        
        # Per-client wake word detection
        self.client_wake_word_detectors: Dict[str, WakeWordDetector] = {}
        self.client_wake_word_tasks: Dict[str, asyncio.Task] = {}

        # Setup routes directly in constructor
        self._setup_routes()
    
    def _generate_client_id(self) -> str:
        """Generate a unique client ID"""
        return str(uuid.uuid4())
    
    def _register_client(self, client_id: str, websocket: WebSocket, user: User):
        """Register a new client with authenticated user"""
        # Convert User to minimal AgentUserContext
        user_context = user.to_agent_context()
        
        self.client_websockets[client_id] = websocket
        self.client_runners[client_id] = AgentRunner(client_id, user_context)
        self.client_user_contexts[client_id] = user_context
        self.client_voice_sessions[client_id] = False
        self.client_text_sessions[client_id] = False
        
        # Initialize wake word detector for this client
        self.client_wake_word_detectors[client_id] = WakeWordDetector(client_id)
        
        # Provide websocket reference to util.py tools
        set_websocket_connection(client_id, websocket)
        
        # Pre-initialize voice agent and warm up MCP connections immediately
        asyncio.create_task(self._pre_initialize_agent(client_id))
        
        # Start wake word detection for this client
        asyncio.create_task(self._start_wake_word_detection(client_id))
        
        logger.info(f"Client {client_id} registered with user context: {user_context}")
        
        logger.info(f"Client {client_id} registered with user context: {user_context}")

    async def _pre_initialize_agent(self, client_id: str):
        """Pre-initialize agent and warm up MCP connections for instant session starts"""
        try:
            agent_runner = self.client_runners[client_id]
            websocket = self.client_websockets[client_id]

            await agent_runner._initialize_voice()  # This includes MCP warming
            logger.info(f"[WEBSOCKET] Pre-initialized voice agent for client {client_id} - ready for instant session start")

            
            await websocket.send_text(json.dumps({
                "type": "initialized",
            }))
        except Exception as e:
            logger.error(f"[WEBSOCKET] Failed to pre-initialize agent for client {client_id}: {e}")
            # Don't raise - let the voice session initialization handle it gracefully
    
    def _setup_routes(self):
        """Set up WebSocket routes"""
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
            """Main WebSocket endpoint for both voice and text sessions - requires JWT authentication"""
            
            # Authenticate user before accepting WebSocket connection
            from ...database.connection import get_session_factory
            SessionLocal = get_session_factory()
            db = SessionLocal()
            
            try:
                # Validate JWT token
                user = await get_user_from_token(db, token)
                if not user:
                    await websocket.close(code=4001, reason="Invalid or expired token")
                    return
                
                # Accept WebSocket connection after successful authentication
                await websocket.accept()
                
                # Generate unique client ID
                client_id = self._generate_client_id()
                
                # Register client with user context
                self._register_client(client_id, websocket, user)
                
                logger.info(f"[WEBSOCKET] Authenticated client {client_id} connected for user {user.username}")
                
            except Exception as e:
                logger.error(f"[WEBSOCKET] Authentication error: {e}")
                await websocket.close(code=4001, reason="Authentication failed")
                return
            finally:
                db.close()
            
            try:
                logger.info(f"[WEBSOCKET] Client {client_id} ready, waiting for session initialization...")
                
                while True:
                    try:
                        message_json = await websocket.receive_text()
                        msg = json.loads(message_json)
                        message = msg.get("payload")
                        message_type = msg.get("type", "")
                        # Route messages based on type
                        if message_type == "start_voice_session":
                            await self._handle_voice_session_start(client_id, websocket, message)
                        elif message_type == "start_text_session":
                            await self._handle_text_session_start(client_id, websocket, message)
                        elif message_type == "stop_voice_session":
                            await self._handle_voice_session_stop(client_id)
                        elif message_type == "stop_text_session":
                            await self._handle_text_session_stop(client_id)
                        elif message_type == "text":
                                await self._route_text_session_message(client_id, message)
                        elif message_type.endswith("_response"):
                            handle_websocket_response(client_id, msg)
                        elif message_type == "audio" or message_type == "video":
                            if self.client_voice_sessions.get(client_id, False):
                                await self._route_voice_session_message(client_id, message)
                            else:
                                if message_type == "audio":
                                    await self._route_wake_word_audio(client_id, message)
                            
                    except WebSocketDisconnect:
                        logger.info(f"[WEBSOCKET] Client {client_id} disconnected")
                        break
                    except json.JSONDecodeError as e:
                        logger.error(f"[WEBSOCKET] Invalid JSON received from client {client_id}: {e}")
                        continue  # Continue processing messages despite JSON errors
                    except Exception as e:
                        logger.error(f"[WEBSOCKET] Error processing message from client {client_id}: {e}")
                        continue  # Continue processing messages despite other errors
                        
            except Exception as e:
                logger.error(f"[WEBSOCKET] Fatal error for client {client_id}: {e}")
            finally:
                await self._cleanup_client(client_id)
                
        @self.app.get("/")
        async def root():
            """Root endpoint with server info"""
            return {
                "name": "Luna AI Multi-Client Streaming Server",
                "version": "1.0.0",
                "status": "running",
                "active_clients": len(self.client_websockets),
                "endpoints": {
                    "health": "/health",
                    "weather": "/weather?city={city_name}",
                    "websocket": "/ws"
                },
                "description": "Multi-client WebSocket server for Luna AI agent communication"
            }
                
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "active_clients": len(self.client_websockets),
                "active_voice_sessions": sum(self.client_voice_sessions.values()),
                "active_text_sessions": sum(self.client_text_sessions.values()),
                "active_wake_word_detectors": len(self.client_wake_word_detectors),
            }

        @self.app.get("/weather")
        async def get_weather(city: str = Query(..., description="City name to get weather for")):
            """Get weather data for a specified city using OpenWeatherMap API"""
            try:
                # Get API key from environment
                api_key = os.getenv("WEATHERAPI_KEY")
                if not api_key:
                    raise HTTPException(status_code=500, detail="Weather API key not configured")
                
                # Make request to OpenWeatherMap API
                url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        weather_data = response.json()
                        return weather_data
                    elif response.status_code == 401:
                        raise HTTPException(status_code=500, detail="Invalid API key")
                    elif response.status_code == 404:
                        raise HTTPException(status_code=404, detail=f"City '{city}' not found")
                    else:
                        raise HTTPException(status_code=500, detail="Weather service temporarily unavailable")
                        
            except httpx.RequestError as e:
                logger.error(f"Weather API request failed: {e}")
                raise HTTPException(status_code=500, detail="Failed to connect to weather service")
            except Exception as e:
                logger.error(f"Weather endpoint error: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")

        @self.app.post("/mcp/{client_id}/{mcp_name}")
        async def mcp_proxy(client_id: str, mcp_name: str, request: Request):
            """Proxy MCP requests to clients"""
            if client_id not in self.client_websockets:
                raise HTTPException(status_code=404, detail="Client not connected")
            
            if mcp_name not in ["filesystem", "google"]:
                raise HTTPException(status_code=400, detail="Unknown MCP name")
            
            websocket = self.client_websockets[client_id]
            data = await request.json()
            
            # Check if this is a notification-style request (fire and forget)
            method = data.get("method", "")
            if method.startswith("notification"):
                # Fire and forget - send notification immediately without queuing
                request_id = str(uuid.uuid4())
                message = {
                    "type": "mcp_request",
                    "mcp_name": mcp_name,
                    "data": data,
                    "request_id": request_id
                }
                
                logger.info(f"[WEBSOCKET] Firing MCP notification to client {client_id} for {mcp_name} with request_id {request_id}")
                await websocket.send_text(json.dumps(message))
                
                # Return 202 Accepted for notifications (MCP client expects this for fire-and-forget)
                from fastapi.responses import Response
                return Response(status_code=202)
            
            # Handle regular request-response MCP calls
            request_id = str(uuid.uuid4())
            message = {
                "type": "mcp_request",
                "mcp_name": mcp_name,
                "data": data,
                "request_id": request_id
            }
            
            logger.info(f"[WEBSOCKET] Forwarding MCP request to client {client_id} for {mcp_name} with request_id {request_id}")
            await websocket.send_text(json.dumps(message))
            
            # Wait for response with timeout to prevent blocking
            try:
                response_data = await asyncio.wait_for(get_mcp_queue(client_id).get(), timeout=30.0)

                logger.info(f"[WEBSOCKET] Received MCP response: {response_data}")
                
                # Handle null or empty responses gracefully
                if response_data is None:
                    logger.warning(f"[WEBSOCKET] Received null response for MCP request {request_id}")
                    return {"error": "No response received from client"}
                
                return response_data
                
            except asyncio.TimeoutError:
                logger.error(f"[WEBSOCKET] Timeout waiting for MCP response for client {client_id}, request {request_id}")
                return {"error": "Request timeout - no response from client"}
            except Exception as e:
                logger.error(f"[WEBSOCKET] Error processing MCP response for client {client_id}, request {request_id}: {e}")
                return {"error": f"Internal error: {str(e)}"}

    async def _handle_voice_session_start(self, client_id: str, websocket: WebSocket, message: dict):
        """Start voice session with live streaming for a specific client"""
        try:
            initial_message = message.get("initial_message")
            memories = message.get("memories", [])
            
            if initial_message:
                logger.info(f"[WEBSOCKET] Starting voice session for client {client_id} with initial message: {initial_message[:50]}...")
            else:
                logger.info(f"[WEBSOCKET] Starting voice session for client {client_id} without initial message")
            
            logger.info(f"[WEBSOCKET] Voice session starting for client {client_id} with {len(memories)} memories")
            
            agent_runner = self.client_runners[client_id]
            
            live_events, live_request_queue = await agent_runner.start_voice_conversation(initial_message, memories=memories)
            self.client_voice_sessions[client_id] = True
            
            async def voice_message_sender(message: dict):
                try:
                    message["session"] = "voice"
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"[WEBSOCKET] Voice send error for client {client_id}: {e}")
            
            voice_events_task = asyncio.create_task(
                agent_runner.process_voice_events(live_events, voice_message_sender)
            )
            self.client_voice_tasks[client_id] = voice_events_task
            
            await websocket.send_text(json.dumps({
                "type": "voice_session_started",
                "status": "success",
                "memories_loaded": len(memories)
            }))
            
        except Exception as e:
            logger.error(f"[WEBSOCKET] Error starting voice session for client {client_id}: {e}")
            await websocket.send_text(json.dumps({
                "type": "voice_session_error",
                "error": str(e)
            }))



    async def _handle_text_session_start(self, client_id: str, websocket: WebSocket, message: dict):
        """Start a new text session with specified type (explain/rewrite/chat)"""
        try:
            message = message.get("initial_message", message)  # Support both nested and flat structure
            session_type = message.get("session_type")  # 'explain', 'rewrite', or 'chat'
            content_obj = message.get("content")  # Now expects object with selected_text and user_query
            
            # Handle nested memories structure
            memories_obj = message.get("memories", {})
            if isinstance(memories_obj, dict) and "memories" in memories_obj:
                memories = memories_obj["memories"]
            else:
                memories = memories_obj if isinstance(memories_obj, list) else []
            
            agent_runner = self.client_runners[client_id]
            
            # Check if text session is already active
            if self.client_text_sessions.get(client_id, False):
                current_type = agent_runner.get_text_session_type()
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": f"Text session already active with type '{current_type}'. End current session first."
                }))
                return
            
            # Validate content structure
            if not isinstance(content_obj, dict) or "selected_text" not in content_obj or "user_query" not in content_obj:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": "Content must be an object with 'selected_text' and 'user_query' fields.  Received: " + str(json.dumps(content_obj))
                }))
                return
            
            selected_text = content_obj.get("selected_text", "")
            user_query = content_obj.get("user_query", "")
            
            logger.info(f"[WEBSOCKET] Starting {session_type} text session for client {client_id} with selected_text: {selected_text[:50]}... and user_query: {user_query[:50]}...")
            
            # Start new text session with specified type
            async_gen = await agent_runner.start_text_session_with_type(session_type, selected_text, user_query, memories=memories)
            self.client_text_sessions[client_id] = True
            
            # Send session started confirmation
            await websocket.send_text(json.dumps({
                "type": "text_session_started",
                "session_type": session_type,
                "memories_loaded": len(memories)
            }))
            
            # Stream the initial response in background task
            text_streaming_task = asyncio.create_task(
                self._stream_text_response_from_generator(client_id, websocket, async_gen)
            )
            self.client_text_tasks[client_id] = text_streaming_task
                
        except Exception as e:
            logger.error(f"[WEBSOCKET] Error starting text session for client {client_id}: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": str(e)
            }))

    async def _stream_text_response_from_generator(self, client_id: str, websocket: WebSocket, async_gen):
        """Stream text response from an async generator for a specific client"""
        try:
            # Stream the response in real-time
            async for event in async_gen:
                if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            # Send each text chunk as it arrives
                            await websocket.send_text(json.dumps({
                                "session": "text",
                                "type": "text_content",
                                "data": part.text
                            }))
            
            # Send completion signal
            await websocket.send_text(json.dumps({
                "session": "text",
                "type": "complete",
                "data": ""
            }))
            
        except Exception as e:
            logger.error(f"[WEBSOCKET] Error streaming text response for client {client_id}: {e}")
            await websocket.send_text(json.dumps({
                "session": "text",
                "type": "error",
                "error": str(e)
            }))

    async def _handle_voice_session_stop(self, client_id: str):
        """Stop voice session for a specific client"""
        if not self.client_voice_sessions.get(client_id, False):
            return
            
        try:
            # Cancel voice events task
            if client_id in self.client_voice_tasks:
                voice_task = self.client_voice_tasks[client_id]
                if not voice_task.done():
                    voice_task.cancel()
                    try:
                        await voice_task
                    except asyncio.CancelledError:
                        pass
                del self.client_voice_tasks[client_id]
            
            # End voice conversation
            agent_runner = self.client_runners[client_id]
            await agent_runner.end_voice_conversation()
            self.client_voice_sessions[client_id] = False
            
            websocket = self.client_websockets[client_id]

            await websocket.send_text(json.dumps({
                "type": "voice_session_ended",
            }))
            
        except Exception as e:
            logger.error(f"[WEBSOCKET] Error stopping voice session for client {client_id}: {e}")

    async def _handle_text_session_stop(self, client_id: str):
        """Stop text session for a specific client"""
        if not self.client_text_sessions.get(client_id, False):
            return
            
        try:
            # Cancel text streaming task
            if client_id in self.client_text_tasks:
                text_task = self.client_text_tasks[client_id]
                if not text_task.done():
                    text_task.cancel()
                    try:
                        await text_task
                    except asyncio.CancelledError:
                        pass
                del self.client_text_tasks[client_id]
            
            agent_runner = self.client_runners[client_id]
            await agent_runner.end_text_conversation()
            self.client_text_sessions[client_id] = False
            logger.info(f"[WEBSOCKET] Text session stopped for client {client_id}")

            websocket = self.client_websockets[client_id]
            await websocket.send_text(json.dumps({
                "type": "text_session_ended",
            }))

        except Exception as e:
            logger.error(f"[WEBSOCKET] Error stopping text session for client {client_id}: {e}")

    async def _route_wake_word_audio(self, client_id: str, message: dict):
        """Route audio data to wake word detection for a specific client"""
        # Extract audio data and forward to wake word detector
        try:
            data = message.get("data", "")
            if data:
                audio_bytes = base64.b64decode(data)
                
                detector = self.client_wake_word_detectors.get(client_id)
                if detector:
                    detector.add_audio_chunk(audio_bytes)
        except Exception as e:
            logger.error(f"[WEBSOCKET] Error routing audio to wake word detector for client {client_id}: {e}")

    async def _start_wake_word_detection(self, client_id: str):
        """Start wake word detection task for a specific client"""
        try:
            detector = self.client_wake_word_detectors[client_id]
            websocket = self.client_websockets[client_id]
            
            async def wake_word_event_handler():
                try:
                    async for event in detector.start():
                        if isinstance(event, WakeWordEvent) and event.detected:
                            logger.info(f"[WEBSOCKET] Wake word detected for client {client_id}: {event.wake_word} (confidence: {event.confidence:.3f})")
                            
                            # Automatically start voice session (client will know from voice_session_started event)
                            await self._handle_voice_session_start(client_id, websocket, {"initial_message": None, "memories": []})
                        
                        elif isinstance(event, WakeWordStatus):
                            # Log periodic status updates (optional, can be removed if too verbose)
                            max_score = max(event.scores.values()) if event.scores else 0.0
                            if max_score > 0.1:  # Only log if there's some audio activity
                                logger.debug(f"[WEBSOCKET] Wake word scores for client {client_id}: {event.scores}")
                        
                except Exception as e:
                    logger.error(f"[WEBSOCKET] Error in wake word detection for client {client_id}: {e}")
            
            # Start the wake word detection task
            wake_word_task = asyncio.create_task(wake_word_event_handler())
            self.client_wake_word_tasks[client_id] = wake_word_task
            
            logger.info(f"[WEBSOCKET] Wake word detection started for client {client_id}")
            
        except Exception as e:
            logger.error(f"[WEBSOCKET] Failed to start wake word detection for client {client_id}: {e}")

    async def _route_voice_session_message(self, client_id: str, message: dict):
        """Route messages to appropriate active session for a specific client"""
        
        agent_runner = self.client_runners[client_id]
        
        await agent_runner.send_voice_content(message)
    
    async def _route_text_session_message(self, client_id: str, message: dict):
        """Continue active text conversation for a specific client"""
        agent_runner = self.client_runners[client_id]
        websocket = self.client_websockets[client_id]
            
        msg = message.get("text", "")

        try:
            # Check if text session is active
            if not self.client_text_sessions.get(client_id, False):
                await websocket.send_text(json.dumps({
                    "session": "text",
                    "type": "error", 
                    "error": "No active text session. Start a session with 'text_action' first."
                }))
                return
            
            session_type = agent_runner.get_text_session_type()
            logger.info(f"[WEBSOCKET] Continuing {session_type} conversation for client {client_id} with: {msg[:50]}...")

            # Cancel any existing text streaming task
            if client_id in self.client_text_tasks:
                existing_task = self.client_text_tasks[client_id]
                if not existing_task.done():
                    existing_task.cancel()
                    try:
                        await existing_task
                    except asyncio.CancelledError:
                        pass
            
            # Continue the conversation
            # Continue conversation with new message (just pass the user_query for continuing conversation)
            async_gen = await agent_runner.continue_text_conversation(msg)
            
            # Stream the response back to client in background task
            text_streaming_task = asyncio.create_task(
                self._stream_text_response_from_generator(client_id, websocket, async_gen)
            )
            self.client_text_tasks[client_id] = text_streaming_task
                
        except Exception as e:
            logger.error(f"[WEBSOCKET] Error routing text session message for client {client_id}: {e}")
            await websocket.send_text(json.dumps({
                "session": "text",
                "type": "error",
                "error": str(e)
            }))

    async def _save_audio_recording(self, client_id: str):
        """Save recorded audio to WAV file for debugging purposes"""
        import wave
        try:
            if client_id not in self.client_audio_buffers or not self.client_audio_buffers[client_id]:
                logger.debug(f"[WEBSOCKET] No audio recorded for client {client_id}, skipping WAV file creation")
                return

            # Get recorded audio chunks and timestamps
            audio_chunks = self.client_audio_buffers[client_id]
            start_time = self.client_recording_start_time.get(client_id, datetime.datetime.now())

            # Create filename with timestamp
            timestamp_str = start_time.strftime("%Y%m%d_%H%M%S")
            filename = f"audio_debug_client_{client_id[:8]}_{timestamp_str}.wav"

            # Concatenate all audio chunks
            audio_data = b''.join(audio_chunks)

            if not audio_data:
                logger.debug(f"[WEBSOCKET] Empty audio data for client {client_id}, skipping WAV file creation")
                return

            # Audio format assumptions based on Luna AI specs:
            # 24kHz sample rate, 16-bit PCM, mono
            sample_rate = 24000
            channels = 1
            sample_width = 2  # 16-bit = 2 bytes per sample

            # Write WAV file
            with wave.open(filename, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data)

            audio_duration = len(audio_data) / (sample_rate * channels * sample_width)
            logger.info(f"[WEBSOCKET] Saved {audio_duration:.1f}s of audio for client {client_id} to {filename}")
        except Exception as e:
            logger.error(f"[WEBSOCKET] Error saving audio recording for client {client_id}: {e}")

    async def _cleanup_client(self, client_id: str):
        """Clean up all sessions for a specific client"""
        try:
            # Stop voice session
            await self._handle_voice_session_stop(client_id)
            
            # Stop text session
            await self._handle_text_session_stop(client_id)

            # Stop wake word detection
            if client_id in self.client_wake_word_detectors:
                detector = self.client_wake_word_detectors[client_id]
                detector.stop()
                logger.info(f"[WEBSOCKET] Stopped wake word detector for client {client_id}")
            
            # Cancel wake word detection task
            if client_id in self.client_wake_word_tasks:
                task = self.client_wake_word_tasks[client_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del self.client_wake_word_tasks[client_id]
                logger.info(f"[WEBSOCKET] Cancelled wake word detection task for client {client_id}")
            
            # Remove client references
            if client_id in self.client_websockets:
                del self.client_websockets[client_id]
            if client_id in self.client_runners:
                del self.client_runners[client_id]
            if client_id in self.client_user_contexts:
                del self.client_user_contexts[client_id]
            if client_id in self.client_voice_sessions:
                del self.client_voice_sessions[client_id]
            if client_id in self.client_text_sessions:
                del self.client_text_sessions[client_id]
            if client_id in self.client_text_tasks:
                del self.client_text_tasks[client_id]
            if client_id in self.client_wake_word_detectors:
                del self.client_wake_word_detectors[client_id]
            
            # Remove from websocket communication util
            remove_websocket_connection(client_id)
            
            logger.info(f"[WEBSOCKET] All sessions cleaned up for client {client_id}")
            
        except Exception as e:
            logger.error(f"[WEBSOCKET] Error during cleanup for client {client_id}: {e}")



    async def start_server(self, host: str = "0.0.0.0", port: int = None):
        """Start the FastAPI server with deployment-ready defaults"""
        import openwakeword

        openwakeword.utils.download_models()

        if port is None:
            port = int(os.environ.get("PORT"))
            
        logger.info(f"[WEBSOCKET] Starting server on {host}:{port}")
        
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="info",
            log_config=None,  # Disable uvicorn's default logging
            access_log=False,  # Disable access logging
            use_colors=False
        )
        server = uvicorn.Server(config)
        await server.serve()
