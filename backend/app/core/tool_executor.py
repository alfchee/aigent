"""
ToolExecutor - Ejecutor unificado de herramientas

Este módulo implementa el ejecutor centralizado de herramientas con manejo de errores,
retry automático y lógica de fallback, siguiendo las mejores prácticas del 
paper arxiv 2603.05344v1 sobre Tool Learning.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set
from langchain_core.tools import BaseTool, StructuredTool

from app.core.tool_registry import ToolRegistry, get_tool_registry

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Error específico para fallos en ejecución de herramientas."""
    
    def __init__(self, tool_name: str, message: str, is_retryable: bool = True):
        self.tool_name = tool_name
        self.is_retryable = is_retryable
        super().__init__(message)


class ToolValidationError(Exception):
    """Error específico para fallos de validación de parámetros."""
    
    def __init__(self, tool_name: str, message: str, missing_params: List[str] = None):
        self.tool_name = tool_name
        self.missing_params = missing_params or []
        super().__init__(message)


class ToolExecutor:
    """
    Ejecutor unificado de herramientas con manejo de errores y retry.
    
    Este ejecutor proporciona:
    - Validación de argumentos contra el schema de la herramienta
    - Retry automático con backoff exponencial
    - Fallback a skills equivalentes si falla un MCP
    - Logging detallado de ejecuciones
    """
    
    # Categorías que pueden tener fallback entre skill y MCP
    FALLBACK_CATEGORIES = {
        "files": ["filesystem", "filesystem_mcp", "drive", "google_drive"],
        "data": ["postgres", "database", "mysql"],
        "search": ["search", "brave", "duckduckgo"],
        "development": ["github", "code_execution"],
    }
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or get_tool_registry()
        self.logger = logging.getLogger(__name__)
        self._execution_history: List[Dict[str, Any]] = []
    
    async def execute(
        self, 
        tool_name: str, 
        args: Dict[str, Any],
        retry_count: int = 3,
        retry_delay: float = 1.0,
        enable_fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Ejecuta una herramienta con retry y manejo de errores.
        
        Args:
            tool_name: Nombre de la herramienta a ejecutar
            args: Argumentos para la herramienta
            retry_count: Número máximo de reintentos
            retry_delay: Delay base entre reintentos (segundos)
            enable_fallback: Si True, intenta fallback si falla
            
        Returns:
            Dict con:
                - success: bool
                - result: Any (resultado de la herramienta)
                - error: str (mensaje de error si falló)
                - tool_name: str
                - attempts: int (número de intentos)
        """
        # 1. Validar que la herramienta existe
        tool = await self.registry.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool {tool_name} not found",
                "tool_name": tool_name,
                "attempts": 0
            }
        
        # 2. Validar argumentos contra schema
        validation_error = self._validate_args(tool, args)
        if validation_error:
            return {
                "success": False,
                "error": validation_error,
                "tool_name": tool_name,
                "attempts": 0,
                "validation_error": True
            }
        
        # 3. Ejecutar con retry
        last_error = None
        for attempt in range(retry_count):
            try:
                self.logger.info(f"Executing tool {tool_name} (attempt {attempt + 1}/{retry_count})")
                
                result = await self._execute_tool(tool, args)
                
                # Registrar en historial
                self._record_execution(
                    tool_name=tool_name,
                    args=args,
                    success=True,
                    attempts=attempt + 1
                )
                
                return {
                    "success": True,
                    "result": result,
                    "tool_name": tool_name,
                    "attempts": attempt + 1
                }
                
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Attempt {attempt + 1}/{retry_count} failed for {tool_name}: {e}")
                
                # Actualizar disponibilidad en registry
                await self.registry.update_tool_availability(
                    tool_name,
                    is_available=False,
                    error=last_error
                )
                
                # Si hay más reintentos, esperar
                if attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # Backoff exponencial
        
        # 4. Si falló todo, intentar fallback
        if enable_fallback:
            fallback_result = await self._try_fallback(tool_name, args)
            if fallback_result:
                return fallback_result
        
        # 5. Registrar fallo final
        self._record_execution(
            tool_name=tool_name,
            args=args,
            success=False,
            attempts=retry_count,
            error=last_error
        )
        
        return {
            "success": False,
            "error": f"Max retries exceeded: {last_error}",
            "tool_name": tool_name,
            "attempts": retry_count
        }
    
    async def _execute_tool(self, tool: BaseTool, args: Dict[str, Any]) -> Any:
        """Ejecuta una herramienta, detectando si es sync o async."""
        
        # Verificar si la herramienta es una StructuredTool
        if isinstance(tool, StructuredTool):
            # Usar el método correcto según el tipo
            if hasattr(tool, 'ainvoke') and (hasattr(tool, 'is_async') and tool.is_async):
                return await tool.ainvoke(args)
            elif hasattr(tool, 'ainvoke'):
                # StructuredTool con ainvoke
                try:
                    return await tool.ainvoke(args)
                except TypeError:
                    # Si ainvoke no acepta args, usar invoke
                    return tool.invoke(args)
            else:
                return tool.invoke(args)
        
        # Para BaseTool genérico
        if asyncio.iscoroutinefunction(tool.invoke):
            return await tool.invoke(args)
        else:
            return tool.invoke(args)
    
    def _validate_args(self, tool: BaseTool, args: Dict[str, Any]) -> Optional[str]:
        """
        Valida los argumentos contra el schema de la herramienta.
        
        Args:
            tool: Herramienta a validar
            args: Argumentos a validar
            
        Returns:
            None si es válido, string con error si no es válido
        """
        # Obtener el schema de argumentos
        args_schema = None
        
        if isinstance(tool, StructuredTool):
            args_schema = tool.args_schema
        elif hasattr(tool, 'args_schema'):
            args_schema = tool.args_schema
        
        if args_schema is None:
            # No hay schema, permitir cualquier cosa
            return None
        
        # Obtener propiedades requeridas
        required: List[str] = []
        properties: Dict[str, Any] = {}
        
        try:
            if hasattr(args_schema, 'model_json_schema'):
                schema = args_schema.model_json_schema()
            elif hasattr(args_schema, 'schema'):
                schema = args_schema.schema()
            else:
                schema = args_schema if isinstance(args_schema, dict) else {}
            
            required = schema.get('required', [])
            properties = schema.get('properties', {})
            
        except Exception as e:
            self.logger.warning(f"Could not parse args_schema for {tool.name}: {e}")
            return None
        
        # Verificar parámetros requeridos
        missing = []
        for param in required:
            if param not in args or args[param] is None:
                missing.append(param)
        
        if missing:
            return f"Missing required parameter(s): {', '.join(missing)}"
        
        # Verificar tipos de parámetros (básico)
        for param_name, param_value in args.items():
            if param_name in properties:
                expected_type = properties[param_name].get('type')
                if expected_type and param_value is not None:
                    if not self._check_type(param_value, expected_type):
                        self.logger.warning(
                            f"Parameter {param_name} type mismatch: "
                            f"expected {expected_type}, got {type(param_value)}"
                        )
        
        return None
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Verifica si el valor coincide con el tipo esperado."""
        type_mapping = {
            'string': str,
            'integer': int,
            'number': (int, float),
            'boolean': bool,
            'array': list,
            'object': dict,
        }
        
        expected = type_mapping.get(expected_type)
        if expected is None:
            return True  # Desconocido, permitir
        
        return isinstance(value, expected)
    
    async def _try_fallback(
        self, 
        original_tool_name: str, 
        args: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Intenta usar una herramienta equivalente si la original falla.
        
        Args:
            original_tool_name: Nombre de la herramienta que falló
            args: Argumentos originales
            
        Returns:
            Resultado del fallback o None si no hay fallback disponible
        """
        metadata = await self.registry.get_metadata(original_tool_name)
        if not metadata:
            return None
        
        # Determinar categoría y buscar alternativas
        category = metadata.category
        source = metadata.source
        
        # Si la original era un MCP, buscar un skill equivalente
        if source == "mcp":
            # Buscar skills en la misma categoría
            skill_tools = await self.registry.get_tools_by_category(category)
            if skill_tools:
                fallback_tool = skill_tools[0]  # Usar el primero disponible
                self.logger.info(
                    f"Falling back from {original_tool_name} to {fallback_tool.name}"
                )
                
                try:
                    result = await self._execute_tool(fallback_tool, args)
                    return {
                        "success": True,
                        "result": result,
                        "tool_name": fallback_tool.name,
                        "fallback_from": original_tool_name,
                        "attempts": 1
                    }
                except Exception as e:
                    self.logger.error(f"Fallback failed: {e}")
        
        return None
    
    def _record_execution(
        self,
        tool_name: str,
        args: Dict[str, Any],
        success: bool,
        attempts: int,
        error: Optional[str] = None
    ) -> None:
        """Registra la ejecución en el historial."""
        self._execution_history.append({
            "tool_name": tool_name,
            "args": args,
            "success": success,
            "attempts": attempts,
            "error": error,
        })
        
        # Mantener solo los últimos 1000 registros
        if len(self._execution_history) > 1000:
            self._execution_history = self._execution_history[-1000:]
    
    def get_execution_history(
        self, 
        tool_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de ejecuciones.
        
        Args:
            tool_name: Filtrar por nombre de herramienta (opcional)
            limit: Número máximo de registros
            
        Returns:
            Lista de ejecuciones
        """
        history = self._execution_history
        
        if tool_name:
            history = [h for h in history if h["tool_name"] == tool_name]
        
        return history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de ejecución."""
        total = len(self._execution_history)
        successful = sum(1 for h in self._execution_history if h["success"])
        failed = total - successful
        
        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
        }


# Singleton accessor
_tool_executor_instance: Optional[ToolExecutor] = None


def get_tool_executor(registry: Optional[ToolRegistry] = None) -> ToolExecutor:
    """Obtiene la instancia singleton del ToolExecutor."""
    global _tool_executor_instance
    if _tool_executor_instance is None:
        _tool_executor_instance = ToolExecutor(registry)
    return _tool_executor_instance
