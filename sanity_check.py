import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables from the .env file
load_dotenv()

# Initialize the modern Google Generative AI model line
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)

print("Sending request to Google Generative AI...")
try:
    response = llm.invoke("Hello! Confirm that you are up and running by saying 'System fully operational'.")
    print("\n--- Response ---")
    print(response.content)
except Exception as e:
    print("\n--- Error ---")
    print(e)