def create_doc(title: str, content: str) -> str:
    """Creates a Google Doc (Placeholder)."""
    return f"[MOCK] Created Google Doc '{title}' with content length {len(content)}"

def send_email(to: str, subject: str, body: str) -> str:
    """Sends an email via Gmail (Placeholder)."""
    return f"[MOCK] Sent email to {to} with subject '{subject}'"

def create_calendar_event(summary: str, start_time: str, end_time: str) -> str:
    """Creates a calendar event (Placeholder)."""
    return f"[MOCK] Created event '{summary}' from {start_time} to {end_time}"

tools = [create_doc, send_email, create_calendar_event]
