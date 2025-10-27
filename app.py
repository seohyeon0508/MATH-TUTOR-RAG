import streamlit as st
import importlib
import sys
import os
import re
import json
from langchain_neo4j import Neo4jGraph
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

DEBUG_MODE = True # True로 설정하면 상세 로그 출력

def log_debug(message: str):
    """디버그 모드가 활성화된 경우에만 메시지를 출력합니다."""
    if DEBUG_MODE:
        print(f"🐛 DEBUG: {message}")

scripts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
if scripts_path not in sys.path:
    sys.path.append(scripts_path)

try:
    tutor_module = importlib.import_module("06_tutor_rag")
    process_turn = tutor_module.process_turn
    get_initial_state = tutor_module.get_initial_state
except ImportError as e:
    st.error(f"튜터 로직 스크립트(06_tutor_rag.py)를 로드하는 데 실패했습니다: {e}")
    st.stop()

# 페이지 기본 설정
st.set_page_config(
    page_title="AI 수학 튜터", page_icon="📚",
    layout="wide", initial_sidebar_state="expanded"
)

# 사이드바
with st.sidebar:
    st.title("📊 나의 학습 현황")
    
    if "conversation_state" not in st.session_state:
        st.session_state.conversation_state = get_initial_state()

    current_state = st.session_state.conversation_state
    mastered_concepts_set = current_state.get("explained_concepts", set())
    explanation_counts = current_state.get("explanation_count", {})
    
    st.metric("🎓 학습 완료 개념", f"{len(mastered_concepts_set)} 개")
    
    weak_concepts_list = [name for name, count in explanation_counts.items() if count >= 2]
    
    st.subheader("🎯 복습 추천 개념")
    if weak_concepts_list:
        for concept in weak_concepts_list:
            st.warning(f"- {concept} (설명 {explanation_counts.get(concept, 0)}회)")
    else:
        st.success("🎉 모든 개념을 잘 이해하고 있어요!")
        
    st.divider()
    
    if st.button("🔄 학습 기록 초기화"):
        st.session_state.conversation_state = get_initial_state()
        st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 학습 기록이 초기화되었습니다."}]
        st.rerun()

# 메인 화면
st.title("📚 수포자를 위한 AI 수학 튜터")
st.caption("개념의 선수 지식을 확인하며 차근차근 학습해요!")

# 채팅 기능 핵심 로직

# 1. 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 수학 개념에 대해 무엇이든 물어보세요."}]


# 2. (핵심) 이전 대화 기록을 먼저 모두 표시
for message in st.session_state.messages:
    avatar = "🧑‍🎓" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])


# 3. pending_input 또는 새 사용자 입력 확인
pending_input = st.session_state.conversation_state.get("pending_input")
user_input = st.chat_input("수학 개념을 입력하세요...")

# 4. 둘 중 하나라도 존재하면 로직 실행
if pending_input or user_input:
    
    input_to_process = ""
    run_logic = False 
    
    if pending_input:
        input_to_process = pending_input
        log_debug(f"Processing pending input: {input_to_process}")
        st.session_state.conversation_state.pop("pending_input")
        run_logic = True
        
    elif user_input:
        input_to_process = user_input
        st.session_state.messages.append({"role": "user", "content": user_input})
        run_logic = True
        
    # 5. AI 튜터 응답 생성 (공통 로직)
    if run_logic:
        with st.chat_message("assistant", avatar="🤖"):
            message_placeholder = st.empty()
            full_response_content = ""
            new_state = get_initial_state()

            try:
                current_state = st.session_state.conversation_state
                log_debug(f"Calling master function: process_turn (Input: '{input_to_process}')")
                
                result_data = process_turn(input_to_process, current_state)
                
                explanation_stream = result_data.get("explanation_stream")
                response_text = result_data.get("response_text")
                new_state = result_data.get("new_state", get_initial_state())

                # 스트리밍 또는 텍스트 출력
                if explanation_stream:
                    # 스트림이 있으면 write_stream으로 출력
                    full_response_content = message_placeholder.write_stream(explanation_stream)
                elif response_text:
                    # 텍스트 응답(진단 질문, 오류 등)은 markdown으로 출력
                    full_response_content = response_text
                    message_placeholder.markdown(full_response_content)
                else:
                    full_response_content = "오류: 튜터가 응답을 생성하지 못했습니다."
                    message_placeholder.error(full_response_content)

                st.session_state.conversation_state = new_state

            except Exception as e:
                full_response_content = f"죄송합니다, 앱 처리 중 예상치 못한 오류가 발생했습니다: {e}"
                log_debug(f"Error during response generation: {e}")
                message_placeholder.error(full_response_content)
                st.session_state.conversation_state = get_initial_state()

        # AI 응답(최종 텍스트)을 기록에 추가
        if full_response_content:
             st.session_state.messages.append({"role": "assistant", "content": full_response_content})

    # 6. rerun 
    st.rerun()

st.divider()
st.subheader("📍 학습 경로")
path_container = st.container()
with path_container:
    st.info("개념을 질문하면 여기에 학습 경로가 표시됩니다.")