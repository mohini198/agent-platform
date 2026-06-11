import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.checkpoint.redis import RedisSaver
from app_orchestrator import workflow  # Import your compiled graph structure

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.2)
REDIS_URI = "redis://localhost:6379"

print("=== Testing Redis Long-Term Context Recall ===")

with RedisSaver.from_conn_string(REDIS_URI) as checkpointer:
    # Re-compile the application structure with the memory checkpointer
    app = workflow.compile(checkpointer=checkpointer)
    
    # CRITICAL: We pass the EXACT same thread_id from our previous run
    config = {"configurable": {"thread_id": "project_run_001"}}
    
    # We don't provide a 'task' or initial inputs. We just ask a conversational follow-up question!
    follow_up_prompt = "Based on the report your agents just generated in memory, list out the specific clean energy storage companies that were mentioned."
    
    print(f"User Follow-up: '{follow_up_prompt}'")
    print("Fetching context from Docker Redis container...")
    
    # We look up the state values using the app's get_state method
    current_state = app.get_state(config)
    
    if current_state.values:
        saved_draft = current_state.values.get("current_draft")
        
        # Ask the LLM to answer using only the text saved in Redis memory
        response = llm.invoke(f"Read this document from memory:\n\n{saved_draft}\n\nQuestion: {follow_up_prompt}")
        print("\n🎯 [Agent Response pulled entirely from Redis Memory]:")
        print(response.content)
    else:
        print("❌ Error: Could not find any saved state for thread_id 'project_run_001' in Redis.")