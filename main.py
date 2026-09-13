from my_agent import root_agent

def main():
    print("歡迎使用 TheLook eCommerce 智能總管 Agent！(輸入 'exit' 或 'quit' 離開)")
    print("-" * 50)
    
    while True:
        user_input = input("\n使用者: ")
        if user_input.strip().lower() in ['exit', 'quit']:
            print("感謝使用，再見！")
            break
            
        # 將使用者的問題交給總管 Agent 處理
        # (註: 實際呼叫方式請依據 Google ADK LlmAgent 的版本 API 為準，常見為直接呼叫或 .run())
        response = root_agent(user_input)
        print(f"\nAgent: {response}")


if __name__ == "__main__":
    main()
