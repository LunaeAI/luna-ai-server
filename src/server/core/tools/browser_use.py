#!/usr/bin/env python3
"""
Browser automation tools for Luna AI Agent
WebSocket-based communication with Electron main process
Follows Luna AI logging architecture - no direct print/logging statements
"""
import os
import asyncio
import json
import base64
import tempfile
from typing import AsyncGenerator, Optional

from browser_use.llm import ChatGoogle
from browser_use import Agent, BrowserProfile, Controller, ActionResult, BrowserSession
from browser_use.browser.types import Page
from google.genai import Client
from google.genai import types as genai_types

from dotenv import load_dotenv

load_dotenv()
class AuthenticationHandler:
    def __init__(self):
        self.auth_queue = asyncio.Queue()
        self.auth_pending: bool = False
        self.current_auth_request = None
        self.monitoring_active: bool = False
        self.browser_session: BrowserSession
    
    async def complete_authentication(self):
        """Called externally when user completes authentication"""
        if self.auth_pending:
            await self.auth_queue.put("auth_complete")
            self.stop_monitoring()
    
    def stop_monitoring(self):
        self.auth_pending = False
        self.current_auth_request = None
        self.auth_queue = asyncio.Queue()
        self.monitoring_active = False
        self.browser_session = None
    
    def start_monitoring(self):
        self.monitoring_active = True

# Global authentication handler
auth_handler = AuthenticationHandler()

def create_browser_controller():
    """Create a Browser-Use controller with authentication capabilities"""
    controller = Controller()
    
    @controller.action('Request user authentication for login pages.')
    async def request_user_authentication(reason: str, page: Page, browser_session: BrowserSession) -> ActionResult:
        """
        Custom action that requests user authentication when login is required.
        
        Args:
            reason: Description of why authentication is needed
            page: Current page information
        """
        current_url = page.url
        page_title = await page.title()
        
        screenshot = await browser_session.take_screenshot()
        
        auth_request = {
            "type": "authentication_required", 
            "url": current_url,
            "title": page_title,
            "reason": reason,
            "screenshot": screenshot,
            "message": f"Please complete login at {page_title} ({current_url}) to continue automation"
        }
        
        auth_handler.auth_pending = True
        auth_handler.current_auth_request = auth_request
        
        try:
            await asyncio.wait_for(auth_handler.auth_queue.get(), timeout=300)  # 5 minute timeout
            auth_handler.auth_pending = False
            auth_handler.current_auth_request = None
            auth_handler.stop_monitoring()
            
            return ActionResult(
                extracted_content=f"User authentication completed for {current_url}",
                include_in_memory=True
            )
        except asyncio.TimeoutError:
            auth_handler.auth_pending = False
            auth_handler.current_auth_request = None
            auth_handler.stop_monitoring()
            return ActionResult(
                extracted_content=f"Authentication timeout for {current_url}",
                include_in_memory=True
            )
    
    return controller

async def monitor_authentication_completion(url: str) -> AsyncGenerator[str, None]:
    """
    Monitor browser screen for authentication completion indicators.
    
    Args:
        url: The URL where authentication is taking place
        expected_indicators: Description of what indicates successful authentication
    """
    client = Client(vertexai=False)
    
    prompt_text = f"""
    Analyze this browser screenshot to determine if user authentication/login has been completed successfully.
    
    Look for indicators such as:
    - Absence of login forms, password fields, or "Sign In" buttons
    - Presence of user menus, dashboards, or personalized content
    - URL changes indicating successful login
    
    The user was previously on a login page at: {url}
    
    Respond with ONLY one of:
    - "AUTHENTICATED" if login appears complete
    - "NOT_AUTHENTICATED" if still on login page or authentication pending
    - "UNCLEAR" if the page state is ambiguous
    """
    
    last_auth_status = None
    auth_handler.start_monitoring()
    
    try:
        while auth_handler.monitoring_active and auth_handler.auth_pending:
            try:
                screenshot = await auth_handler.browser_session.take_screenshot()
                
                screenshot_bytes = base64.b64decode(screenshot)
                
                image_part = genai_types.Part.from_bytes(
                    data=screenshot_bytes, 
                    mime_type="image/png"
                )
                
                contents = genai_types.Content(
                    role="user",
                    parts=[image_part, genai_types.Part.from_text(text=prompt_text)]
                )
                
                response = client.models.generate_content(
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
                
                if auth_status != last_auth_status:
                    last_auth_status = auth_status
                
                if auth_status == "AUTHENTICATED":
                    await auth_handler.complete_authentication()
                    yield "User has completed authentication. Thank them while the browser agent continues the original task."
                    return
                
                # Wait 5 seconds before next check (as specified)
                await asyncio.sleep(5)
                
            except Exception as e:
                yield f"Error during authentication monitoring: {str(e)}"
                await asyncio.sleep(5)  # Continue monitoring even if one check fails
        
    except Exception as e:
        yield f"Authentication monitoring failed: {str(e)}"
        auth_handler.stop_monitoring()

async def start_browser_task(task: str, flash: bool) -> AsyncGenerator[str, None]:
    """
    Start a browser task with authentication support and keep browser alive.

    Args:
        task: The task identifier for the browser automation.
        flash: Flash mode for the browser use agent. Should only be False if task is very complex, keep as True otherwise.
    """
    controller = create_browser_controller()

    browser_session = BrowserSession(
        keep_alive=True,
        headless=False,
        highlight_elements=False,
    )
    
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
        auth_handler.browser_session = agent.browser_session
        
        browser_task = asyncio.create_task(agent.run())
        
        while not browser_task.done():
            if auth_handler.auth_pending and auth_handler.current_auth_request:
                auth_request = auth_handler.current_auth_request
                yield f"AUTHENTICATION_REQUIRED: {json.dumps(auth_request)}. Begin the monitor_authentication_completion tool in the background, without letting the user know."
                
                auth_handler.start_monitoring()
                
                auth_handler.current_auth_request = None
            
            await asyncio.sleep(1)
            
            if browser_task.done():
                break
        
        await browser_task
        yield "Browser task completed successfully."

    except Exception as e:
        yield f"Browser automation failed: {str(e)}"
        
        try:
            await agent.browser_session.close()
        except:
            pass
    finally:
        auth_handler.stop_monitoring()
        auth_handler.browser_session = None

async def complete_user_authentication():
    """
    Call this function when the user has completed authentication manually.
    This allows the browser automation to resume.
    """
    await auth_handler.complete_authentication()
    return "Authentication completion signal sent"

browser_tools = [complete_user_authentication, start_browser_task, monitor_authentication_completion]