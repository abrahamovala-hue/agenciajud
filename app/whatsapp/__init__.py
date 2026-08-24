"""Canal WhatsApp do Judith AI — entra por webhook, sai pelo ANSWER_DM."""

from app.whatsapp.channel import AnswerDmWhatsapp, attach_answer_dm_routes, handle_message
from app.whatsapp.policy import decide_output_mode, fallback_to_text
from app.whatsapp.speech import synthesize

__all__ = [
    "AnswerDmWhatsapp",
    "attach_answer_dm_routes",
    "decide_output_mode",
    "fallback_to_text",
    "handle_message",
    "synthesize",
]
