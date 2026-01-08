from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from agents.state import AgentState
from agents.tools import execute_python, web_search

# --- CONFIGURATION ---
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# --- 1. DEFINE THE AGENTS ---

def create_agent(llm, system_prompt, tools=None):
    """Helper to create an agent node with a specific persona."""
    if tools:
        llm = llm.bind_tools(tools)
        
    def agent_node(state: AgentState):
        messages = state["messages"]
        # Add the system prompt to the history temporarily for this inference
        sys_msg = SystemMessage(content=system_prompt)
        response = llm.invoke([sys_msg] + messages)
        # Update the state with the new message and the sender name
        # We explicitly set the sender to the node name so the router works
        node_name = system_prompt.split("(")[1].split(")")[0].lower() # extracts 'manager', 'coder' etc roughly
        if "Manager" in system_prompt: node_name = "manager"
        elif "Coder" in system_prompt: node_name = "coder"
        elif "Skeptic" in system_prompt: node_name = "skeptic"
        
        return {"messages": [response], "sender": node_name} 
    return agent_node

# --- PROMPTS ---

MANAGER_PROMPT = """You are the Lead Data Scientist (Manager).
1. Analyze the user's request.
2. Break it down into logical steps.
   - If the user asks for REAL-TIME info (prices, news, stocks, DATES), the step is: "Search the internet for [query]" or "Use Python to get current date".
   - If the user provides a file, the step is: "Load data".
3. Instruct the 'Coder' to execute the first step.
4. If the 'Skeptic' approves the previous work, IMMEDIATELY decide the next step. 
5. IMPORTANT: When the entire analysis is complete, you MUST respond with the word "Conclusion" or "Final Answer" followed by the summary.
"""

CODER_PROMPT = """You are the Python Developer (Coder).
1. Your job is to WRITE CODE based on the Manager's instructions.
2. Use 'web_search' tool immediately if the Manager asks for real-time information or specific data values.
3. Use 'execute_python' to run code or analyze data.
4. If the 'Skeptic' rejects your work, fix the code and try again.
5. IF SEARCH RESULTS CONFLICT: Do not keep searching. Summarize the conflict.
"""

SKEPTIC_PROMPT = """You are the Skeptical Reviewer.
1. Review the Coder's tool output.
2. CHECK FOR:
   - Logical errors (e.g., calculating mean of a name column).
   - Data Leakage.
   - Empty or confusing charts.
   - Failed searches (returns 0 results).
3. HANDLING CONFLICTS & DATES:
   - If a search returns conflicting data, **DO NOT REJECT**. APPROVE it and note the conflict.
   - **TRUST THE TOOLS:** If the Code/Search says the date is 2025, 2026, or later, **BELIEVE IT**. Do not reject it as "future date" just because your internal training data is older.
   - **Ambiguity is NOT an error.**
4. RESPONSE FORMAT:
   - If severe issues found (errors, empty results): Start with "REJECTED:" and explain why.
   - If good: Respond with "APPROVED".
""" 

# --- 2. BUILD NODES ---

manager_node = create_agent(llm, MANAGER_PROMPT)
coder_node = create_agent(llm, CODER_PROMPT, tools=[execute_python, web_search])
skeptic_node = create_agent(llm, SKEPTIC_PROMPT)
tool_node = ToolNode([execute_python, web_search])

# --- 3. ROUTING LOGIC ---

def router(state: AgentState):
    """Decides where to go after the Manager speaks."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # 1. If Manager calls a tool (rare but possible), let them
    if getattr(last_message, "tool_calls", None):
        return "tools"
    
    # 2. STOP CONDITION: If Manager says "Conclusion", we end the run.
    if "Conclusion" in last_message.content or "Final Answer" in last_message.content:
        return END
    
    # 3. Default: Manager assigns work to Coder
    return "coder"

def coder_router(state: AgentState):
    """Decides where to go after Coder speaks."""
    last_message = state["messages"][-1]
    # If Coder wrote code (tool call), execute it
    if getattr(last_message, "tool_calls", None):
        return "tools"
    # If Coder just talked, send to Skeptic for review
    return "skeptic"

def skeptic_router(state: AgentState):
    """Decides where to go after Skeptic speaks."""
    last_message = state["messages"][-1]
    content = last_message.content.upper()
    
    if "REJECTED" in content:
        return "coder" # Loop back to fix code
    elif "APPROVED" in content:
        return "manager" # Back to manager for next step
    else:
        return "manager" # Default

# --- 4. GRAPH CONSTRUCTION ---

workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("manager", manager_node)
workflow.add_node("coder", coder_node)
workflow.add_node("skeptic", skeptic_node)
workflow.add_node("tools", tool_node)

# Set Entry Point
workflow.set_entry_point("manager")

# Add Edges

# 1. Manager Logic (THE FIX IS HERE)
# Instead of hardcoding manager->coder, we use the router to check for "Conclusion"
workflow.add_conditional_edges(
    "manager",
    router,
    {
        "coder": "coder",
        "tools": "tools",
        END: END
    }
)

# 2. Coder Logic
workflow.add_conditional_edges(
    "coder",
    coder_router,
    {
        "tools": "tools",
        "skeptic": "skeptic"
    }
)

# 3. Tool Logic
workflow.add_edge("tools", "skeptic") # Tool output always goes to Skeptic for review

# 4. Skeptic Logic
workflow.add_conditional_edges(
    "skeptic",
    skeptic_router,
    {
        "coder": "coder",
        "manager": "manager"
    }
)

# Compile
app = workflow.compile()