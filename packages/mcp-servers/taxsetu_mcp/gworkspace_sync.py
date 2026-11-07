"""mcp-server-gworkspace-sync (mock). Calendar deadlines + Drive audit-vault archive of ALREADY-signed returns.
ponytail: in-memory; real OAuth2 Gmail/Calendar/Drive later."""
from .core import Server, ToolError


def build() -> Server:
    s, cal, vault = Server("mcp-server-gworkspace-sync"), [], {}

    @s.tool
    def sync_compliance_schedule_to_calendar(tenant_id: str, deadlines_list: list) -> dict:
        """Idempotent on (tenant, date, title)."""
        keys = {(e["tenant_id"], e["date"], e["title"]) for e in cal}
        new = [e for e in ({"tenant_id": tenant_id, **x} for x in deadlines_list) if (tenant_id, e["date"], e["title"]) not in keys]
        cal.extend(new)
        return {"added": len(new), "total": len([e for e in cal if e["tenant_id"] == tenant_id])}

    @s.tool
    def archive_signed_returns_to_drive(fy: str, month: str, files_list: list) -> dict:
        """Archives only files carrying an acknowledgement number (i.e. already filed by a human)."""
        if any(not f.get("ack_no") for f in files_list):
            raise ToolError("refusing to archive unsigned/unfiled documents")
        vault.setdefault(f"{fy}/{month}", []).extend(files_list)
        return {"archived": len(files_list)}

    @s.resource("gdrive://audit-vault/{fy}/{month}")
    def v(fy, month):
        return vault.get(f"{fy}/{month}", [])
    return s
