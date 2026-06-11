import os
import time
from dotenv import load_dotenv

# Core modern LangChain & Gemini modules
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.tools import Tool
from langchain_community.tools.tavily_search import TavilySearchResults

# 1. Load config secrets
load_dotenv()

# 2. Setup the LLM core targeting our stable free-tier model line
# max_retries keeps our requests resilient against rate limits
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0.1,
    max_retries=6
)

# 3. Create a rate-limit-safe search tool wrapper
base_search = TavilySearchResults(max_results=2)

def safe_search_wrapper(query: str):
    print(f"   └─ 🔍 Executing web search query: '{query}'...")
    time.sleep(2)  # Generates a tiny breathing space for the free tier balance
    return base_search.invoke(query)

research_tool = Tool(
    name="web_search",
    description="Search the web for up-to-date facts, pricing details, market trends, or system guidelines.",
    func=safe_search_wrapper
)

# 4. Construct our isolated Researcher Specialist Agent
research_agent = create_agent(
    model=llm,
    tools=[research_tool],
    name="research_specialist",
    system_prompt=(
        "You are a dedicated Competitive Research Specialist. Your job is to explore the web, "
        "gather fresh operational data about requested topics, and extract 3 key factual insights. "
        "Format your final output clearly with bullet points."
    )
)

# 5. Unit test just this single module
if __name__ == "__main__":
    print("=== Testing Single Component: Research Specialist Agent ===")
    
    # A localized prompt matching your smart parking hackathon concept "LetMePark"
    test_query = "Find the typical pricing models or features for smart shopping mall parking applications."
    
    print(f"Target Prompt: {test_query}\n")
    print("Waiting 10 seconds to clear any active API cooldowns...")
    time.sleep(10)
    print("Invoking Researcher Agent node...")
    
    # Run the agent using the modern standard schema array
    response = research_agent.invoke({"messages": [("user", test_query)]})
    
    print("\n=================== TEST RESULT ===================")
    print(response["messages"][-1].content)
    print("====================================================")