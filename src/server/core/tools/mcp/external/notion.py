from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams

notion_mcp = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mcp.notion.com/mcp"
    ),
)