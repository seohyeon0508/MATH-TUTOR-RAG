

# === 8. 실행 예시 ===
# === 8. 실행 예시 (대화형으로 수정) ===
if __name__ == "__main__":
    print("🤖 AI 수학 튜터에 오신 것을 환영합니다! (종료하려면 'exit' 입력)")
    
    tutor_state = None

    while True:
        # 1. 새 질문을 기다리는 상태일 때
        if not tutor_state:
            user_question = input("   > 어떤 개념이 궁금하신가요? ")
            if user_question.lower() == 'exit':
                break
            
            tutor_state = intelligent_tutor(user_question)

            # --- 🔥 여기가 수정된 부분! ---
            # intelligent_tutor 함수의 결과를 여기서 바로 처리합니다.

            if tutor_state and tutor_state.get("error"):
                print(f"🤖 튜터: {tutor_state['error']}")
                tutor_state = None # 상태 초기화
            
            # 선수 지식이 있어서 진단 질문을 생성한 경우
            elif tutor_state and tutor_state.get("waiting_for_response"):
                print(f"🤖 튜터: {tutor_state['diagnostic_question']}\n")
            
            # 선수 지식이 없어서 바로 설명을 생성한 경우
            elif tutor_state:
                print(f"🤖 튜터: {tutor_state['explanation']}")
                tutor_state = None # 상태 초기화

        # 2. 튜터의 진단 질문에 대한 답변을 기다리는 상태일 때
        else:
            student_answer = input("   > 나의 답변: ")
            if student_answer.lower() == 'exit':
                break
            
            follow_up = handle_diagnostic_response(student_answer, tutor_state)
            print(f"🤖 튜터: {follow_up['explanation']}")
            
            # 대화 턴이 끝났으므로 상태를 초기화
            tutor_state = None

    print("\n🤖 튜터를 종료합니다. 다음에 또 만나요!")
    
