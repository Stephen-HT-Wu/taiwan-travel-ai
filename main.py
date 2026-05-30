from agent import run_agent

if __name__ == "__main__":
    print("🗺️  台灣旅遊助理（輸入 quit 離開）")
    print("=" * 40)
    messages = []
    while True:
        user_input = input("\n你：").strip()
        if user_input.lower() in ("quit", "exit", "離開", "q"):
            print("掰掰！旅途愉快 ✈️")
            break
        if not user_input:
            continue
        run_agent(user_input, messages)
