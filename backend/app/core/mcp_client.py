import asyncio
import json
import os
from typing import List, Dict, Any, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    # Fallback if mcp is not installed yet (e.g. during dev setup)
    ClientSession = Any
    StdioServerParameters = Any
    stdio_client = None

class McpManager:
    def __init__(self):
        self.active_sessions: Dict[str, ClientSession] = {} 
        self.tools_cache = [] 
        self.tool_lookup: Dict[str, tuple] = {} # prefixed_name -> (server_id, original_name) 
        
        self._server_tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_events: Dict[str, asyncio.Event] = {}

    async def load_servers(self): 
        """Lee active_mcp.json e inicia los servidores configurados.""" 
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(root, "app/settings/active_mcp.json")
        registry_path = os.path.join(root, "app/data/mcp_registry.json")
        
        if not os.path.exists(config_path): 
            return 

        try:
            with open(config_path, 'r') as f: 
                config = json.load(f)
                
            if not os.path.exists(registry_path):
                print(f"Warning: Registry not found at {registry_path}")
                return
                
            with open(registry_path, 'r') as f:
                registry = json.load(f)

            for server_id, settings in config.items(): 
                if settings.get('enabled'): 
                    # Only connect if not already connected
                    if server_id not in self.active_sessions:
                        await self.connect_server(server_id, settings, registry)
        except Exception as e:
            print(f"Error loading MCP servers: {e}")

    async def _run_server_task(self, name: str, params: StdioServerParameters, ready_event: asyncio.Event):
        """Runs the MCP client session in a dedicated task."""
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self.active_sessions[name] = session
                    ready_event.set()
                    
                    # Keep session alive until shutdown is requested
                    await self._shutdown_events[name].wait()
        except Exception as e:
            print(f"MCP Server {name} connection failed/closed: {e}")
        except BaseException:
            # Catch BaseExceptionGroup and GeneratorExit during shutdown
            # The 'RuntimeError: Attempted to exit cancel scope...' from anyio often appears here
            # when mixing asyncio.create_task with anyio context managers.
            pass
        finally:
            if not ready_event.is_set():
                ready_event.set() # Unblock waiter if failed early
            if name in self.active_sessions:
                del self.active_sessions[name]

    async def connect_server(self, server_id: str, settings: dict, registry: dict): 
        # 1. Resolver el comando desde el Registry 
        definition = registry.get(server_id) 
        
        if not definition: 
            print(f"Warning: Server definition for {server_id} not found in registry")
            return 

        # 2. Preparar argumentos y variables de entorno 
        cmd = definition['command'] 
        args = []
        for arg in definition['args']:
            # Replace placeholders like {path} or {connection_string}
            formatted_arg = arg
            params = settings.get('params', {})
            try:
                # Check if arg has formatting placeholders
                if "{" in arg and "}" in arg:
                    formatted_arg = arg.format(**params)
            except KeyError as e:
                print(f"Missing param {e} for server {server_id}")
                return
            args.append(formatted_arg)
            
        env = os.environ.copy() 
        if 'env_vars' in definition: 
            for env_var in definition['env_vars']:
                # Allow overriding via settings, or fallback to os.environ, or fail?
                # Usually env vars like TOKENS are in os.environ or settings (if secure).
                # The user plan implies they might be passed via settings/modal?
                # "Usuario ingresa el token y da Guardar -> active_mcp.json"
                # So we check settings['env_vars'] first, then os.environ
                val = settings.get('env_vars', {}).get(env_var) or os.environ.get(env_var)
                if val:
                    env[env_var] = val
                else:
                    print(f"Warning: Env var {env_var} missing for {server_id}")

        # 3. Iniciar conexión STDIO 
        if stdio_client is None:
            print("MCP library not installed.")
            return

        server_params = StdioServerParameters(command=cmd, args=args, env=env) 
        
        # Prepare synchronization primitives
        shutdown_event = asyncio.Event()
        self._shutdown_events[server_id] = shutdown_event
        ready_event = asyncio.Event()
        
        # Start background task
        task = asyncio.create_task(self._run_server_task(server_id, server_params, ready_event))
        self._server_tasks[server_id] = task
        
        # Wait for connection to be established
        await ready_event.wait()
        
        if server_id in self.active_sessions:
            print(f"✅ MCP Server conectado: {server_id}")
        else:
            print(f"❌ Falló conexión con {server_id}")

    async def get_all_tools(self) -> List[Dict[str, Any]]: 
        """Recupera herramientas de TODOS los servidores conectados.""" 
        all_tools = [] 
        self.tool_lookup.clear()
        for name, session in self.active_sessions.items(): 
            try:
                result = await session.list_tools() 
                for tool in result.tools: 
                    # Modificamos el nombre para evitar colisiones (ej: github_create_issue) 
                    prefixed_name = f"{name}_{tool.name}"
                    self.tool_lookup[prefixed_name] = (name, tool.name)
                    
                    tool_def = { 
                        "name": prefixed_name, 
                        "description": tool.description, 
                        "inputSchema": tool.inputSchema, 
                        "origin_session": session, # Guardamos ref para saber a quién llamar 
                        "original_name": tool.name 
                    } 
                    all_tools.append(tool_def) 
            except Exception as e:
                print(f"Error listing tools for {name}: {e}")
        return all_tools 

    async def call_tool(self, tool_name: str, arguments: dict): 
        """Enruta la llamada al servidor MCP correcto.""" 
        
        if tool_name in self.tool_lookup:
            server_id, real_tool_name = self.tool_lookup[tool_name]
        else:
            # Fallback (deprecated logic)
            parts = tool_name.split('_', 1)
            if len(parts) < 2:
                return "Invalid tool name format"
            server_id = parts[0]
            real_tool_name = parts[1]
        
        session = self.active_sessions.get(server_id) 
        if session: 
            try:
                result = await session.call_tool(real_tool_name, arguments)  
                # MCP result.content is a list of Content objects (TextContent, ImageContent, etc.)
                # We need to serialize it to string for the LLM
                output = []
                for content in result.content:
                    if hasattr(content, "text"):
                        output.append(content.text)
                    else:
                        output.append(str(content))
                return "\n".join(output)
            except Exception as e:
                return f"Error executing tool {tool_name}: {e}"
        return "Herramienta no encontrada."
    
    async def test_connection(self, server_id: str, settings: dict, registry: dict) -> Dict[str, Any]:
        """Prueba la conexión con un servidor MCP sin persistirla."""
        try:
            # 1. Resolver el comando desde el Registry
            definition = registry.get(server_id)
            if not definition:
                # Si no está en registry, ¿tal vez es una config custom completa?
                # Por ahora asumimos que debe estar en registry o settings trae 'command'
                if 'command' in settings:
                    definition = settings
                else:
                    return {"success": False, "message": f"Server definition for {server_id} not found in registry"}

            # 2. Preparar argumentos y variables de entorno
            cmd = definition['command']
            args = []
            
            # Merge definition args with potential overrides or format params
            def_args = definition.get('args', [])
            params = settings.get('params', {})
            
            for arg in def_args:
                formatted_arg = arg
                try:
                    if "{" in arg and "}" in arg:
                        formatted_arg = arg.format(**params)
                except KeyError as e:
                    return {"success": False, "message": f"Missing param {e} for server {server_id}"}
                args.append(formatted_arg)
            
            env = os.environ.copy()
            if 'env_vars' in definition:
                for env_var in definition['env_vars']:
                    val = settings.get('env_vars', {}).get(env_var) or os.environ.get(env_var)
                    if val:
                        env[env_var] = val
                    else:
                        # Si es prueba, tal vez fallar si falta variable
                        pass 

            # 3. Iniciar conexión STDIO temporal
            if stdio_client is None:
                return {"success": False, "message": "MCP library not installed."}

            server_params = StdioServerParameters(command=cmd, args=args, env=env)
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    # Verificar listando herramientas
                    result = await session.list_tools()
                    tool_count = len(result.tools)
                    return {
                        "success": True, 
                        "message": f"Conexión exitosa. Herramientas detectadas: {tool_count}",
                        "tools_count": tool_count
                    }
                    
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def cleanup(self):
        """Close all sessions."""
        # Signal all tasks to shutdown
        for name, event in self._shutdown_events.items():
            event.set()
        
        # Wait for tasks to finish
        if self._server_tasks:
            # Wait with timeout to avoid hanging
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._server_tasks.values(), return_exceptions=True),
                    timeout=2.0
                )
            except asyncio.TimeoutError:
                print("Warning: Timed out waiting for MCP servers to shutdown")
        
        self.active_sessions.clear()
        self._server_tasks.clear()
        self._shutdown_events.clear()
