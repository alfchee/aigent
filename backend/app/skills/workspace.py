def create_doc(title: str, content: str) -> str:
    """Creates a Google Doc (Placeholder)."""
    return f"[MOCK] Created Google Doc '{title}' with content length {len(content)}"

def send_email(to: str, subject: str, body: str) -> str:
    """Sends an email via Gmail (Placeholder)."""
    return f"[MOCK] Sent email to {to} with subject '{subject}'"

tools = [create_doc, send_email]
