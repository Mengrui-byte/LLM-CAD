import os
from dotenv import load_dotenv
from src.graph import app

# 加载环境变量 (OPENAI_API_KEY)
load_dotenv()

def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please create a .env file with OPENAI_API_KEY=sk-...")
        return

    print("=== CAD Multi-Agent System Initialized ===")
    user_input = input("请输入您想要设计的模型 (例如: 一个带手柄的马克杯): ")
    if not user_input:
        user_input = "一个带手柄的马克杯"

    initial_state = {
        "user_request": user_input,
        "iteration_count": 0,
        "messages": []
    }

    print(f"\nStart processing: {user_input}\n")
    
    try:
        for output in app.stream(initial_state):
            for key, value in output.items():
                print(f"\nFinished Node: {key}")
                if "messages" in value:
                    for msg in value["messages"]:
                        print(f"  - {msg}")
                if "inspector_feedback" in value:
                    print(f"  - Feedback: {value['inspector_feedback']}")
                    
        print("\n=== Workflow Completed ===")
        print("Check 'model.scad' for the generated code.")
        
    except Exception as e:
        print(f"\nExecution failed: {e}")

if __name__ == "__main__":
    main()
