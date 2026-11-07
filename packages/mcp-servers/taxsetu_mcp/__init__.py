"""The 8-server MCP mesh. `mesh(stage)` builds every server; `Client` is the in-process host used by agents/tests."""
from . import (gstn_nic, gworkspace_sync, incometax_traces, mca_labour, paytm_upi_aa, statutory_rag, tally_xml, whatsapp_voice)
from .core import Server, ToolError  # noqa: F401


class Client:
    """In-process MCP host: routes a tool/resource call to the named server, same call surface as JSON-RPC."""

    def __init__(self, servers: dict):
        self.servers = servers

    def call(self, server: str, tool: str, **args):
        return self.servers[server].call(tool, args)

    def read(self, server: str, uri: str):
        return self.servers[server].read(uri)

    def tool_names(self) -> list:
        return [t for s in self.servers.values() for t in s.tools]


def mesh(stage=None, gstn: dict | None = None, itd: dict | None = None, clock=None) -> Client:
    srv = [gstn_nic.build(stage, **(gstn or {})), tally_xml.build(), whatsapp_voice.build(*([clock] if clock else [])),
           paytm_upi_aa.build(), incometax_traces.build(stage, itd), mca_labour.build(), statutory_rag.build(),
           gworkspace_sync.build()]
    return Client({s.name.removeprefix("mcp-server-"): s for s in srv})


if __name__ == "__main__":    # python -m taxsetu_mcp <name>  -> serve one server on stdio
    import sys
    mesh().servers[sys.argv[1]].serve_stdio()
