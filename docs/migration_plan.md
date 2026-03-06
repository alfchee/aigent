# Plan Maestro de Migración: De Script Lineal a Arquitectura de Agente Modular

Este documento detalla la hoja de ruta para transformar `navibot` de una arquitectura basada en scripts lineales y bucles `while` a una arquitectura de agentes modular, extensible y escalable, utilizando **LangGraph** y un sistema de **Skills (Habilidades)** dinámico.

## Objetivo
Pasar de un "Script Lineal" a una Arquitectura de Agente Modular y Extensible (inspirada en LangGraph, ZeroClaw y patrones de alta escala).

## 🏗️ Fase 1: Reestructuración de Proyecto (Arquitectura de "Skills")

El objetivo de esta fase es desacoplar el código y establecer una base modular donde las capacidades del agente sean "plugins" independientes.

### 1.1 Estructura de Directorios
Moveremos la lógica de herramientas a un directorio `skills/` más formalizado.

- **Directorio `skills/`**: Cada archivo (`google_calendar.py`, `meta_social.py`, `browser.py`) será un módulo independiente.
- **Estandarización**: Cada módulo debe exportar sus herramientas de una manera consistente.

### 1.2 Decoradores de Tool
Utilizaremos el decorador `@tool` de **LangChain** para definir las herramientas. Esto permite:
- **Autodescripción**: Los metadatos de la herramienta (nombre, descripción, esquema de argumentos) se generan automáticamente a partir de la firma de la función y su docstring.
- **Facilidad de uso**: Simplifica la integración con los LLMs.

### 1.3 Cargador Dinámico (Skill Loader)
Implementaremos un sistema que escanea la carpeta `skills/` y registra las herramientas automáticamente al iniciar el agente.
- **Escaneo**: Detectar módulos en la carpeta `skills/`.
- **Registro**: Importar dinámicamente y registrar las funciones decoradas con `@tool` en el registro de herramientas del agente.
- **Ventaja**: Añadir una nueva habilidad solo requerirá crear un nuevo archivo en la carpeta, sin modificar el código del núcleo del agente.

## 🧠 Fase 2: Implementación de LangGraph (El Orquestador)

Aquí es donde resolvemos problemas de rendimiento, control de flujo y mantenibilidad del bucle de ejecución.

### 2.1 Definición del Grafo (`StateGraph`)
Reemplazaremos el bucle `while` personalizado (`ReActLoop`) con un `StateGraph` de LangGraph.
- **Nodos**: Representan unidades de trabajo (agentes, herramientas, lógica de decisión).
- **Aristas (Edges)**: Definen el flujo de control entre nodos.
- **Estado (State)**: Un objeto compartido que mantiene el contexto de la conversación y el estado de la ejecución.

### 2.2 Modelo Supervisor (Orquestador)
Configuraremos un nodo principal que actúe como el **Planner/Supervisor**.
- **Rol**: Decidir qué trabajador (Worker) o herramienta invocar basándose en la entrada del usuario y el estado actual.
- **Lógica**: Utilizará el LLM para enrutar la ejecución al nodo apropiado.

### 2.3 Workers Especializados
Crearemos nodos específicos para tareas complejas que operen de forma aislada.
- **Ejemplo**: Un nodo para navegación web pesada (usando `browser-use` o similar).
- **Funcionamiento**: Reciben una subtarea, la ejecutan y reportan el resultado al estado global.
- **Aislamiento**: Permite manejar errores y reintentos de forma granular sin afectar al flujo principal.

## Próximos Pasos Inmediatos
1.  Instalar dependencias necesarias (`langchain`, `langgraph`).
2.  Crear la estructura de directorios para la Fase 1.
3.  Implementar el `SkillLoader` y migrar una herramienta piloto (ej. Calendar).
