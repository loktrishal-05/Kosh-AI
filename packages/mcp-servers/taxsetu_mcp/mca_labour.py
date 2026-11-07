"""mcp-server-mca-labour. Registered so the mesh is complete; the document generators are Phase 5 and refuse rather than fake legal text."""
from .core import Server, ToolError


def build() -> Server:
    s = Server("mcp-server-mca-labour")
    for name in ("draft_spice_plus_emoa_inc33", "draft_eaoa_inc34_with_entrenchment", "compile_labour_registers_form_a_and_b"):
        def tool(**kw):
            raise ToolError("Phase 5: not implemented yet")
        tool.__name__ = name
        s.tool(hitl=True)(tool)
    return s
