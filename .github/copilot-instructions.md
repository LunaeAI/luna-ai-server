# Luna AI - GitHub Copilot Instructions

## Project Overview

Luna AI is an Electron-based multimodal AI assistant that combines Google's ADK (Agent Development Kit) with real-time audio/video streaming capabilities. The agent can perform UI automation, screen capture, persistent memory management, and integrates with external services via MCP (Model Context Protocol) servers.

## Architecture Components

### Core Technology Stack

- **Frontend**: Electron + React/TypeScript with TailwindCSS
- **Backend Agent**: Python with Google ADK + FastAPI WebSocket server
- **Build System**: Webpack + Electron Forge
- **AI Models**: Gemini 2.5 Flash with live preview capabilities
- **Voice Detection**: Porcupine wake word detection ("LUNA")
- **Memory System**: SQLite-based persistent memory with similarity search

### Critical Architecture Pattern

### Service Architecture

Luna's architecture is split into two main components:

#### SERVER (Python Backend)

The Python server handles agent processing, a proxy server to connect to client-side running MCPs, and WebSocket streaming to facilitate server-client real-time communication:

```
├── agent/                     # Core Python ADK agent system
│   ├── core/                 # Agent foundation components
│   │   ├── agent.py          # Agent creation and lifecycle (async pattern)
│   │   ├── tools/            # Agent capability modules
│   │   │   ├── util.py       # Core utility tools coordination
│   │   │   ├── memory_tools.py     # SQLite-based persistent memory
│   │   │   ├── workspace_tools.py  # File system and workspace operations
│   │   │   ├── reminder_tools.py   # Reminder and scheduling functionality
│   │   │   ├── browser.py      # Browser automation and control
│   │   │   └── callbacks/          # Tool execution logging and callbacks
│   │   └── prompts/          # System prompts and agent instructions
│   ├── runner/               # ADK session management
│   │   ├── websocket_server.py     # FastAPI WebSocket server (class-based)
│   │   ├── agent_runner.py          # ADK event processing & session lifecycle
│   │   └── __init__.py              # Runner package exports
│   ├── util/                 # Shared utilities and helpers
│   └── __main__.py           # Entry point script (absolute imports)
├── mcp/                      # Model Context Protocol servers
│   ├── google/               # Google Workspace MCP server
│   │   ├── mcp_server.py    # FastMCP-based Google API integration
│   │   ├── get_credentials.py # OAuth2 authentication flow
│   │   ├── requirements.txt  # Python dependencies
│   │   └── GOOGLE_CLIENT_SECRETS.json # OAuth client configuration
│   └── mcp.json             # MCP server configuration
└── dist/                     # Compiled executables (PyInstaller)
    └── luna-streaming-server.exe # Standalone Python server executable
```

#### CLIENT (Electron Frontend)

The Electron client provides the user interface and manages communication with the Python server:

```
├── main/                     # Electron main process
│   ├── main.js              # Application entry point and lifecycle
│   ├── services/            # Main process services
│   │   ├── agent/           # Agent-related services
│   │   │   ├── mcp-manager-service.js     # MCP server lifecycle management
│   │   │   └── streaming-server-service.js # Python server process management
│   │   ├── events-service.js              # IPC event handling
│   │   ├── overlay/          # UI automation services
│   │   └── user/            # User data services
│   ├── tray/                # System tray integration
│   ├── windows/             # Window management
│   └── utils/               # Shared utilities
├── renderer/                # Electron renderer processes
│   ├── main/                # Main application window
│   │   ├── components/      # React components
│   │   ├── hooks/           # React hooks (useKeywordDetection, useConnection)
│   │   ├── services/        # Client-side services
│   │   └── pages/           # Application pages
│   ├── orb/                 # Voice interaction window
│   │   ├── services/        # StreamingService (audio/video/WebSocket). THIS IS VERY IMPORTANT: It serves as the main hub for the client's connection with the remote server.
│   │   └── components/      # Orb-specific UI components
│   └── overlay/             # Text-based overlay window
│       └── services/        # Simplified StreamingService
└── preload/                 # Electron preload scripts
    └── preload.js           # Context bridge for IPC communication
```

__**This codebase is the SERVER.**__

### Key Communication Flows

1. **Wake Word → Agent Session**:

    ```
    Porcupine detects "LUNA" → useKeywordDetection.tsx → useConnection.tsx →
    StreamingService → WebSocket → websocket_server.py → agent_runner.py → get_agent_async() → ADK Session
    ```

2. **Screen Sharing Integration**:

    ```
    Electron desktopCapturer → StreamingService → Base64 frames (1fps) →
    WebSocket → websocket_server.py → ADK Live Request Queue
    ```

3. **MCP Tool Execution**:

    ```
    Agent Request → util.py → MCPManagerService → HTTP proxy → mcp_server.py → Google API → Response
    ```

4. **Memory Persistence**:
    ```
    Agent Tools → util.py memory functions → MemoryDatabase → SQLite storage → Similarity search with embeddings
    ```

### Key Communication Flows

