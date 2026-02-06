# Work Plan

## Current Focus
- [x] Initial Project Setup
- [x] Documentation
    - [x] Structure analysis
    - [x] Create project status
    - [x] Create work plan

## Roadmap
1. **Core Features**
   - [ ] Implement robust Scheduling system ("N8n-style" workflow automation)
   - [ ] Enhance Browser Skill with Playwright (controlled environment)
   - [ ] Implement System Skills (File handling via os/shutil)
   - [ ] **MCP Server Integration** (Extend capabilities via MCP)
   - [ ] **Google Workspace Integration** (Gmail, Docs, Calendar)

2. **Frontend (Nuxt 3 + Nuxt UI)**
   - [ ] Dashboard for bot status
   - [ ] Task management UI
   - [ ] Real-time logs viewer
   - [ ] Chat Interface for user interaction (context, file provision)

3. **Backend (FastAPI + Python)**
   - [ ] **Strict Function Calling** Architecture (Google Gen AI SDK)
   - [ ] Interaction Channels (Telegram, Slack, Discord, WhatsApp)
   - [ ] Persistence (SQLite/JSON)
   - [ ] Docker containerization

4. **Refining Architecture**
   - [ ] Ensure NO Headless Browser dependency for core logic (use Tools)
