"""Server-sent events emitted while the assistant answers.

Event names (``data`` is always a JSON object):

``turn``         ``{turn_id, conversation_id, mode}``, first event of every answer
``step``         ``{id, tool, label, status, detail}``, tool progress (running/done/failed)
``sources``      ``{items: [{index, kind, title, excerpt, url}]}``, evidence used
``reasoning``    ``{text}``, streamed thinking of reasoning models
``answer``       ``{text}``, streamed answer text
``approval``     ``{id, kind, title, summary, preview, expires_at}``, proposal awaiting a decision
``suggestions``  ``{items}``, follow-up questions
``title``        ``{title}``, the conversation received a generated title
``error``        ``{message}``
``done``         ``{turn_id}``, last event
"""

from __future__ import annotations

import json
from typing import Any


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
