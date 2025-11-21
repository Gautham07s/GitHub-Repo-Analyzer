import logging
from typing import TypedDict, Dict, Any, List, Optional
from langgraph.graph import StateGraph, END

# Import your existing agents
from agents.authenticator import AuthenticatorAgent
from agents.fetcher import FetcherAgent
from agents.validator import ValidatorAgent
from agents.fixer import FixerAgent
from agents.summarizer import SummarizerAgent

log = logging.getLogger(__name__)

# 1. Define the State
# This dictionary holds all data passed between agents
class RepoState(TypedDict):
    # Inputs
    repo_url: str
    github_token: Optional[str]
    ollama_model: str
    
    # Internal Data (populated by agents)
    owner: Optional[str]
    repo_name: Optional[str]
    branch: Optional[str]
    file_paths: List[str]
    file_contents: Dict[str, str]
    
    # Agent Outputs
    validations: Dict[str, Any]
    solutions: Dict[str, Any]
    summary: Dict[str, Any]
    
    # Flow Control
    status: str  # 'ok' or 'error'
    error_message: Optional[str]
    step_failed: Optional[str]

# 2. Define the Nodes (Agent wrappers)
def auth_node(state: RepoState) -> RepoState:
    """Authenticates and lists files."""
    log.info("--- Node: Authenticator ---")
    agent = AuthenticatorAgent(token=state.get("github_token"))
    
    res = agent.list_files(state["repo_url"])
    
    if res.get("status") != "ok":
        return {
            **state, 
            "status": "error", 
            "error_message": res.get("error"), 
            "step_failed": "auth"
        }
    
    return {
        **state,
        "owner": res["owner"],
        "repo_name": res["repo"],
        "branch": res["branch"],
        "file_paths": res["file_paths"],
        "status": "ok"
    }

def fetch_node(state: RepoState) -> RepoState:
    """Fetches file content."""
    log.info("--- Node: Fetcher ---")
    agent = FetcherAgent(token=state.get("github_token"))
    
    res = agent.fetch(state["owner"], state["repo_name"], state["file_paths"], state["branch"])
    
    if res.get("status") != "ok":
        return {
            **state,
            "status": "error", 
            "error_message": str(res.get("details")), 
            "step_failed": "fetch"
        }
        
    return {**state, "file_contents": res["files"], "status": "ok"}

def validate_node(state: RepoState) -> RepoState:
    """Validates code syntax and linting."""
    log.info("--- Node: Validator ---")
    agent = ValidatorAgent()
    
    res = agent.run(state["file_contents"])
    
    if res.get("status") != "ok":
         return {
            **state,
            "status": "error", 
            "error_message": "Validation failed", 
            "step_failed": "validate"
        }
        
    return {**state, "validations": res["validations"], "status": "ok"}

def fixer_node(state: RepoState) -> RepoState:
    """Generates fixes using LLM."""
    log.info("--- Node: Fixer ---")
    agent = FixerAgent(model=state["ollama_model"])
    
    res = agent.run(state["validations"], state["file_contents"])
    
    if res.get("status") != "ok":
        return {
            **state,
            "status": "error", 
            "error_message": "Fixer failed", 
            "step_failed": "fixer"
        }
        
    return {**state, "solutions": res["solutions"], "status": "ok"}

def summarizer_node(state: RepoState) -> RepoState:
    """Summarizes the report."""
    log.info("--- Node: Summarizer ---")
    agent = SummarizerAgent(model=state["ollama_model"])
    
    repo_full_name = f"{state['owner']}/{state['repo_name']}"
    res = agent.run(repo_full_name, state["branch"], state["validations"], state["solutions"])
    
    if res.get("status") != "ok":
        return {
            **state,
            "status": "error", 
            "error_message": "Summarizer failed", 
            "step_failed": "summarizer"
        }
        
    return {**state, "summary": res["summary"], "status": "ok"}

# 3. Define Conditional Logic
def check_status(state: RepoState):
    """Determines if the graph should proceed or end based on errors."""
    if state.get("status") == "error":
        return "end"
    return "continue"

# 4. Build the Graph
def build_graph():
    workflow = StateGraph(RepoState)

    # Add Nodes
    workflow.add_node("authenticator", auth_node)
    workflow.add_node("fetcher", fetch_node)
    workflow.add_node("validator", validate_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("summarizer", summarizer_node)

    # Set Entry Point
    workflow.set_entry_point("authenticator")

    # Add Edges with conditional error handling
    workflow.add_conditional_edges(
        "authenticator",
        check_status,
        {"continue": "fetcher", "end": END}
    )
    
    workflow.add_conditional_edges(
        "fetcher",
        check_status,
        {"continue": "validator", "end": END}
    )
    
    workflow.add_conditional_edges(
        "validator",
        check_status,
        {"continue": "fixer", "end": END}
    )
    
    workflow.add_conditional_edges(
        "fixer",
        check_status,
        {"continue": "summarizer", "end": END}
    )
    
    workflow.add_edge("summarizer", END)

    return workflow.compile()