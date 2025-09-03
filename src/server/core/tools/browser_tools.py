#!/usr/bin/env python3
"""
Browser automation tools for Luna AI Agent
WebSocket-based communication with Electron main process
Follows Luna AI logging architecture - no direct print/logging statements
"""
import json
import os
import asyncio
import logging
import base64
from typing import AsyncGenerator, Optional

from browserbase import Browserbase
from browser_use.llm import ChatGoogle
from browser_use import Agent, BrowserProfile, BrowserSession, Controller, ActionResult
from google.genai import Client
from google.genai import types as genai_types
from google.adk.tools import ToolContext
from uuid import UUID, uuid4
from playwright.async_api import async_playwright
from ...util.websocket_communication import send_websocket_command

logger = logging.getLogger(__name__)

class ManagedBrowserSession:
    def __init__(self, cdp_url: str, browser_profile: BrowserProfile, browserbase_client=None, session_id=None, context_id=None, client_id=None):
        self.id = uuid4()
        self.cdp_url = cdp_url
        self.browser_profile = browser_profile
        self.browser_session = None
        self.auth_needed = False
        self.browserbase_client = browserbase_client
        self.browserbase_session_id = session_id
        self.auth_message_sent = False  # Flag to prevent repeated auth messages
        self.context_id = context_id
        self.client_id = client_id

    async def __aenter__(self) -> BrowserSession:
        self.browser_session = BrowserSession(
            cdp_url=self.cdp_url,
            browser_profile=self.browser_profile,
            keep_alive=True,
            highlight_elements=False,
        )
        await self.browser_session.start()
        return self.browser_session
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
    
    async def cleanup(self):
        """Clean up both browser_use session and BrowserBase session."""
        if self.browser_session:
            try:
                await self.browser_session.stop()
                logger.info(f"Browser session stopped for managed session {self.id}")
            except Exception as e:
                logger.error(f"Error stopping browser session for managed session {self.id}: {e}")
        
        # Terminate BrowserBase session
        if self.browserbase_client and self.browserbase_session_id:
            try:
                await asyncio.sleep(3)

                self.browserbase_client.sessions.update(
                    id=self.browserbase_session_id, 
                    status="REQUEST_RELEASE",
                    project_id=os.getenv("BROWSERBASE_PROJECT_ID")
                )
                logger.info(f"BrowserBase session {self.browserbase_session_id} terminated")
            except Exception as e:
                logger.error(f"Error terminating BrowserBase session {self.browserbase_session_id}: {e}")
        
        # Send context_id to client for storage
        if self.client_id and self.context_id:
            try:
                await send_websocket_command(
                    command_type="browser",
                    action="save",
                    data={"context_id": self.context_id},
                    client_id=self.client_id
                )
                logger.info(f"Context ID {self.context_id} sent to client for storage during cleanup")
            except Exception as e:
                logger.error(f"Failed to send context_id to client during cleanup: {e}")

# Global mapping to link BrowserSession instances to ManagedBrowserSession
_SESSION_MAPPING = {}

BROWSER_SESSIONS = {} # TODO: Limit concurrent sessions based on tier.

async def cleanup_all_browser_sessions():
    """Clean up all active browser sessions."""
    if not BROWSER_SESSIONS:
        logger.info("No browser sessions to clean up")
        return
    
    logger.info(f"Cleaning up {len(BROWSER_SESSIONS)} browser sessions")
    
    # Get a copy of the session IDs to avoid modifying dict during iteration
    session_ids = list(BROWSER_SESSIONS.keys())
    
    for session_id in session_ids:
        managed_session = BROWSER_SESSIONS.get(session_id)
        if managed_session:
            try:
                # Call the cleanup method directly
                await managed_session.cleanup()
                logger.info(f"Cleaned up browser session {session_id}")
            except Exception as e:
                logger.error(f"Error cleaning up browser session {session_id}: {e}")
            finally:
                # Remove from the global dict
                BROWSER_SESSIONS.pop(session_id, None)
    
    logger.info("All browser sessions cleaned up")

