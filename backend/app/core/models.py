from pydantic import BaseModel
from typing import Literal, Optional


class SupervisorDecision(BaseModel):
    action: Literal["respond", "delegate", "use_tool"]
    delegate_to: Optional[str] = None   # role_id when action == "delegate"
    response: Optional[str] = None      # direct reply when action == "respond"
    reasoning: Optional[str] = None     # chain-of-thought, never forwarded to user
