import streamlit as st
import importlib
import sys
import os
import re
import json
from streamlit_agraph import agraph, Node, Edge, Config
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

    # 세션 상태 초기화 (get_initial_state 호출 시 프로필 로드됨)
    if "conversation_state" not in st.session_state:
        st.session_state.conversation_state = get_initial_state()

    current_state = st.session_state.conversation_state
    
    # JSON에서 list로 로드된 explained_concepts
    mastered_concepts_list = current_state.get("explained_concepts", []) 
    explanation_counts = current_state.get("explanation_count", {})

    # (수정) list의 길이로 학습 완료 개수 표시
    st.metric("🎓 학습 완료 개념", f"{len(mastered_concepts_list)} 개")

    # 설명 횟수가 2번 이상인 개념을 취약 개념으로 간주
    weak_concepts_list = [
        name for name, count in explanation_counts.items() 
        if count >= 2 and name in mastered_concepts_list
    ]
    
    st.subheader("🎯 복습 추천 개념")
    if weak_concepts_list:
        # (수정) 설명 횟수도 함께 표시
        for concept in weak_concepts_list:
            st.warning(f"- {concept} (설명 {explanation_counts.get(concept, 0)}회)")
    else:
        st.success("🎉 모든 개념을 잘 이해하고 있어요!")
        
    st.divider()
    
    if st.button("🔄 학습 기록 초기화"):
        try:
            profile_path = os.path.join("data", "user_profile.json")
            if os.path.exists(profile_path):
                os.remove(profile_path)
                st.toast("프로필 파일이 삭제되었습니다.")
        except Exception as e:
            st.error(f"프로필 파일 삭제 중 오류: {e}")
            
        st.session_state.conversation_state = get_initial_state() # 새 프로필 로드 (빈 상태)
        st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 학습 기록이 초기화되었습니다."}]
        st.rerun()

# 메인 화면
st.title("📚 수포자를 위한 AI 수학 튜터")
st.caption("개념의 선수 지식을 확인하며 차근차근 학습해요!")

# 채팅 기능 핵심 로직

# 1. 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 수학 개념에 대해 무엇이든 물어보세요."}]


# 2. 이전 대화 기록을 먼저 모두 표시
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


#학습경로 시각화

st.divider()
st.subheader("📍 학습 경로")
path_container = st.container(height=300) 

with path_container:
    # 세션 상태에서 시각화 데이터 가져오기
    current_state = st.session_state.conversation_state
    path_data = current_state.get("learning_path")
    # (수정) set이 아닌 list/tuple인지 확인 (JSON에서 로드된 상태)
    learned_concepts_iterable = current_state.get("explained_concepts", [])
    learned_concepts = set(learned_concepts_iterable) # set으로 변환
    current_goal = current_state.get("primary_goal_concept")

    if path_data and path_data.get("nodes"):
        nodes = []
        edges = []
        
        node_ids = set() # 중복 노드 방지
        
        # 1. 노드 객체 생성 및 스타일 적용
        for n in path_data.get("nodes", []):
            node_id = n.get("id")
            if node_id not in node_ids:
                node_ids.add(node_id)
                
                # 학습 상태에 따라 노드 색상 변경
                if node_id == current_goal:
                    color = "#FFD700" # 노란색 (현재 목표)
                    size = 20
                elif node_id in learned_concepts:
                    color = "#90EE90" # 연두색 (학습 완료)
                    size = 15
                else:
                    color = "#D3D3D3" # 회색 (미학습)
                    size = 15
                    
                nodes.append(Node(id=node_id, 
                                  label=n.get("label", node_id), 
                                  color=color,
                                  size=size))

        # 2. 엣지 객체 생성
        for e in path_data.get("edges", []):
            edges.append(Edge(source=e.get("source"), 
                              target=e.get("target"),
                              label=e.get("label", ""),
                              color="#D3D3D3")) # 엣지 색상

        # 3. 그래프 설정 (물리 엔진 비활성화)
        config = Config(width="100%",
                        height=280,
                        directed=True, 
                        physics=False, # (중요) 물리 효과 끄기
                        hierarchical=True, # (중요) 계층 구조로 표시
                        layout={"hierarchical": {"direction": "LR"}}, # 좌->우 방향
                        )

        agraph(nodes=nodes, edges=edges, config=config)

    else:
        st.info("개념을 질문하면 여기에 학습 경로가 표시됩니다.")