import os
import time
from dotenv import load_dotenv

# Core modern LangChain & Gemini modules
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

# Load config secrets
load_dotenv()

# Initialize the model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0.0, # 0.0 is perfect for precise evaluations and strict formatting
    max_retries=6
)

# Construct our isolated Reviewer Specialist Agent
reviewer_agent = create_agent(
    model=llm,
    tools=[], 
    name="reviewer_specialist",
    system_prompt=(
        "You are an elite Senior Project Quality Reviewer. Your job is to strictly evaluate "
        "business memos against the initial user goal. "
        "CRITICAL RULES:\n"
        "1. If the memo is highly detailed, professional, and directly covers the features requested, "
        "you MUST start your response with the word 'APPROVED'.\n"
        "2. If the memo is too brief, completely missing features, or lacks professional structure, "
        "do NOT say approved. Instead, output strict constructive feedback pointing out the errors."
    )
)

if __name__ == "__main__":
    print("=== Testing Single Component: Reviewer Specialist Agent ===")
    
    # We pass the exact text your Writer Agent just outputted
    writer_memo_to_test = """
    ### EXECUTIVE SUMMARY
    This memo outlines the strategic positioning of 'LetMePark,' our innovative smart parking platform...
    
    ### VALUE PROPOSITION
    - For Property Owners: Maxmized Revenue via machine learning dynamic pricing. Enhanced Loyalty via POS integration.
    - For End-Users: Stress-Free Experience and advanced booking.
    
    ### STRATEGIC FEATURES
    - Dynamic Pricing Engine: Uses ML algorithms to analyze real-time occupancy.
    - Integrated Retail Discounting: Connects to retail POS systems.
    - Core Operational Technologies: Uses ANPR ticketless entry, mobile booking, and live camera guidance.
    """
    
    original_user_goal = "Create a competitive market entry overview for our smart parking platform 'LetMePark'."
    
    reviewer_input = (
        f"The user wanted this goal: '{original_user_goal}'\n\n"
        f"Please evaluate if this generated draft satisfies the criteria perfectly:\n{writer_memo_to_test}"
    )
    
    print("Waiting 5 seconds to clear API timers...")
    time.sleep(5)
    print("Invoking Reviewer Agent node...")
    
    response = reviewer_agent.invoke({"messages": [("user", reviewer_input)]})
    
    print("\n=================== TEST RESULT ===================")
    print(response["messages"][-1].content)
    print("====================================================")