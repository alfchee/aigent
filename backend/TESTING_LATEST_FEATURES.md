# Testing Latest Backend Features

## 1) Run backend tests

```bash
source backend/.venv/bin/activate
PYTHONPATH=backend pytest -q backend/tests
```

## 2) Required environment variables

### Minimum for local tests
- `OPENAI_API_KEY` only if you want real LLM calls.
- `TELEGRAM_BOT_TOKEN` only if you want Telegram integration active.
- `TELEGRAM_WEBHOOK_SECRET` only if webhook secret validation is enabled.

### OpenViking with Azure GPT-4.1-nano
Use OpenAI-compatible Azure endpoint values:

```bash
OPENVIKING_LLM_PROVIDER=openai
OPENVIKING_LLM_MODEL=gpt-4.1-nano
OPENVIKING_LLM_API_KEY=<AZURE_OPENAI_API_KEY>
OPENVIKING_LLM_BASE_URL=https://<your-resource>.openai.azure.com/openai/v1

OPENVIKING_EMBED_PROVIDER=openai
OPENVIKING_EMBED_MODEL=text-embedding-3-small
OPENVIKING_EMBED_API_KEY=<AZURE_OPENAI_API_KEY>
OPENVIKING_EMBED_BASE_URL=https://<your-resource>.openai.azure.com/openai/v1
OPENVIKING_CONFIG_FILE=/home/alfchee/Workspace/own/navibot/workspace/config/ov.conf
```

If your Azure setup uses deployment names, set `OPENVIKING_LLM_MODEL` and `OPENVIKING_EMBED_MODEL` to those deployment identifiers.

## 3) Test Telegram webhook endpoint

Start backend:

```bash
cd backend
uvicorn app.main:app --reload
```

Then send a test request:

```bash
curl -X POST "http://localhost:8000/telegram/webhook" \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: $TELEGRAM_WEBHOOK_SECRET" \
  -d '{"update_id":1}'
```

## 4) Test MarkItDown processing flow

In Telegram, send a `.txt`, `.md`, `.pdf`, or document to the bot.  
The backend will:
- download file into `workspace/sessions/<chat_id>/downloads`,
- extract text with MarkItDown,
- store extracted content in memory,
- generate a summary response.

## 5) Test backend chat persistence API

Every websocket turn now persists `user` and `assistant` messages in:
- `workspace/db/chat_messages.db`

Read paginated history:

```bash
curl "http://localhost:8000/chat/<session_id>/messages?conversationId=<conversation_id>&limit=50"
```

Read previous page (older than timestamp):

```bash
curl "http://localhost:8000/chat/<session_id>/messages?conversationId=<conversation_id>&beforeCreatedAt=<ts>&limit=50"
```
