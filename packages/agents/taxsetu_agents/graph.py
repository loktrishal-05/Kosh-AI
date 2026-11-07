"""Tiny state-machine runner with LangGraph's shape (named nodes, conditional edges) and a HARD step cap, so no agent can loop forever.
ponytail: swap for langgraph.StateGraph when checkpointing/streaming is needed; the node functions port over unchanged."""
END = "__end__"


class LoopCapExceeded(RuntimeError):
    pass


class Graph:
    def __init__(self, max_steps: int = 12):
        self.nodes, self.max_steps = {}, max_steps

    def node(self, name: str, then=END):
        """then: next node name, or callable(state) -> name. A node can stop the run by setting state['halt'] = True."""
        def reg(fn):
            self.nodes[name] = (fn, then)
            return fn
        return reg

    def run(self, entry: str, state: dict) -> dict:
        cur, trail = entry, []
        for _ in range(self.max_steps):
            if cur == END:
                return {**state, "trail": trail}
            fn, then = self.nodes[cur]
            trail.append(cur)
            fn(state)
            cur = END if state.get("halt") else then(state) if callable(then) else then
        raise LoopCapExceeded(f"exceeded {self.max_steps} steps: {trail}")
