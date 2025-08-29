# Luna AI Multi-Client Server

A Python WebSocket server running Google ADK (Agent Development Kit) that supports multiple concurrent client connections. This server can be deployed to cloud platforms and allows multiple Luna AI Electron clients to connect simultaneously.

## Features

-   **Multi-Client Support**: Handle multiple concurrent WebSocket connections
-   **Google ADK Integration**: Powered by Gemini 2.5 Flash with live preview capabilities
-   **Voice & Text Sessions**: Support for both voice and text-based AI interactions
-   **Memory System**: Persistent memory across sessions with similarity search
-   **Tool Integration**: MCP (Model Context Protocol) tool support
-   **Cloud Deployment Ready**: Environment-based configuration for easy deployment

## Architecture

The server supports multiple clients, each with their own:

-   Unique client ID (UUID-based)
-   Dedicated AgentRunner instance
-   Separate voice and text session management
-   Independent memory and tool contexts

## Local Development

### Prerequisites

-   Python 3.12+
-   Google API key for Gemini

### Setup

1. Clone the repository
2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Copy environment template:

    ```bash
    cp .env.example .env
    ```

4. Edit `.env` and add your Google API key:

    ```
    GOOGLE_API_KEY=your_google_api_key_here
    ```

5. Run the server:
    ```bash
    python -m src.server
    ```

The server will start on `http://localhost:8765` by default.

## Cloud Deployment

### Option 1: Railway.app (Recommended - Free Tier Available)

1. Connect your GitHub repository to Railway
2. Set environment variables in Railway dashboard:
    - `GOOGLE_API_KEY`: Your Google API key
    - `HOST`: `0.0.0.0` (auto-set)
    - `PORT`: Auto-assigned by Railway
3. Deploy automatically on git push

Railway will automatically detect the `railway.json` configuration.

### Option 2: Render.com (Free Tier Available)

1. Connect your GitHub repository to Render
2. Choose "Web Service"
3. Render will auto-detect the `render.yaml` configuration
4. Set environment variables:
    - `GOOGLE_API_KEY`: Your Google API key
5. Deploy

### Option 3: Docker Deployment

Build and run with Docker:

```bash
# Build the image
docker build -t luna-ai-server .

# Run the container
docker run -p 8000:8000 \
  -e GOOGLE_API_KEY=your_api_key \
  -e HOST=0.0.0.0 \
  -e PORT=8000 \
  luna-ai-server
```

### Option 4: Heroku

1. Install Heroku CLI
2. Create a new Heroku app:
    ```bash
    heroku create your-luna-ai-server
    ```
3. Set environment variables:
    ```bash
    heroku config:set GOOGLE_API_KEY=your_api_key
    ```
4. Deploy:
    ```bash
    git push heroku main
    ```

## Environment Variables

| Variable         | Description               | Default   | Required |
| ---------------- | ------------------------- | --------- | -------- |
| `HOST`           | Server host address       | `0.0.0.0` | No       |
| `PORT`           | Server port               | `8765`    | No       |
| `GOOGLE_API_KEY` | Google API key for Gemini | None      | Yes      |
| `LOG_TO_FILE`    | Enable file logging       | `false`   | No       |
| `MCP_PORTS`      | MCP server ports (JSON)   | `{}`      | No       |

## API Endpoints

-   `GET /`: Server information and status
-   `GET /health`: Health check endpoint
-   `WebSocket /ws`: Main WebSocket endpoint for client connections

## WebSocket Protocol

### Connection Flow

1. Client connects to `/ws`
2. Server responds with `client_registered` message (no client_id needed)
3. Client can start voice or text sessions
4. Multiple sessions supported per client (identified by WebSocket connection)

### Message Types

#### Client → Server (Simplified - No client_id needed)

-   `start_voice_session`: Begin voice interaction
-   `start_text_session`: Begin text interaction
-   `text_action`: Perform text processing action
-   `voice_content`: Send voice message
-   `audio`/`video`: Send media data
-   `stop_voice_session`/`stop_text_session`: End sessions

#### Server → Client (Clean responses)

-   `client_registered`: Connection confirmation
-   `voice_session_started`: Voice session ready
-   `text_session_result`: Text processing result
-   `chunk`: Streaming text response
-   `audio`: Voice response data
-   Status messages and errors

### Simplified Architecture Benefits

-   **Cleaner client code**: No need to track or send client_id
-   **Reduced complexity**: WebSocket connection inherently identifies the client
-   **Better performance**: Smaller message payloads
-   **Easier debugging**: Server-side logging still tracks client_id internally

## Multi-Client Architecture

Each client connection receives:

-   Dedicated AgentRunner instance (identified by WebSocket connection)
-   Isolated session state
-   Independent tool contexts

**Simplified Routing**: The WebSocket connection itself serves as the client identifier, eliminating the need for explicit client_id tracking on the client side.

This allows multiple Luna AI clients to connect simultaneously without interference.

## Monitoring

-   Health check: `GET /health`
-   Logs include client IDs for debugging
-   Active client count in health status

## Development Notes

-   Uses Python's native logging (no custom Node.js logging)
-   Environment-based configuration for deployment
-   Context variables for client-specific tool execution
-   Proper cleanup on client disconnect
-   **Simplified client communication**: No client_id needed in message payloads

## License

[Your License Here]
