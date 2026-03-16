# Vue 3 + TypeScript + Vite

This template should help get you started developing with Vue 3 and TypeScript in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about the recommended Project Setup and IDE Support in the [Vue Docs TypeScript Guide](https://vuejs.org/guide/typescript/overview.html#project-setup).

## Sistema de diseño: layout y scroll del chat

- El canvas del chat usa altura fija de viewport con `h-[100dvh]` y `overflow-hidden`.
- El layout split-view mantiene header e input como zonas fijas (`shrink-0`).
- La zona central del chat usa `min-h-0 flex-1 overflow-hidden` para delegar scroll.
- Solo `MessageList` aplica `overflow-y-auto` para scroll vertical de mensajes.
- El sidebar aplica `min-h-0` y `overflow-y-auto` para evitar doble scrollbar global.
- La organización usa carpeta por conversación (`folder`) y agente (`agentId`) persistidos.
- El sidebar incluye filtros persistentes por carpeta y agente en localStorage.
- El compositor soporta comando `/folder <nombre>` y prefijo `@agente` por conversación.
