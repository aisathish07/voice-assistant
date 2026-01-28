"""
MCP Skill - Bridge to Model Context Protocol Servers
"""
import logging
import asyncio
import os
import sys
from typing import Dict, Any, List

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVERS

# Import MCP SDK
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

logger = logging.getLogger(__name__)

class MCPSkill:
    """
    Connects to local MCP servers and exposes their tools to the assistant.
    """
    
    def __init__(self):
        self.keywords = ["use", "ask", "tell"] # Generic keywords, we rely on tool names
        self.sessions = {}
        self.available_tools = {}
        
        if not HAS_MCP:
            logger.warning("mcp package not installed. Integration disabled.")
            return

        # Start servers in background
        asyncio.create_task(self._connect_servers())

    async def _connect_servers(self):
        """Connect to all configured MCP servers"""
        for name, config in MCP_SERVERS.items():
            try:
                command = config.get("command")
                args = config.get("args", [])
                env = config.get("env", None)
                
                logger.info(f"🔌 Connecting to MCP server: {name}...")
                
                server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=env
                )
                
                # We need to maintain the connection context
                # This is tricky in a class structure without an enter/exit context manager
                # For now, we'll try to establish long-running clients
                
                # NOTE: The official python SDK uses context managers 'async with'
                # which makes persistent connections hard in this class structure.
                # We will implement a per-request connection for now (slower but safer)
                # or a dedicated connection manager. 
                
                # For this v1, we will just log that we CAN connect.
                # Actual tool execution will happen on demand.
                logger.info(f"✅ MCP Server configured: {name}")
                
            except Exception as e:
                logger.error(f"❌ Failed to config {name}: {e}")

    async def handle(self, text: str, context: Dict[str, Any]) -> str:
        """
        Handle user requests by routing to MCP tools.
        For now, this is a distinct 'use [tool]' router.
        """
        if not HAS_MCP:
            return "MCP SDK is missing. Please run 'pip install mcp'."

        text = text.lower()
        
        # 1. Identify which server to use (naive routing)
        target_server = None
        for name in MCP_SERVERS:
            if name in text:
                target_server = name
                break
        
        if not target_server:
            # If we don't know which server, list them
            return f"Which tool should I use? Configured: {list(MCP_SERVERS.keys())}"

        # 2. Extract input (naive)
        # "tell desktop commander to check disk" -> "check disk"
        prompt = text.replace(f"tell {target_server}", "").replace(f"ask {target_server}", "").strip()
        
        # 3. Connect and Execute
        # Since we use context managers, we connect, execute, disconnect.
        config = MCP_SERVERS[target_server]
        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env", None)
        
        try:
            async with stdio_client(StdioServerParameters(command=command, args=args, env=env)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # List tools to find a match (or just let LLM decide tool call - complex)
                    # For v1, we will simply ask the server to 'sample' or use a generic tool if available.
                    # BUT wait, MCP is about TOOLS. The LLM needs to know the tools.
                    # This Skill implementation is a 'pass-through'. 
                    
                    tools = await session.list_tools()
                    
                    # Return tool list for now
                    tool_names = [t.name for t in tools.tools]
                    return f"Connected to {target_server}. Available tools: {', '.join(tool_names)}. (Tool execution not yet fully implemented)"

        except Exception as e:
            return f"Error talking to {target_server}: {e}"

        return "Command processed."
