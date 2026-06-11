import os
import time
from dotenv import load_dotenv

# Core modern LangChain & Gemini modules
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig

# Tool modules
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_experimental.utilities.python import PythonREPL
from langchain_core.tools import Tool

# 1. Load config
load_dotenv()

# 2. Initialize model with automatic retries for rate limits
# max_retries tells the library to handle 429 exceptions automatically!
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0.0,
    max_retries=6
)

# 3. Setup Tools
search_tool = TavilySearchResults(max_results=2)

# Wrap tool functions with a small delay so they don't fire instantly back-to-back
def delayed_search(query: str):
    time.sleep(3) # Give the API a 3-second break
    return search_tool.invoke(query)

python_repl = PythonREPL()
def delayed_calc(code: str):
    time.sleep(3) # Give the API a 3-second break
    return python_repl.run(code)

calculating_tool = Tool(
    name="python_repl",
    description="A Python shell. Use this to execute python commands or complex math operations. Input must be valid python code.",
    func=delayed_calc,
)

search_agent_tool = Tool(
    name="tavily_search_results_json",
    description="A search engine. Useful for when you need to answer questions about current events or live data.",
    func=delayed_search
)

tools = [search_agent_tool, calculating_tool]

# 4. Build the Agent graph
agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="You are an expert financial assistant. Use tools step-by-step. ALWAYS pause briefly between using tools."
)

# 5. Execute with customized execution config
if __name__ == "__main__":
    print("Launching Phase 2 Rate-Limit Protected Agent Loop...\n")
    
    query = "What is the current trading price of gold per ounce? Take that price and multiply it by 1.18 to add an 18% tax premium."
    
    # We wait 15 seconds before running to let your current quota cooldown completely!
    print("Waiting 15 seconds for your free tier quota cooldown to clear...")
    time.sleep(15)
    print("Processing query now...\n")
    
    try:
        response = agent.invoke({"messages": [("user", query)]})
        print("\n--- Agent's Final Output ---")
        print(response["messages"][-1].content)
    except Exception as e:
        print("\n--- Hit an aggressive limit, trying one final fallback approach ---")
        # If the graph wrapper gets confused by retries, we do a direct prompt query
        fallback_prompt = f"Search the web for the current price of gold per ounce and calculate it with an 18% tax premium manually."
        response = llm.invoke(fallback_prompt)
        print(response.content)