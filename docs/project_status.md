# Project Status

## Overview
Navibot is a Personal AI Agent designed for **Executive Management**. 
It aims to be an autonomous agent that strictly uses **Function Calling (Tools)** to perform actions, eliminating instability associated with headless browsers for core logic. It leverages the **Google Generative AI SDK** as its brain.

## Tech Stack

### Backend
- **Core**: Python + FastAPI
- **AI Engine**: Google Generative AI SDK
- **Automation Approach**: Strict Function Calling (Tools)
- **Browser Automation**: Playwright (only for specific controlled tasks)
- **Scheduling**: APScheduler (Cron-like jobs)
- **Persistence**: SQLite / JSON (Lightweight)

### Frontend
- **Framework**: Nuxt 3 (Vue.js)
- **UI System**: TailwindCSS + Nuxt UI (Clean Dashboard/Chat)

### Integrations & Skills
- **Google Workspace**: Gmail, Docs, Calendar
- **MCP**: Model Context Protocol support for extensions
- **Channels**: Telegram, Slack, Discord, WhatsApp
- **System**: Native Python file operations (os, shutil)

## Architecture
The project is structured as a monorepo:
- `/backend`: Python application hosting the Agent and API.
- `/frontend`: Nuxt.js web application for the dashboard and chat interface.

## Current Capabilities
### Implemented
1. **Basic Project Structure**: Monorepo with backend and frontend folders.
2. **Initial Skills**: Basic browser and scheduler modules exist (need refinement).

### Planned / In Progress
1. **Advanced Scheduling**: "N8n-style" workflow automation.
2. **Chat Interface**: For providing instructions and files to the agent.
3. **Workspace Integration**: Connection to Google Services.
4. **Channel Support**: External communication bots.
