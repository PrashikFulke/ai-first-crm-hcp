import os
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

# Load environment variables (including GROQ_API_KEY and DATABASE_URL)
load_dotenv()

from agent.graph import app as agent_app

async def test_agent():
    print("--- Starting Agent Core Integration Test ---")
    
    if not os.getenv("GROQ_API_KEY"):
        print("WARNING: GROQ_API_KEY is not set in the environment.")
        return

    # Mock user input
    user_input = "Met Dr. Smith, discussed Product X efficacy, positive sentiment, shared brochure"
    print(f"Input: {user_input}\n")
    
    # Initialize state
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "form_state": {},
        "pending_updates": {},
        "validation_errors": []
    }

    try:
        # Run graph
        result = await agent_app.ainvoke(initial_state)
        
        print("--- Final Form State ---")
        print(result.get("form_state"))
        
        print("\n--- Validation Errors ---")
        print(result.get("validation_errors"))
        
        print("\n--- Tool Execution & Messages ---")
        for msg in result.get("messages", []):
            msg_type = msg.__class__.__name__
            if msg_type == "AIMessage" and msg.tool_calls:
                print(f"[Agent Intent] Routing to Tools: {msg.tool_calls}")
            elif msg_type == "ToolMessage":
                print(f"[Tool Execution Output] {msg.name}: {msg.content}")
            elif msg_type == "AIMessage":
                print(f"[Agent Response] {msg.content}")
            
    except Exception as e:
        print(f"Error during graph execution: {e}")

if __name__ == "__main__":
    asyncio.run(test_agent())
