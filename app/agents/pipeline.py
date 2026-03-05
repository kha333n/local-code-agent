from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.services.ollama import OllamaClient
from app.services.retrieval import Retriever, build_context_pack
from app.tools.sandbox_tools import SandboxedTools


class AgentState(TypedDict, total=False):
    workspace: str | None
    local_model: str
    messages: list[dict[str, str]]
    user_query: str
    plan: str
    retrieved: list[dict[str, Any]]
    context_pack: str
    draft: str
    patch_applied: bool
    test_output: str
    final_response: str


class AgentRunner:
    def __init__(self, retriever: Retriever, ollama: OllamaClient) -> None:
        self.retriever = retriever
        self.ollama = ollama
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("plan", self.plan)
        graph.add_node("retrieve", self.retrieve)
        graph.add_node("propose_patch", self.propose_patch)
        graph.add_node("apply_patch", self.apply_patch)
        graph.add_node("run_tests", self.run_tests)
        graph.add_node("fix_loop", self.fix_loop)
        graph.add_node("summarize", self.summarize)

        graph.set_entry_point("plan")
        graph.add_edge("plan", "retrieve")
        graph.add_edge("retrieve", "propose_patch")
        graph.add_edge("propose_patch", "apply_patch")
        graph.add_edge("apply_patch", "run_tests")
        graph.add_edge("run_tests", "fix_loop")
        graph.add_edge("fix_loop", "summarize")
        graph.add_edge("summarize", END)
        return graph.compile()

    def run(
        self,
        workspace: str | None,
        messages: list[dict[str, str]],
        tools: SandboxedTools | None,
        local_model: str | None = None,
    ) -> str:
        if not workspace:
            return "Please provide project root path to enable project context."

        user_query = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_query = m.get("content", "")
                break

        state: AgentState = {
            "workspace": workspace,
            "local_model": local_model or "",
            "messages": messages,
            "user_query": user_query,
            "patch_applied": False,
            "test_output": "",
        }
        final = self.graph.invoke(state)
        return final.get("final_response", final.get("draft", ""))

    def plan(self, state: AgentState) -> AgentState:
        return {"plan": "Plan: retrieve context, generate answer, and provide safe next actions."}

    def retrieve(self, state: AgentState) -> AgentState:
        query = state.get("user_query", "")
        workspace = state.get("workspace")
        if not workspace:
            return {"retrieved": [], "context_pack": "Stateless mode: workspace context disabled."}
        chunks = self.retriever.retrieve(workspace, query)
        payloads = [c.payload for c in chunks]
        return {
            "retrieved": payloads,
            "context_pack": build_context_pack(chunks),
        }

    def propose_patch(self, state: AgentState) -> AgentState:
        context_pack = state.get("context_pack", "")
        messages = state.get("messages", [])
        system_prompt = {
            "role": "system",
            "content": (
                "You are a local coding agent. Use workspace context when relevant. "
                "If you suggest code edits, include concrete file paths and patches.\n\n"
                f"{context_pack}"
            ),
        }
        merged = [system_prompt, *messages]
        draft = self.ollama.chat(merged, model=state.get("local_model") or None)
        return {"draft": draft}

    def apply_patch(self, state: AgentState) -> AgentState:
        # Patch application is policy-gated and explicit by client tool flow.
        return {"patch_applied": False}

    def run_tests(self, state: AgentState) -> AgentState:
        return {"test_output": ""}

    def fix_loop(self, state: AgentState) -> AgentState:
        return {}

    def summarize(self, state: AgentState) -> AgentState:
        draft = state.get("draft", "")
        if not draft:
            draft = "No response generated."
        return {"final_response": draft}