async def monitor_authentication_background(managed_session):
    """
    Internal authentication monitoring that runs in background.
    Returns True if authentication completed, False otherwise.
    """
    logger.info(f"Starting background authentication monitoring for session {managed_session.id}")
    genai_client = Client(vertexai=False)
    
    prompt_text = """
    Analyze this browser screenshot to determine if user authentication/login has been completed successfully.
    
    Look for indicators such as:
    - Absence of login forms, password fields, or "Sign In" buttons
    - Presence of user menus, dashboards, or personalized content
    - URL changes indicating successful login
    
    Respond with ONLY one of:
    - "AUTHENTICATED" if login appears complete
    - "NOT_AUTHENTICATED" if still on login page or authentication pending
    - "UNCLEAR" if the page state is ambiguous
    """
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(managed_session.cdp_url)
            context = browser.contexts[0]
            page = context.pages[0]
            cdp_session = await context.new_cdp_session(page)

            # Monitor while authentication is needed
            while managed_session.auth_needed:
                screenshot_data = await cdp_session.send("Page.captureScreenshot", {
                    "format": "jpeg",
                    "quality": 80,
                    "fullpage": False
                })
                
                image_part = genai_types.Part.from_bytes(
                    data=base64.b64decode(screenshot_data['data']), 
                    mime_type="image/png"
                )
                
                contents = genai_types.Content(
                    role="user",
                    parts=[image_part, genai_types.Part.from_text(text=prompt_text)]
                )
                
                response = genai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=(
                            "You are an authentication status detector. Analyze browser screenshots "
                            "to determine if a user has successfully completed login/authentication. "
                            "Be precise and only respond with the exact words specified."
                        )
                    )
                )
                
                auth_status = response.candidates[0].content.parts[0].text.strip()
                logger.info(f"AUTHENTICATION STATUS: {auth_status}")
                
                if auth_status == "AUTHENTICATED":
                    managed_session.auth_needed = False
                    managed_session.auth_message_sent = False  # Reset flag for potential future use
                    logger.info(f"Authentication completed for session {managed_session.id}")
                    return True
                
                await asyncio.sleep(2)
        
        # If we exit the while loop, auth_needed became False
        return True
        
    except Exception as e:
        logger.error(f"Background authentication monitoring failed: {str(e)}")
        if managed_session:
            managed_session.auth_needed = False
            managed_session.auth_message_sent = False  # Reset flag on error
        return False

async def start_browser_task(task: str, flash: bool, tool_context: ToolContext) -> AsyncGenerator[str, None]:
    """
    Start a browser task with authentication support and keep browser alive.

    Args:
        task: The task identifier for the browser automation.
        flash: Flash mode for the browser use agent. Should only be False if task is very complex, keep as True otherwise.
        tool_context: Tool context containing client_id for WebSocket communication.
    """
    logger.info(f"Starting browser task: {task}, flash={flash}")
    
    try:
        controller = create_browser_controller()
        logger.info("Browser controller created")
        
        session, context_id, bb = await create_context_and_session(tool_context)
        logger.info(f"Context and session created: session_id={session.id}, context_id={context_id}")
        
        browser_profile = BrowserProfile(
            keep_alive=True,
            highlight_elements=False,
        )

        managed_session = ManagedBrowserSession(
            cdp_url=session.connect_url, 
            browser_profile=browser_profile,
            browserbase_client=bb,
            session_id=session.id,
            context_id=context_id,
            client_id=tool_context.state.get("client_id")
        )

        BROWSER_SESSIONS[managed_session.id] = managed_session

        async with managed_session as browser_session:
            # Link browser_session to managed_session via global mapping
            _SESSION_MAPPING[id(browser_session)] = managed_session

            llm = ChatGoogle(model='gemini-2.5-flash')

            agent = Agent(
                task=task,
                llm=llm,
                controller=controller,
                browser_session=browser_session,
                use_thinking=not flash,  # Enable agent reasoning output
                use_vision=not flash,    # Enable vision for better context
                max_actions_per_step=10,  # Process one action at a time for clarity
                use_flash=flash
            )

            try:
                browser_task = asyncio.create_task(agent.run())
                auth_monitor_task = None  # Track authentication monitoring task
                
                while not browser_task.done():
                    # Start authentication monitoring if needed and not already running
                    if managed_session.auth_needed and not managed_session.auth_message_sent and auth_monitor_task is None:
                        yield f"Authentication required. Notify the user to manually login via the window provided."
                        managed_session.auth_message_sent = True
                        # Start authentication monitoring in background
                        auth_monitor_task = asyncio.create_task(
                            monitor_authentication_background(managed_session)
                        )
                    
                    # Check if authentication monitoring completed
                    if auth_monitor_task and auth_monitor_task.done():
                        try:
                            auth_result = await auth_monitor_task
                            if auth_result:
                                yield "Authentication completed successfully. Browser task continuing."
                            else:
                                yield "Authentication monitoring ended without completion."
                        except Exception as e:
                            yield f"Authentication monitoring failed: {str(e)}"
                        finally:
                            auth_monitor_task = None
                    
                    await asyncio.sleep(2)
                
                # Clean up auth monitoring task if still running
                if auth_monitor_task and not auth_monitor_task.done():
                    auth_monitor_task.cancel()
                    try:
                        await auth_monitor_task
                    except asyncio.CancelledError:
                        pass
                
                yield "Browser task completed successfully."

            except Exception as e:
                yield f"Browser automation failed: {str(e)}"

            finally:
                # Clean up session mapping
                if id(browser_session) in _SESSION_MAPPING:
                    del _SESSION_MAPPING[id(browser_session)]

                del BROWSER_SESSIONS[managed_session.id]
    
    except Exception as e:
        logger.error(f"Failed to start browser task: {e}")
        
        # Clean up any sessions that may have been created
        if 'managed_session' in locals() and managed_session.id in BROWSER_SESSIONS:
            try:
                await managed_session.cleanup()
                del BROWSER_SESSIONS[managed_session.id]
                logger.info(f"Cleaned up failed session {managed_session.id}")
            except Exception as cleanup_error:
                logger.error(f"Error during session cleanup: {cleanup_error}")
        
        yield f"Failed to initialize browser task: {str(e)}"


