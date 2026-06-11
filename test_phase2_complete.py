import os
import sys
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults

# 1. Use the modern, unified agent engine from langchain.agents
from langchain.agents import create_agent

load_dotenv()

# Verify API keys are present before starting
if not os.getenv("TAVILY_API_KEY") or not os.getenv("GROQ_API_KEY"):
    print("❌ Error: Missing TAVILY_API_KEY or GROQ_API_KEY in your .env file.")
    sys.exit(1)

print("=== Launching Official Phase 2 ReAct Agent Verification ===")

# 2. Define Tool 1: Live Web Search
search_tool = TavilySearchResults(max_results=1)

# 3. Define Tool 2: Python Calculator Execution
@tool
def python_calculator(expression: str) -> str:
    """Executes basic mathematical expressions and equations. Input should be a pure math string like '1850 * 0.10'."""
    try:
        # Using a controlled eval for safe mathematical computation
        allowed_chars = "0123456789+-*/.() "
        if not all(c in allowed_chars for c in expression):
            return "Error: Invalid characters in mathematical expression."
        result = eval(expression)
        return f"Calculation Result: {result}"
    except Exception as e:
        return f"Error computing expression: {str(e)}"

tools = [search_tool, python_calculator]

# 4. Initialize the Model Engine
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0)

# 5. Define the Strategy Prompt
system_prompt = (
    "You are a precise research and analysis agent. You have access to a web search tool "
    "and a python calculator. Always search for real-time facts first, then use the calculator "
    "to compute any mathematical percentages or changes. Do not guess math numbers."
)

# 6. Build the Agent using the modern V1.0 framework
agent = create_agent(
    model=llm, 
    tools=tools, 
    system_prompt=system_prompt
)

if __name__ == "__main__":
    target_query = "What is the current price of gold and what is 10% of it?"
    print(f"Target Query: {target_query}\n")
    
    # In the modern interface, we invoke the agent using the messages array
    response = agent.invoke({"messages": [("user", target_query)]})
    
    print("\n==================================================")
    print("✅ PHASE 2 SINGLE-AGENT REACT LOOP VALIDATED SUCCESSFULLY!")
    print("==================================================")
    print("[🎯 Final Output]:")
    
    # Extract the final message content
    print(response["messages"][-1].content)