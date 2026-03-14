# Arquitectura de Seguridad de Capas Profundas para Navibot

Este documento detalla la propuesta de arquitectura de seguridad para la gestión de Skills en Navibot, con el objetivo de mitigar riesgos asociados a la ejecución de código externo y proteger la integridad del sistema y los datos del usuario.

## 1. El Riesgo: Anatomía del Malware en Skills

En el contexto actual (2026), el malware para LLMs ha evolucionado hacia ataques sofisticados. Los vectores de ataque principales identificados son:

*   **Log-To-Leak**: Skills maliciosos que "envenenan" logs o la memoria de contexto para exfiltrar información sensible (claves API, datos personales) durante procesos de resumen o auditoría.
*   **Inyección Indirecta de Prompt**: Descarga de contenido con instrucciones ocultas (en metadatos o esteganografía) que alteran el comportamiento del agente durante la ejecución de una tarea.
*   **Envenenamiento de Herramientas**: Ataques a la cadena de suministro donde un Skill legítimo es comprometido para incluir dependencias maliciosas.

## 2. Implementación Segura: "El Fortín de Navi"

Para mitigar estos riesgos, se propone una arquitectura basada en cinco pilares de defensa para la importación y ejecución de Skills:

### A. Manifiesto de Capacidades Estrictas (Least Privilege)
Cada Skill debe incluir un archivo `MANIFEST.json` declarando explícitamente sus capacidades requeridas.

*   **Mecanismo**: Si un Skill intenta realizar acciones no declaradas (ej. acceso a red o sistema de archivos), el sistema lo bloqueará automáticamente.
*   **Ejemplo**: Un Skill de "Cálculo Matemático" no debería tener acceso a red ni filesystem.

### B. Escaneo Estático de Seguridad (Skill-Scanner)
Antes de incorporar un Skill, este debe pasar por un análisis estático de seguridad (integrando herramientas como SkillFortify o Semgrep).

*   **Detección**:
    *   Patrones de exfiltración de datos (URLs sospechosas).
    *   Llamadas a funciones peligrosas (`eval()`, `exec()`, `os.system()`).
    *   Código ofuscado.

### C. Ejecución en Sandbox Aislado
Los Skills no se ejecutarán en el entorno principal del agente.

*   **Aislamiento**: Ejecución en entornos "Zero-Trust" (contenedores WebAssembly o sandbox de Python restringido).
*   **Puente Controlado**: Navibot actúa como único intermediario para el paso de datos. El Skill no tiene acceso directo a variables internas ni a la memoria de largo plazo (ChromaDB/Qdrant) salvo lo explícitamente proporcionado.

### D. Verificación de Firma y Cadena de Suministro
Se requiere firma digital válida para todos los Skills.

*   **Skills de Terceros**: Firma coincidente con desarrolladores de confianza.
*   **Skills Locales**: Auto-firmados con una clave local del servidor.

### E. Monitoreo de Comportamiento con "Shadow LLM"
Para tareas críticas, se implementará una segunda instancia de LLM ("Guardián").

*   **Función**: Vigilar las llamadas a herramientas en tiempo real.
*   **Acción**: Si detecta incoherencia entre la instrucción original y la acción del Skill (ej. enviar email en lugar de resumir), detiene la ejecución y solicita confirmación manual.

## 3. Recomendación Técnica de Implementación

1.  Crear directorio `/secure_skills`.
2.  Desarrollar un script "Aduana" en Python que analice los archivos depositados en este directorio contra las reglas de seguridad (Manifiesto, Escaneo, Firma).
3.  Solo integrar el Skill a `available_tools` si pasa todas las validaciones.