async def create_context_and_session(tool_context: ToolContext):
    """
    Create a Browserbase context and session, fetching existing context_id from client if available.
    
    Args:
        tool_context: Tool context containing client_id for WebSocket communication.
    
    Returns:
        tuple: (session, context_id)
    """
    bb = Browserbase(api_key=os.environ["BROWSERBASE_API_KEY"])
    
    context_id = None

    response = await send_websocket_command(
        command_type="browser",
        action="get",
        data={},
        client_id=tool_context.state.get("client_id")
    )

    logger.info(f"Got response: {json.dumps(response)}")
    
    if response.get("status") == "success" and response.get("data", {}).get("context_id"):
        context_id = response["data"]["context_id"]
        logger.info(f"Retrieved existing context ID: {context_id}")

    if not context_id:
        context_id = bb.contexts.create(project_id=os.environ["BROWSERBASE_PROJECT_ID"]).id

    # Create session with context and persist=True
    session = bb.sessions.create(
        project_id=os.environ["BROWSERBASE_PROJECT_ID"],
        browser_settings={
            "context": {
                "id": context_id,
                "persist": True  # Save changes back to context
            }
        }
    )
    
    # Get Live View URL
    live_view = bb.sessions.debug(session.id)
    logger.info(f"Live View URL: {live_view.debuggerFullscreenUrl}")

    await send_websocket_command(
        command_type="browser",
        action="live_url",
        data={"live_url": live_view.debuggerFullscreenUrl},
        client_id=tool_context.state.get("client_id")
    )
    logger.info(f"Live preview URL sent to client: {live_view.debuggerFullscreenUrl}")

    return session, context_id, bb

async def wait_until_auth_completed(managed_session):
    """Wait until authentication is completed (auth_needed becomes False)."""
    while managed_session.auth_needed:
        await asyncio.sleep(1)

def create_browser_controller():
    """Create a Browser-Use controller with authentication capabilities"""
    controller = Controller()
    
    @controller.action('Request user authentication for login pages.')
    async def request_user_authentication(browser_session: BrowserSession) -> ActionResult:
        """
        Custom action that requests user authentication when login is required.
        
        Args:
            browser_session: The current browser session
        """
        # Get the managed session from the global mapping
        managed_session = _SESSION_MAPPING.get(id(browser_session))
        if not managed_session:
            return ActionResult(
                extracted_content="Unable to find managed session for authentication",
                include_in_memory=True
            )
        
        managed_session.auth_needed = True

        try:
            await asyncio.wait_for(
                wait_until_auth_completed(managed_session),
                timeout=300  # 5 minute timeout
            )
            
            return ActionResult(
                extracted_content="User authentication completed successfully.",
                include_in_memory=True
            )
        except asyncio.TimeoutError:
            return ActionResult(
                extracted_content="Authentication timeout. Stop the current browser task immediately.",
                include_in_memory=True
            )
    
    return controller


browser_tools = [start_browser_task]