1. **Wake Word → Agent Session**:

    ```
    Porcupine detects "LUNA" → useKeywordDetection.tsx → useConnection.tsx →
    StreamingService → WebSocket → websocket_server.py → agent_runner.py → get_agent_async() → ADK Session
    ```

2. **Screen Sharing Integration**:

    ```
    Electron desktopCapturer → StreamingService → Base64 frames (1fps) →
    WebSocket → websocket_server.py → ADK Live Request Queue
    ```

3. **Memory Persistence**:
    ```
    Agent Tools → util.py memory functions → MemoryDatabase → SQLite storage →
    Similarity search with embeddings for context retrieval
    ```

## Development Patterns

### Python Dependencies Management

```bash
# Essential setup commands
npm run install-python-deps    # Installs Google ADK + FastAPI
npm run check-python-deps     # Validates Python environment
npm run setup-streaming       # Complete streaming setup
```

### MCP Tool Development

**All MCP tools must support async initialization:**

```python
# tools/mcp/your_mcp.py
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, StdioConnectionParams

your_mcp = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command='npx',
            args=[
                "-y",
                "@modelcontextprotocol/server-filesystem",
                "/absolute/path/to/target/directory",  # Use absolute paths
            ],
            cwd="/absolute/path/to/target/directory",  # Set working directory
        ),
    )
)
```

### Environment-Aware Path Resolution

```javascript
// Pattern used throughout codebase
getServerScriptPath() {
    if (!app.isPackaged) {
        return path.join(process.cwd(), "src", "main", "services", "agent", "websocket_server.py");
    } else {
        return path.join(__dirname, "websocket_server.py");  // Webpack bundled
    }
}
```

## Your Behavior

### Error Handling Pattern

You should NEVER implement any fallback mechanisms, and try-catch blocks should ONLY be used for non-deterministic cases, such as return values from an LLM or network connections.

### Debugging

You should ALWAYS pinpoint the root cause of the issue and only implement fixes if you are certain that is what is causing the issue. If you are not certain about what could be causing the issue at hand, do NOT implement fixes directly in the code; instead, elaborate via text and note that they are just possible causes and not the surefire root cause.

### Comments, Documentation, and Code Readability

You should NEVER generate documentation files unless explicitly specified, and comments should be kept to a minimum, only at key points. Be as concise as possible.

All methods, in Python and JavaScript/TypeScript, should have proper docstrings and headers.

### Planning

ALWAYS plan out tasks before executing them, using the SequentialThink tool.

### Libraries

When working with external libraries and frameworks, ALWAYS consult the official documentation via Context7 for guidance on usage, best practices, and troubleshooting, prior to implementation. This applies to your thinking/planning steps as well.

## Required Scripts Order

1. `npm install` - Node.js dependencies
2. `npm run install-python-deps` - Python/ADK setup
3. `npm start` - Development mode (spawns Python server automatically)

### Production Packaging

- **Webpack** bundles Python files into `.webpack/main/`
- **Electron Forge** packages for distribution
- Python server is packaged into standalone executable using PyInstaller

### Key File Dependencies

- `streaming-server-service.js` manages Python server process lifecycle
- `StreamingService.ts` manages communication over Websocket with the Python server
- `events-service.js` manages communication between renderer and main process within Electron

## Common Gotchas

1. **Never use `root_agent` in WebSocket server** - only `await get_agent_async()`
2. **Python import handling** All paths should be RELATIVE, with the exception of `__main__.py` which serves as the entry script to start the server. This file MUST have absolute imports instead.
3. **Video frame throttling** - WebSocket server limits to 5fps to prevent queue buildup

## Testing Integration Points

- WebSocket health check: `http://localhost:8765/health`
- Audio pipeline: Verify `AudioWorkletStreaming` initialization

## Memory System Architecture

**Persistent SQLite memory with similarity search capabilities:**

```python
# Memory tools pattern in util.py
def search_memory(query: str):
    """Search through persistent memories using similarity matching"""
    memories = memory_db.search_similar_memories(query, min_confidence=0.3)

def save_memory(text: str):
    """Save important information for future conversations"""
    memory_id = memory_db.add_memory(memory=text, confidence=0.5)
```

**Memory database handles:**

- User preferences and context retention
- Tool execution logging via callbacks
- Automatic memory reinforcement/weakening based on usage
- Semantic search with embeddings for relevant context retrieval

## Frontend Hook Patterns

**Key React hooks for agent integration:**

```typescript
// useKeywordDetection.tsx - Porcupine wake word detection
const { keywordDetection, isListening } = useKeywordDetection(accessKey);

// useConnection.tsx - WebSocket streaming state management
const { connectionState, startListening, stopListening } = useConnection();

// StreamingService.ts - Unified audio/video streaming
class StreamingService {
    async startStreaming() {
        /* Audio + Video initialization */
    }
    private handleServerMessage(data: string) {
        /* ADK event processing */
    }
}
```

**Audio pipeline uses AudioWorklet pattern:**

- RecorderProcessor: Converts Float32 → Int16 PCM for agent input
- PlayerProcessor: Queues and plays agent audio responses
- 24kHz sample rate, real-time processing with mute/volume controls
