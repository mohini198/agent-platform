import os
import time
from dotenv import load_dotenv

# Core modern LangChain & Gemini modules
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

# Load config secrets
load_dotenv()

# Initialize the model (using temperature=0.3 for a bit more professional eloquence)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0.3,
    max_retries=6
)

# Construct our isolated Writer Specialist Agent (No tools needed, just raw synthesis)
writer_agent = create_agent(
    model=llm,
    tools=[], 
    name="writer_specialist",
    system_prompt=(
        "You are an expert Corporate Communications Writer. Your sole job is to take raw, "
        "bulleted research facts and expand them into a beautifully structured, highly executive "
        "Business Proposal Memo. Use clear headers like 'EXECUTIVE SUMMARY', 'VALUE PROPOSITION', "
        "and 'STRATEGIC FEATURES'. Keep the tone highly professional and compelling."
    )
)

if __name__ == "__main__":
    print("=== Testing Single Component: Writer Specialist Agent ===")
    
    # We pass the exact raw data our researcher just generated!
    mock_research_data = (
        "- Dynamic Pricing: Adjusts fees based on real-time mall occupancy using ML to maximize revenue.\n"
        "- Integrated Discounting: Links with mall retail POS systems to waive parking fees based on shopper spending thresholds.\n"
        "- Core Operational Features: Uses ANPR (Automatic Number Plate Recognition), mobile app advance booking, and live camera guidance."
    )
    
    user_goal = "Create a competitive market entry overview for our smart parking platform 'LetMePark'."
    
    # Combine them into the message history for the writer
    writer_input = (
        f"The user wants to: {user_goal}\n\n"
        f"Here is the raw data collected by our researcher:\n{mock_research_data}\n\n"
        f"Please transform this data into the final polished proposal memo."
    )
    
    print("Waiting 5 seconds to clear API timers...")
    time.sleep(5)
    print("Invoking Writer Agent node...")
    
    response = writer_agent.invoke({"messages": [("user", writer_input)]})
    
    print("\n=================== TEST RESULT ===================")
    print(response["messages"][-1].content)
    print("====================================================")