"""mcp-server-whatsapp-voice (mock outbox). Enforces the supplier-nudge loop cap at the tool layer, so even a looping agent cannot spam."""
import time

from taxsetu_engine.recon import can_nudge

from .core import Server, ToolError

LOCALES = {"hi", "ta", "te", "mr", "gu", "kn", "bn", "en"}


def build(clock=time.time) -> Server:
    s, outbox, sent = Server("mcp-server-whatsapp-voice"), [], {}   # sent[(phone, inv_no, period)] -> [timestamps]

    @s.tool
    def send_interactive_approval_card(to: str, summary: str, buttons: list) -> dict:
        """Card with up to 3 reply buttons (WhatsApp limit). The button press is only a request; OTP gating happens in the API."""
        if not 1 <= len(buttons) <= 3:
            raise ToolError("WhatsApp interactive cards allow 1-3 buttons")
        outbox.append({"to": to, "kind": "card", "summary": summary, "buttons": buttons})
        return {"sent": True}

    @s.tool
    def dispatch_supplier_2b_nudge(supplier_phone: str, inv_no: str, bill_img_uri: str, period: str) -> dict:
        """Max 3 nudges per invoice per period with a 48h cooldown; after that the item must go to the CA exception queue."""
        ts = sent.setdefault((supplier_phone, inv_no, period), [])
        verdict = can_nudge(len(ts), (clock() - ts[-1]) / 3600 if ts else None)
        if verdict != "SEND":
            return {"sent": False, "verdict": verdict}
        ts.append(clock())
        outbox.append({"to": supplier_phone, "kind": "nudge", "inv_no": inv_no, "img": bill_img_uri})
        return {"sent": True, "verdict": "SEND", "nudge_no": len(ts)}

    @s.tool
    def push_vernacular_voice_summary(to: str, locale: str, audio_uri: str) -> dict:
        if locale not in LOCALES:
            raise ToolError(f"unsupported locale {locale}")
        outbox.append({"to": to, "kind": "voice", "locale": locale, "audio": audio_uri})
        return {"sent": True}

    @s.resource("whatsapp://thread/{phone}/history")
    def hist(phone):
        return [m for m in outbox if m["to"] == phone]
    return s
