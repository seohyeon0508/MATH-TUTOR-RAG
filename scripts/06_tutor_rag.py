#디버깅용
DEBUG_MODE = True # True로 설정하면 상세 로그 출력

def log_debug(message: str):
    """디버그 모드가 활성화된 경우에만 메시지를 출력합니다."""
    if DEBUG_MODE:
        print(f"🐛 DEBUG: {message}")

import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_neo4j import Neo4jGraph
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from utils.student_profile import load_profile, save_profile

load_dotenv()

NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USER = os.getenv('NEO4J_USER')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

#LLM, graphDB 초기화
llm = ChatOpenAI(model='gpt-4o-mini', temperature=0.3)
graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USER, password=NEO4J_PASSWORD)


#1. 사용자 질문에서 핵심 개념 추출
def extract_concept(user_question: str) -> str:
    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 중학교 수학 질문 분석 전문가입니다.
질문에서 학생이 궁금해하는 '핵심 수학 개념'을 추출하세요.
반드시 개념 이름만 반환하고, 다른 말은 절대 하지 마세요.

규칙:
1. 개념을 *정확히* 추출해야 합니다. (예: '각뿔대'를 '각뿔'로 추출하면 안 됩니다.)
2. 질문이 개념 그 자체인 경우, 해당 개념을 그대로 반환하세요.
3. 두 개념의 '차이'나 '비교'를 묻는 경우, 'A와 B' 형식으로 두 개념을 모두 반환하세요.
4. **(신규) '넓이', '부피', '구하는 법' 등 속성이나 방법을 묻는 경우, 이를 포함하여 추출하세요.**

예시:
질문: "일차방정식이 뭐야?" → 일차방정식
질문: "계수를 어떻게 구해?" → 계수 구하는 법
질문: "정비례와 반비례 차이가 뭐야?" → 정비례와 반비례
질문: "함수랑 방정식이랑 뭐가 달라?" → 함수와 방정식
질문: "각뿔대가 뭐야?" → 각뿔대
질문: "미적분이 뭐야?" → 미적분
질문: **"각뿔의 부피는 뭐야?" → 각뿔의 부피**
질문: **"원기둥 넓이 어떻게 구해?" → 원기둥 넓이 구하는 법**

개념을 찾을 수 없으면 "개념없음"이라고만 출력하세요.
"""),
        ("user", "{question}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    concept = chain.invoke({"question": user_question}).strip()
    return concept


# 2. 선수 개념 찾기 (그래프 탐색)
def get_prerequisites(concept_name: str, depth: int = 2) -> list:
    """개념의 선수 지식을 depth 단계만큼 찾기"""
    query = f"""
    MATCH path = (prereq:CoreConcept)-[:IS_PREREQUISITE_OF*1..{depth}]->(target:CoreConcept {{name: $concept}})
    WITH prereq, length(path) AS dist
    RETURN DISTINCT prereq.name AS name, prereq.definition AS definition, dist
    ORDER BY dist
    """
    
    try:
        results = graph.query(query, params={"concept": concept_name})
        return [{"name": r["name"], "definition": r["definition"], "depth": r["dist"]} 
                for r in results]
    except Exception as e:
        print(f"⚠️ 그래프 탐색 오류: {e}")
        return []

# 시각화를 위한 경로 탐색 (신규)
def get_path_for_visualization(concept_name: str) -> dict:
    """
    시각화를 위해 특정 개념의 로컬 학습 경로(선수/후속)를 조회합니다.
    (streamlit-agraph 형식에 맞는 노드와 엣지 반환)
    """
    query = """
    MATCH (target:CoreConcept {name: $concept})
    // 1. 선수 개념 (2단계 뒤까지)
    OPTIONAL MATCH path_prereq = (prereq:CoreConcept)-[:IS_PREREQUISITE_OF*1..2]->(target)
    // 2. 후속 개념 (1단계 앞까지)
    OPTIONAL MATCH path_dep = (target)-[:IS_PREREQUISITE_OF*1..1]->(dependent:CoreConcept)
    
    // 모든 노드와 관계 수집
    WITH target, 
         collect(nodes(path_prereq)) + collect(nodes(path_dep)) AS node_lists,
         collect(relationships(path_prereq)) + collect(relationships(path_dep)) AS rel_lists
    
    // 노드 리스트를 풀어서 유니크하게 만들기
    UNWIND node_lists AS node_list
    UNWIND node_list AS n
    WITH target, collect(DISTINCT n) AS all_nodes, rel_lists
    
    // 관계 리스트를 풀어서 유니크하게 만들기
    UNWIND rel_lists AS rel_list
    UNWIND rel_list AS r
    WITH all_nodes + target AS final_nodes_list, collect(DISTINCT r) AS final_rels
    
    // 최종 노드/엣지 포맷팅
    WITH [n IN final_nodes_list | {id: n.name, label: n.name}] AS nodes,
         [r IN final_rels | {source: startNode(r).name, target: endNode(r).name, label: '선수개념'}] AS edges
         
    RETURN nodes, edges
    """
    try:
        results = graph.query(query, params={"concept": concept_name})
        if results and results[0]["nodes"]:
            log_debug(f"'{concept_name}'의 시각화 경로 조회 성공")
            return {
                "nodes": results[0]["nodes"],
                "edges": results[0]["edges"]
            }
    except Exception as e:
        print(f"⚠️ 시각화 경로 탐색 오류: {e}")
    
    return {"nodes": [], "edges": []}

# 진단 질문 생성
def generate_diagnostic_question(target_concept: str, prerequisites: list):
    """선수 개념을 자연스럽게 확인하는 질문 생성 (스트림 반환)"""
    if not prerequisites:
        return None
    
    # 가장 가까운 선수 개념 (depth=1)만 사용
    immediate_prereqs = [p for p in prerequisites if p["depth"] == 1]
    if not immediate_prereqs:
        return None
    
    prereq_info = "\n".join([f"- {p['name']}: {p['definition']}" for p in immediate_prereqs])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 따뜻하고 친절한 수학 선생님입니다.
학생이 '{target_concept}'을 물어봤을 때, 이 개념을 이해하기 위해 먼저 알아야 할 선수 지식을 자연스럽게 확인하고 싶습니다.

규칙:
1. 학생의 기분을 상하게 하지 말고, 격려하는 톤으로 질문하세요
2. "혹시 기억나시나요?", "먼저 확인해볼까요?" 같은 부드러운 표현 사용
3. 선수 개념 1~2개만 언급 (너무 많으면 부담)
4. 질문은 한 문장으로 간결하게

예시:
"좋은 질문이에요! 일차방정식을 제대로 이해하려면 '방정식'과 '일차식' 개념부터 확인해보면 좋은데, 혹시 이 개념들은 기억나시나요?"
"""),
        ("user", """목표 개념: {target_concept}
선수 개념들:
{prereq_info}

위 선수 개념을 확인하는 자연스러운 질문을 생성하세요.""")
    ])
    
    chain = prompt | llm | StrOutputParser()
    return chain.stream({
        "target_concept": target_concept,
        "prereq_info": prereq_info
    })

# 4. 이해도 판단
def assess_understanding(user_response: str, prereq_names: list) -> dict:
    """학생 답변을 보고 각 선수 개념별 이해 여부 판단"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 학생의 이해도를 평가하는 전문가입니다.
학생이 여러 개념에 대해 답변했을 때, **각 개념별로** 이해 여부를 판단하세요.

판단 기준:
- 명확한 긍정 (알아요, 이해해요, 응, 네, 그래, 맞아 등) → true
- 명확한 부정 (몰라요, 모르겠어요, 아니요, 아니, 기억 안나 등) → false
- 애매한 표현 / 언급 없음 / 위 긍정/부정에 해당 안 됨 → null

**중요**: 학생이 "아니", "응" 이라고만 답해도 각각 false/true로 명확히 판단해야 합니다!

**예시**:
"A는 알아요, B는 모르겠어요" → {{"A": true, "B": false}}
"A가 뭐였더라" → {{"A": false, (다른 개념): null}}
"응" → (모든 언급된 개념): true
"아니" → (모든 언급된 개념): false

출력은 반드시 JSON만 출력하세요:
{{"개념1": false, "개념2": true, "개념3": null}}
"""),
        ("user", """선수 개념들: {prereq_names}
학생 답변: {response}

각 개념별 이해 여부를 JSON으로 반환하세요.""")
    ])

    chain = prompt | llm | StrOutputParser()
    result_str = chain.invoke({
        "prereq_names": prereq_names,
        "response": user_response
    }).strip()

    try:
        understanding_map = json.loads(result_str)
        for name in prereq_names:
            if name not in understanding_map:
                understanding_map[name] = None
        return understanding_map
    except Exception as e:
        print(f"⚠️ JSON 파싱 오류: {e}")
        print(f"   LLM 응답: {result_str}")
        return {name: None for name in prereq_names}

# 5. 그래프에서 개념 정보 (정의, 관련 예시) 가져오기
def retrieve_concept_from_graph(concept_name: str) -> dict:
    core_query = """
    MATCH (c:CoreConcept {name: $name}) 
    RETURN c.name AS name, c.definition AS definition
    """
    core_result = graph.query(core_query, params={"name": concept_name})
    
    if not core_result:
        return None
    
    example_query = """
    MATCH (concept:Concept)-[:IS_EXAMPLE_OF]->(core:CoreConcept {name: $name})
    RETURN concept.definition AS example
    LIMIT 3
    """
    examples = graph.query(example_query, params={"name": concept_name})
    
    return {
        "name": core_result[0]["name"],
        "definition": core_result[0]["definition"],
        "examples": [ex["example"] for ex in examples] if examples else []
    }
    

# 6. 맞춤 설명 생성 (stream모드)
def generate_explanation(concept_info: dict, count: int = 0):
    """그래프 데이터 기반 쉬운 설명 생성 (스트림 반환)"""
    concept_name = concept_info["name"]
    definition = concept_info["definition"]
    examples = concept_info.get("examples", [])
    
    examples_text = "\n".join([f"- {ex}" for ex in examples]) if examples else "예시 없음"
    
    system_message = """당신은 중학생 눈높이에 맞춰 설명하는 수학 선생님입니다.

규칙:
1. 정의를 쉽게 풀어서 설명
2. 구체적인 예시 포함 (숫자 예시)
3. 3-4문장으로 간결하게
4. 격려하는 말로 마무리

예시:
"계수는 문자 앞에 붙는 숫자를 말해요. 예를 들어 3x에서 3이 계수예요. 
사과 3개처럼 '몇 개'를 나타내는 숫자라고 생각하면 쉬워요. 
이제 이해되셨나요?"
"""
    user_message_template = """개념: {concept_name}
정의: {definition}

관련 예시:
{examples}

위 내용을 바탕으로 쉬운 설명을 생성하세요."""

    if count > 0:
        system_message = f"""당신은 매우 인내심이 많은 중학교 수학 선생님입니다.
학생이 이전에 '{concept_name}' 개념에 대한 설명을 들었지만, 여전히 이해하지 못했습니다.

**반드시 이전과 다른 방식**으로 설명해야 합니다.
- **새롭고 더 쉬운 예시**나 **다른 비유**를 사용하세요.
- 절대 이전에 했던 말(예: "{definition}")을 그대로 반복하지 마세요.
- 3-4문장으로 간결하지만, 이해하기 쉽게 설명하세요."""
        
        user_message_template = """개념: {concept_name}
정의: {definition}
관련 예시: {examples}

위 내용을 바탕으로 **새롭고 완전히 다른 방식의 설명**을 생성하세요."""

    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_message_template)
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    return chain.stream({
        "concept_name": concept_info["name"],
        "definition": concept_info["definition"],
        "examples": concept_info.get("examples", [])
    })

# 6-1. 일반 설명 생성 함수 (Fallback용, 스트리밍)
def generate_general_explanation(concept_name: str):
    """LLM의 일반 지식을 사용하여 개념을 설명합니다 (스트림 반환)"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""당신은 중학생 눈높이에 맞춰 수학 개념을 설명하는 친절한 선생님입니다.
학생이 '{concept_name}'에 대해 질문했지만, 이 개념은 당신의 전문 지식 그래프에 아직 없습니다.

당신의 일반 지식을 바탕으로 '{concept_name}' 개념을 설명해주세요.

규칙:
1. 중학생이 이해하기 쉽게 설명하세요.
2. 예시를 포함하면 좋습니다.
3. 3-5 문장으로 간결하게 설명하세요.
4. **매우 중요:** 설명 시작 부분에 **"(이 설명은 제 지식 그래프에 기반한 것이 아니라 일반적인 내용이에요.)"** 라는 면책 조항(disclaimer)을 반드시 포함하세요.
"""),
        ("user", f"'{concept_name}' 개념을 설명해주세요.")
    ])
    
    chain = prompt | llm | StrOutputParser()
    explanation = chain.stream({}) 
    log_debug(f"'{concept_name}'에 대한 일반 설명 생성 완료.")
    return explanation

# 6-2. 문제 생성 함수 (수정)
def generate_problem(concept_name: str, explanation_count: int) -> dict:
    """
    LLM을 사용하여 개념에 대한 문제, 정답, 핵심 선수 개념을 생성합니다.
    (수정) 학생에게 보낼 스트림과, 정답/핵심개념 데이터를 분리하여 딕셔너리로 반환합니다.
    """
    
    # (신규) 문제/정답/핵심개념을 JSON으로 생성하는 체인
    # (신규) 설명 횟수에 따라 프롬프트에 추가할 문맥 생성
    if explanation_count > 0:
        history_context = f"학생이 이 개념({concept_name})에 대한 문제를 이미 풀어본 적이 있습니다. **반드시 이전과 다른 새로운 문제**를 출제하세요."
    else:
        history_context = f"학생이 이 개념({concept_name})을 방금 학습했습니다."
        
    problem_gen_prompt = ChatPromptTemplate.from_messages([
        ("system", f"""당신은 JSON 응답을 생성하는 수학 선생님입니다.
{history_context}
'{concept_name}' 개념을 활용하는 간단한 단답형 문제 1개를 만들어주세요.

[규칙]
1. 반드시 'problem', 'answer', 'key_concept'라는 영어 키(key) 3개를 모두 포함해야 합니다.
2. 절대 응답을 ` ```json ... ``` ` (마크다운)으로 감싸지 마세요.
3. "problem" 값에는 줄바꿈이 필요하면 반드시 \\n 문자를 사용하세요.
4. **(수정) "key_concept"에는 이 문제를 푸는 데 필요한 '{concept_name}'의 *가장 중요한 선수 개념* 1가지를 적으세요.** (예: '이항', '밑면의 넓이', '피타고라스 정리'). 만약 마땅한 선수 개념이 없으면 "none"이라고 적으세요.

[JSON 형식]
{{{{
  "problem": "...",
  "answer": "...",
  "key_concept": "..."
}}}}

[JSON 예시 1: 일차방정식 문제]
{{{{
  "problem": "... 2x + 3 = 11 ...",
  "answer": "4",
  "key_concept": "이항"
}}}}

[JSON 예시 2: 각뿔 부피 문제]
{{{{
  "problem": "... 각뿔의 부피는 얼마인가요?",
  "answer": "120cm³",
  "key_concept": "밑면의 넓이"
}}}}
"""),
        # (수정) user 메시지는 간단하게
        ("user", f"'{concept_name}'에 대한 문제를 JSON 형식으로 1개 출제해주세요.")
    ])
    chain = problem_gen_prompt | llm
    
    try:
        # (수정) invoke 시 변수를 전달
        response_content = chain.invoke({
            "concept_name": concept_name,
            "history_context": history_context
        }).content
        log_debug(f"문제 생성 JSON 응답: {response_content}")
        
        # (신규) LLM 응답이 JSON 형식이 아닐 수 있으므로 파싱 시도
        data = json.loads(response_content)
        
        problem_text = data.get("problem", "오류: 문제를 생성하지 못했습니다.")
        problem_answer = data.get("answer", "none")
        problem_key_concept = data.get("key_concept", "none")
        
        # (신규) 학생에게 보낼 problem_text만 스트림으로 변환
        problem_stream = iter([problem_text])
        
        return {
            "problem_stream": problem_stream,
            "problem_data": {
                "answer": problem_answer,
                "key_concept": problem_key_concept
            }
        }
        
    except Exception as e:
        print(f"⚠️ 문제 생성 JSON 파싱 오류: {e}")
        # (신규) 오류 발생 시 안전한 반환
        return {
            "problem_stream": iter(["죄송합니다, 문제 생성 중 오류가 발생했어요."]),
            "problem_data": None
        }

# 6-3. 잡담 처리
def handle_chitchat(user_input: str):
    """LLM을 사용하여 간단한 잡담 처리 (스트림 반환)"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""당신은 '수학 튜터' 챗봇입니다. 학생이 수학과 관련 없는 간단한 대화를 시도합니다.
짧고 간결하게 '튜터'로서 응답하고, 다시 수학 질문을 하도록 유도하세요.
        
예시:
- 학생: 너는 누구야? / 튜터: 저는 AI 수학 튜터입니다. 🤖 궁금한 수학 개념을 물어보세요!
- 학생: 오늘 날씨 어때? / 튜터: 날씨는 잘 모르지만, 수학 개념은 뭐든지 물어보세요! 😊
- 학생: 고마워 / 튜터: 천만에요! 더 궁금한 점이 있나요?
"""),
        ("user", user_input)
    ])
    
    chain = prompt | llm | StrOutputParser()
    response = chain.stream({}) 
    log_debug("잡담 처리 완료.")
    return response

# (handle_chitchat 함수 정의 다음)

# === 6-3b. 문제 풀이 피드백 생성 (신규) ===
def handle_solve_problem(user_answer: str, problem_data: dict):
    """
    학생의 답을 채점하고 '진단형 피드백'을 생성합니다. (스트림 반환)
    """
    answer = problem_data.get("answer", "none")
    key_concept = problem_data.get("key_concept", "none")
    
    log_debug(f"채점 시작: 학생 답={user_answer}, 정답={answer}, 핵심개념={key_concept}")

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""당신은 학생의 답을 채점하는 친절하고 격려하는 수학 선생님입니다.
학생이 방금 수학 문제를 풀었습니다. 학생의 답이 정답과 일치하는지 판단하고, '진단형 피드백'을 제공하세요.

[문제 정보]
- 정답: "{answer}"
- 핵심 개념: "{key_concept}" (이 문제를 푸는 데 필요했던 선수 개념)

[피드백 규칙]
1.  **정답일 경우 (학생의 답이 "{answer}"와 일치하거나, "x= {answer}" 등 의미상 같을 경우):**
    - "정답입니다! 🥳"라고 칭찬해주세요.
    - 이 문제를 푸는 데 사용된 **"{key_concept}"** 개념을 잘 활용했다고 1~2문장으로 격려해주세요.
    - (예: "정답입니다! 🥳 '+3'을 넘기는 '{key_concept}' 개념을 정확히 사용하셨네요. 역시 개념을 아니까 문제가 풀리죠?")

2.  **오답일 경우 (...):**
    - **"아쉽네요, 정답은 '{answer}'였어요. 😅"**라고 **정답을 명확히 알려주세요.**
    - 이 문제를 풀려면 **"{key_concept}"** 개념이 필요했다고 1~2문장으로 힌트를 주세요.
    - "이 개념을 다시 공부해보는 것도 좋아요."라고 제안한 뒤, "더 궁금한 점이 있나요?"라고 물어보세요.
    - (예: "아쉽네요, 정답은 '4'였어요. 😅 이 문제를 풀려면 '+3'을 반대편으로 넘기는 '{key_concept}' 개념이 필요했어요. 이 개념을 다시 공부해보는 것도 좋아요. 더 궁금한 점이 있나요?")
    
피드백은 2-4문장으로 간결하게, 스트림으로 반환하세요.
"""),
        ("user", f"학생의 답: {user_answer}")
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.stream({})


# 6-4. master router 
def call_master_router(user_input: str, current_state: dict) -> tuple[str, str]: # (수정) 반환 타입을 튜플로 명시
    """
    사용자 입력과 현재 상태를 보고, 어떤 작업으로 분류할지 결정하는 '교통 정리' LLM.
    항상 (task, topic) 2개의 값을 튜플로 반환
    """
    # 튜터 흐름에 깊이 관여된 상태인지 확인
    mode = current_state.get("mode", "IDLE")
    
    if mode == "WAITING_PROBLEM_ANSWER":
        log_debug("라우터: 문제 답변 대기 중이므로 'solve_problem'으로 강제 분류")
        return "solve_problem", "none"
    
    if mode in ["WAITING_DIAGNOSTIC", "WAITING_CONTINUATION"]:
        log_debug("라우터: 튜터 흐름(진단/연속)이 진행 중이므로 'tutor_flow'로 강제 분류")
        return "tutor_flow", "none" # (수정) 2개 값 반환

    # (참고) 큐가 비어있어도 POST_EXPLANATION 상태일 수 있음
    queue_status = "비어있음" if not current_state.get("queue") else "설명 대기 중"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""당신은 학생의 요청을 분류하는 '교통 정리' 담당자입니다.
학생의 입력과 현재 대화 상태를 보고, 이 요청을 어떤 부서로 보내야 할지 결정하세요.

[부서 목록]
1.  greeting: 학생이 단순한 인사나 안부를 묻습니다. (예: "안녕", "안녕하세용", "ㅎㅇ")
2.  ask_problem: 학생이 개념에 대한 '문제'를 풀어보길 원합니다. (예: "문제 내줘", "퀴즈 풀어볼래", "일차식 문제 풀어볼게요")
3.  tutor_flow: 학생이 수학 '개념'을 질문하거나, 방금 끝난 개념 설명에 대해 재설명/추가 질문을 합니다. (가장 일반적인 경우)
    (예: "일차방정식이 뭐야?", "방금 설명한 거 이해 안돼", "다른 예시 없어?", "x가 뭔데?", "뭐라는거야", "무슨 말이야?")
4.  chitchat: 수학과 관련 없는 일반적인 대화 또는 감사 표현입니다. (예: "너는 누구야?", "고마워", "수고했어")
5.  solve_problem: 학생이 방금 출제된 문제의 답을 말합니다. (예: "3", "정답 4", "x=4", "3 아니야?")

[상황별 특별 규칙]
1. 만약 튜터가 방금 "문제"를 냈다면 (예: "답을 입력해주세요."), 학생의 숫자("3"), 정답 확인("3 아니야?"), 풀이 과정("x=4") 등은 'chitchat'이나 'greeting'이 아니라, 'solve_problem'이라는 새 부서로 보내야 합니다.

[현재 상태]
- mode: {mode}
- 큐: {queue_status}
- 마지막 설명 개념: {current_state.get("last_explained_concept", "없음")}
학생의 "문제 내줘"와 "다른 예시"를 명확히 구분해야 합니다.
- "문제 내줘" -> ask_problem
- "일차식 문제 내줘" -> ask_problem
- "다른 예시" -> tutor_flow (재설명 요청임)

반드시 부서 이름만 JSON 형식으로 출력하세요.
- `ask_problem`의 경우, 학생이 특정 개념을 언급했다면 "topic"도 추출하세요.
(예: "일차방정식이 뭐야" -> {{{{"task": "tutor_flow", "topic": "일차방정식"}}}})
(예: "3" -> {{{{"task": "solve_problem", "topic": "none"}}}})
(예: "일차식 문제 내줘" -> {{{{"task": "ask_problem", "topic": "일차식"}}}})
(예: "문제 내줘" -> {{{{"task": "ask_problem", "topic": "none"}}}})
{{{{"task": "...", "topic": "..."}}}}
"""),
        ("user", "학생 입력: {input}")
    ])

    chain = prompt | llm | StrOutputParser()
    result_str = chain.invoke({
        "input": user_input
    }).strip()

    try:
        data = json.loads(result_str)
        task = data.get("task", "tutor_flow")
        topic = data.get("topic", "none") # (수정) topic 추출
        
        # IDLE 상태인데 "개념없음" 오류가 날 만한 입력은 chitchat으로 유도
        if task == "tutor_flow" and mode == "IDLE":
            concept = extract_concept(user_input)
            if concept == "개념없음":
                # "개념없음"일 때만 짧은 입력을 greeting/chitchat으로 변경
                if len(user_input.split()) < 4 and len(user_input) < 15:
                    log_debug("라우터: 'tutor_flow'였으나 '개념없음'이 예상되어 'greeting'으로 변경")
                    return "greeting", "none" # (수정) 2개 값 반환
                else:
                    log_debug("라우터: 'tutor_flow'였으나 '개념없음'이 예상되어 'chitchat'으로 변경")
                    return "chitchat", "none" # (수정) 2개 값 반환
            
            # 개념이 있으면(else) task와 topic을 그대로 반환
            log_debug(f"라우터: 'tutor_flow' (IDLE)로 분류, topic: {topic}")
            return task, topic 
            
        log_debug(f"라우터: '{task}' (Non-IDLE)로 분류, topic: {topic}")
        return task, topic # IDLE이 아닌 경우 (원래 2개 값 반환하던 곳)
    
    except Exception as e:
        print(f"⚠️ 마스터 라우터 JSON 파싱 오류: {e}")
        return "tutor_flow", "none" # 2개 값 반환

# 6-5. LLM 의도 분류기 (tutor_flow 내부에서만 사용됨) 
def classify_continuation_intent(user_response: str, next_concept: str = None, question_type: str = "shall_i_explain", last_explained_concept: str = "none") -> dict:
    """
    (tutor_flow 전용) 학생의 답변 의도를 LLM을 통해 분류
    """
    if question_type == 'do_you_know':
        tutor_question_context = f"튜터가 방금 '{next_concept}'(은)는 알고 계신지 물어봤습니다."
        intent_list_intro = "학생의 답변을 분석하여 다음 의도 중 하나로 분류하세요:"
        intent_list = f"""
1.  "continue": '{next_concept}' 설명을 듣길 원함.
    - **매우 중요:** "네", "응", "**웅**", "맞아요" 등 **단 한 단어로 된 긍정 답변**은 **절대로** 다른 의도로 분류하지 말고 **무조건 "continue"**로 분류해야 합니다.
    - 설명을 직접 요청하는 경우 (예: "설명해줘", "알려줘", "그게 뭔데?")
2.  "skip": '{next_concept}' 설명을 건너뛰길 원함 (이미 안다고 답함). (예: "알아요", "괜찮아요", "됐어")
3.  "re-explain": **방금 설명한 개념({last_explained_concept})**에 대한 재설명/추가 설명 요청.
    - (예: "아직 이해안돼", "잘 모르겠어", "뭐더라", "방금 그게 무슨 말이야?", "모르겠어")
    - (예: "아니 {last_explained_concept}(이)가 이해 안돼", "아니 {last_explained_concept}(을)를 모르겠다고")
4.  "new_question": '{next_concept}'과 무관한 새 질문.
5.  "unclear": 위 어디에도 해당하지 않는 불명확한 답변. (예: "아니", "응?", "음...")
"""
    elif question_type == 'shall_i_explain':
        tutor_question_context = f"튜터가 방금 '{next_concept}'(을)를 설명해줄지 물어봤습니다."
        intent_list_intro = "학생의 답변을 분석하여 다음 의도 중 하나로 분류하세요:"
        intent_list = f"""
1.  "continue": '{next_concept}' 설명을 듣길 원함.
    - **매우 중요:** "네", "응", "**웅**", "맞아요" 등 **단 한 단어로 된 긍정 답변**은 **절대로** 다른 의도로 분류하지 말고 **무조건 "continue"**로 분류해야 합니다.
    - 설명을 직접 요청하는 경우 (예: "설명해줘", "알려줘", "그게 뭔데?")
2.  "skip": '{next_concept}' 설명을 건너뛰길 원함 (이미 안다고 답함). (예: "알아요", "괜찮아요", "됐어")
3.  "re-explain": **방금 설명한 개념({last_explained_concept})**에 대한 재설명/추가 설명 요청.
    - (예: "아직 이해안돼", "잘 모르겠어", "뭐더라", "방금 그게 무슨 말이야?", "모르겠어")
    - (예: "아니 {last_explained_concept}(이)가 이해 안돼", "아니 {last_explained_concept}(을)를 모르겠다고")
4.  "new_question": '{next_concept}'과 무관한 새 질문.
5.  "unclear": 위 어디에도 해당하지 않는 불명확한 답변. (예: "아니", "응?", "음...")
"""
    else: # post_explanation (이 부분은 라우터가 처리함. 수정 요)
        tutor_question_context = "튜터가 방금 개념 설명을 마치고 '더 궁금한 것이 있나요?'라고 물었습니다."
        intent_list_intro = "학생의 답변을 분석하여 다음 의도 중 하나로 분류하세요:"
        intent_list = """
1.  "re-explain": 방금 설명들은 개념에 대한 재설명/추가 설명 요청 (예: "아직 이해안돼", "다른 예시 없어?", "좀 더 설명해줘").
2.  "new_question": 새로운 수학 질문 (문제가 아닌 개념 질문).
3.  "acknowledged": 설명을 잘 들었다는 단순 긍정/감사 표현 (예: "네", "웅", "알겠습니다", "고마워요").
4.  "unclear": 의도가 불명확하거나 수학과 관련 없는 대화.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""당신은 학생의 답변 의도를 매우 정확하게 분석하는 전문가입니다.
{tutor_question_context}

{intent_list_intro}
{intent_list}

**부가적인 질문(clarification_question):**
- 학생이 주된 의도와 **별개로**, 추가적으로 질문하는 내용입니다. 없으면 null입니다.
- (예: "웅 근데 그거랑 좌표평면이랑 뭔상관이지" -> "순서쌍과 좌표평면의 연관성에 대한 질문")

**추가 정보 (topic):**
- 주된 의도가 "re-explain" 또는 "new_question"일 경우, 관련된 수학 개념(topic)을 추출하세요.
- **매우 중요:** "re-explain" 의도일 때, 학생이 **"A"를 설명해달라고 명시적으로 말했다면 (예: "A가 뭐더라", "A 다시 설명해줘", "A가 이해 안돼", "A가 뭔데")**,
  튜터가 방금 B에 대해 물어봤더라도 **반드시 "A"를 topic으로 추출해야 합니다.** (예: 튜터가 '일차식'을 물었어도 학생이 '방정식 설명해줘'라고 하면 topic은 '방정식'입니다.)
- 학생이 명시적으로 topic을 말하지 않았다면 (예: "다시 설명해줘", "이해 안돼"),
  "re-explain" 의도일 경우 topic을 **"{last_explained_concept}"**(으)로 설정하세요.
  "new_question" 의도일 경우 "none"을 반환하세요.
  
**출력 형식 (반드시 JSON):**
{{{{"primary_intent": "...", "clarification_question": "...", "topic": "..."}}}}
(clarification_question이 없으면 null, topic은 해당 없을 시 "none")
"""),
        ("user", "학생 답변: {response}")
    ])

    chain = prompt | llm | StrOutputParser()
    result_str = chain.invoke({
        "response": user_response,
        "last_explained_concept": last_explained_concept # 이 줄 추가
    }).strip()

    try:
        data = json.loads(result_str)
        data.setdefault("primary_intent", "unclear")
        data.setdefault("clarification_question", None)
        data.setdefault("topic", "none")
        return data
    except Exception as e:
        print(f"⚠️ 의도 분류 JSON 파싱 오류: {e}")
        return {"primary_intent": "unclear", "clarification_question": None, "topic": "none"}
        
# 7. 메인 튜터 로직 (tutor_flow 전용)
def intelligent_tutor(user_question: str, explained_concepts: set, explanation_count: dict) -> dict:
    """전체 튜터링 프로세스 (기억력 + 설명 횟수 + Fallback 추가)"""
    log_debug(f"intelligent_tutor 호출: 질문='{user_question}', 기억={explained_concepts}, 횟수={explanation_count}")
    print(f"\n{'='*50}")
    print(f"📚 질문: {user_question}")
    print(f"{'='*50}\n")
    
    # 1) 개념 추출
    concept = extract_concept(user_question)
    print(f"🔍 추출된 개념: {concept}\n")
    
    if concept == "개념없음":
        # 이 로직은 이제 라우터의 안전장치에 의해 거의 호출되지 않음
        return {"error": "질문에서 수학 개념을 찾을 수 없습니다."}
    
    # 2) 개념 정보 가져오기 (수정: None 처리 추가)
    concept_info = retrieve_concept_from_graph(concept)
    
    if not concept_info:
        print(f"ℹ️ '{concept}' 개념을 지식 그래프에서 찾을 수 없음 → LLM Fallback 시도\n")
        log_missing_concept(concept)
        return {"fallback_needed": True, "concept": concept, "learning_path": {"nodes": [], "edges": []}}

    path_data = get_path_for_visualization(concept)
    
    # 3) 선수 개념 찾기 (그래프에 개념이 있는 경우)
    all_prerequisites = get_prerequisites(concept)
    
    if not all_prerequisites:
        print("ℹ️ 선수 개념 없음 → 바로 설명\n")
        count = explanation_count.get(concept, 0)
        explanation_stream = generate_explanation(concept_info, count)
        return {
            "concept": concept,
            "explanation_stream": explanation_stream,
            "needs_diagnosis": False,
            "learning_path": path_data
        }


    immediate_prereqs = [p for p in all_prerequisites if p['depth'] == 1]
    prereqs_to_check = [p for p in immediate_prereqs if p['name'] not in explained_concepts]

    if not prereqs_to_check:
        print(f"ℹ️ 선수 개념 ({[p['name'] for p in immediate_prereqs]}) (이미 학습됨) → 바로 설명\n")
        count = explanation_count.get(concept, 0)
        explanation_stream = generate_explanation(concept_info, count)
        return {
            "concept": concept, "concept_info": concept_info,
            "prerequisites": [], "needs_diagnosis": False,
            "explanation_stream": explanation_stream,
            "learning_path": path_data
        }

    print(f"📋 확인 필요한 선수 개념: {[p['name'] for p in prereqs_to_check]}\n")
    diagnostic_q_stream = generate_diagnostic_question(concept, prereqs_to_check)
    
    return {
        "concept": concept,
        "concept_info": concept_info,
        "prerequisites": prereqs_to_check,
        "needs_diagnosis": True,
        "diagnostic_question_stream": diagnostic_q_stream,
        "learning_path": path_data
    }

# 7-1. 진단 응답 처리 함수 (tutor_flow 전용)
def handle_diagnostic_response(concept_info: dict, user_response: str, prerequisites: list, explanation_count: dict) -> dict:
    """
    진단 질문에 대한 학생 답변을 처리하고, 설명 큐를 생성하여 첫 설명을 반환합니다.
    """
    print(f"\n💬 학생 답변: {user_response}\n")
    
    prereq_names = [p["name"] for p in prerequisites]
    
    # 1) 이해도 판단
    understanding_map = assess_understanding(user_response, prereq_names)
    print(f"📊 이해도 분석: {understanding_map}\n")
    
    # 2) 설명 큐 생성 
    explanation_queue, unmentioned_concepts = build_explanation_queue(
        understanding_map, concept_info['name']
    )
    
    concept_to_explain_name = explanation_queue.pop(0) 
    
    current_concept_info = None
    if concept_to_explain_name == concept_info['name']:
        current_concept_info = concept_info
    else:
        current_concept_info = retrieve_concept_from_graph(concept_to_explain_name)

    count = explanation_count.get(concept_to_explain_name, 0)
    
    if not current_concept_info:
        first_explanation_text = f"'{concept_to_explain_name}' 개념에 대한 정보를 찾을 수 없습니다."
        explanation_stream = iter([first_explanation_text])
    else:
        explanation_stream = generate_explanation(current_concept_info, count)
    
    # 3) 후속 질문 생성 (스트림에 추가하기 위해 텍스트로 변환 필요)
    follow_up_text = ""
    if explanation_queue:
        next_concept_name = explanation_queue[0]
        is_next_unmentioned = next_concept_name in unmentioned_concepts 
        if is_next_unmentioned:
            follow_up_text = f"\n\n💡 이 개념이 이해되셨나요? 그럼 '{next_concept_name}'(은)는 알고 계신가요?"
        else:
            follow_up_text = f"\n\n💡 이 개념이 이해되셨나요? 다음으로 '{next_concept_name}'(을)를 설명해드릴까요?"
    else:
        follow_up_text = f"\n\n💡 '{concept_to_explain_name}'에 대한 설명이 끝났어요. 더 궁금한 것이 있나요?"

    return {
        "explanation_stream": explanation_stream,
        "follow_up_text": follow_up_text,
        "queue": explanation_queue,
        "understanding_map": understanding_map,
        "unmentioned_concepts": unmentioned_concepts,
        "explained_concept_name": concept_to_explain_name
    }

# 7-2. 설명 큐 생성 함수 (tutor_flow 전용)
def build_explanation_queue(understanding_map: dict, target_concept: str) -> tuple[list, list]:
    """
    이해도 맵으로부터 설명 큐(Queue)와 언급 안 된 개념 리스트를 생성한다.
    큐 순서: 모르는 것(False) -> 언급 안 한 것(None) -> 목표 개념
    """
    unknown = [name for name, status in understanding_map.items() if status is False]
    unmentioned = [name for name, status in understanding_map.items() if status is None]
    known = [name for name, status in understanding_map.items() if status is True]
    
    queue = unknown + unmentioned + [target_concept]
    
    seen = set(known) 
    unique_queue = []
    for concept in queue:
        if concept not in seen:
            unique_queue.append(concept)
            seen.add(concept)
            
    final_queue = unique_queue or [target_concept] 
    
    print(f"🧠 설명 큐 생성: {final_queue} (다음 대기)")
    return final_queue, unmentioned

# 8. 시스템 명령어 감지 함수
def is_system_command(text: str) -> bool:
    """입력이 시스템 명령어 또는 코드 조각인지 간단히 감지합니다."""
    if not text:
        return False
        
    FILTER_KEYWORDS = ["pyenv", "python", ".py", "conda", "pip", "import ", "def ", "class "]
    text_lower = text.lower()
    
    if len(text.split()) < 5 and any(kw in text_lower for kw in FILTER_KEYWORDS):
        return True
        
    if "/" in text or "\\" in text:
        if text.replace("/", "").replace(" ", "").isdigit():
             return False
        return True

    return False

# 8-1. 대화 상태 초기화 함수
def reset_conversation_flow(state: dict, keep_memory: bool = True):
    """
    대화 흐름 관련 상태 변수들을 초기화합니다.
    keep_memory가 False이면 학습 기억(explained_concepts 등)까지 초기화합니다.
    """
    print("🔄 대화 흐름을 초기화합니다.")
    state["mode"] = "IDLE"
    state["queue"] = []
    state["unmentioned_concepts"] = []
    state["last_tutor_question_type"] = None
    state["target_concept_info"] = None
    state["prerequisites"] = []
    state["primary_goal_concept"] = None
    state["pending_input"] = None 
    state["learning_path"] = {"nodes": [], "edges": []} # <-- 이 줄 추가

    if not keep_memory:
        print("🧠 학습 기억도 초기화합니다.")
        state["explained_concepts"] = set()
        state["explanation_count"] = {}
        state["last_explained_concept"] = None
    
# 8-3. 누락 개념 기록 함수
def log_missing_concept(concept_name: str, log_file="missing_concepts.log"):
    """그래프에 없는 개념을 로그 파일에 기록합니다."""
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{concept_name}\n")
        log_debug(f"'{concept_name}' 개념 누락 기록 완료.")
    except Exception as e:
        print(f"⚠️ 누락 개념 로깅 오류: {e}")


# 9. 핵심 튜터 상태 머신 함수
def handle_tutor_flow(user_input: str, new_state: dict) -> dict:
    """
    복잡한 튜터링 상태 머신 (State Machine) 로직.
    오직 '수학 개념 설명'의 흐름만 담당합니다.
    (수정) prefix, stream, text를 분리하여 반환합니다.
    """
    log_debug(f"핵심 튜터 로직(handle_tutor_flow) 실행...")
    
    # 스트림 반환용 변수
    response_stream = None
    response_text = ""
    response_prefix = "" 

    current_mode = new_state.get("mode", "IDLE")

    # --- 상태 0: 설명 완료 후 ---
    if current_mode == "POST_EXPLANATION":
        intent_data = classify_continuation_intent(user_input, question_type="post_explanation", last_explained_concept=new_state.get("last_explained_concept", "none"))
        primary_intent = intent_data.get("primary_intent")
        topic = intent_data.get("topic")
        log_debug(f"POST_EXPLANATION(tutor_flow) 의도 분석: 주={primary_intent}, 주제={topic}")

        if primary_intent == "re-explain":
            input_for_next_turn = ""
            if topic != "none":
                input_for_next_turn = topic
            else:
                if user_input not in ["??", "?", "흠", "음"]:
                     input_for_next_turn = user_input
                else:
                     input_for_next_turn = new_state.get("last_explained_concept")

            if input_for_next_turn:
                response_text = f"🔄 ('{input_for_next_turn}'(으)로 재설명 요청을 처리합니다.)"
                reset_conversation_flow(new_state)
                new_state["pending_input"] = input_for_next_turn 
            else:
                response_text = "어떤 개념을 다시 설명해 드릴까요?"
                new_state["mode"] = "POST_EXPLANATION"
            
        elif primary_intent == "new_question":
            response_text = "🔄 (새로운 질문으로 처리합니다.)"
            reset_conversation_flow(new_state)
            new_state["pending_input"] = topic if topic != "none" else user_input

        elif primary_intent == "acknowledged":
            response_text = "네! 다른 질문이 있으면 편하게 해주세요."
            new_state["mode"] = "POST_EXPLANATION"
        
        else: # unclear
            response_text = "흠... 방금 하신 말씀이 재설명 요청인지, 새 질문인지 잘 모르겠어요. 다시 말씀해주시겠어요?"
            new_state["mode"] = "POST_EXPLANATION"

    # --- 상태 1: "다음 설명해줄까?" / "알고 계신가요?" 답변 처리 ---
    elif current_mode == "WAITING_CONTINUATION":
        current_queue = new_state.get("queue", [])
        if not current_queue:
            log_debug("WAITING_CONTINUATION 상태인데 큐가 비어있음 - 초기화")
            reset_conversation_flow(new_state)
            response_text = "흠, 대화가 잠시 꼬였네요. 새로운 질문을 해주세요."
            # (수정) prefix 키 추가
            return {"response_prefix": "", "response_text": response_text, "response_stream": None, "new_state": new_state}
        
        next_concept = current_queue[0]
        question_type = new_state.get("last_tutor_question_type", "shall_i_explain")

        intent_data = classify_continuation_intent(user_input, next_concept, question_type, last_explained_concept=new_state.get("last_explained_concept", "none"))
        primary_intent = intent_data.get("primary_intent")
        clarification_q = intent_data.get("clarification_question")
        topic = intent_data.get("topic")
        log_debug(f"WAITING_CONTINUATION 의도 분석: 주={primary_intent}, 부가질문={clarification_q}, 주제={topic}")

        explanation_stream = None
        follow_up_text = ""

        if clarification_q:
            last_concept = new_state.get("last_explained_concept", "이전 개념")
            response_prefix = f"좋은 질문이에요! '{last_concept}'(은)는 '{next_concept}'(을)를 이해하는 데 꼭 필요한 기초 개념이랍니다. "
            log_debug(f"부가 질문 답변(접두사) 생성: {response_prefix}")

        if primary_intent == "continue":
            concept_to_explain_name = current_queue.pop(0)
            log_debug(f"설명 진행: {concept_to_explain_name}")
            current_concept_info = None
            
            if concept_to_explain_name == new_state["target_concept_info"]["name"]:
                 current_concept_info = new_state["target_concept_info"]
            else:
                 current_concept_info = retrieve_concept_from_graph(concept_to_explain_name)
            
            count = new_state["explanation_count"].get(concept_to_explain_name, 0)
            
            if not current_concept_info:
                 explanation_stream = iter([f"'{concept_to_explain_name}' 개념에 대한 정보를 찾을 수 없습니다."])
            else:
                 explanation_stream = generate_explanation(current_concept_info, count)
            
            new_state["explained_concepts"].add(concept_to_explain_name)
            new_state["explanation_count"][concept_to_explain_name] = count + 1
            new_state["last_explained_concept"] = concept_to_explain_name

        elif primary_intent == "skip":
            skipped_concept = current_queue.pop(0)
            log_debug(f"설명 건너뛰기: {skipped_concept}")
            explanation_stream = iter([f"알겠습니다! '{skipped_concept}'(은)는 이미 알고 계셨군요."])
            new_state["explained_concepts"].add(skipped_concept)

        elif primary_intent == "re-explain":
            log_debug(f"{topic} 재설명 요청")
            r_info = retrieve_concept_from_graph(topic)
            count = new_state["explanation_count"].get(topic, 0)
            
            if r_info:
                 response_prefix += f"아, '{topic}'(이)가 아직 이해가 안 되셨군요. 다시 설명해드릴게요.\n\n"
                 explanation_stream = generate_explanation(r_info, count)
            else:
                 explanation_stream = iter([f"'{topic}'에 대한 정보를 찾을 수 없네요."])
            
            new_state["explained_concepts"].add(topic)
            new_state["explanation_count"][topic] = count + 1
            new_state["last_explained_concept"] = topic

        else: # new_question or unclear
            if primary_intent == "new_question" and topic != "none":
                 log_debug(f"새 질문 감지: {topic}")
                 response_text = f"알겠습니다! 그럼 '{topic}'에 대해 먼저 알아볼까요?"
                 reset_conversation_flow(new_state)
                 new_state["pending_input"] = topic
            else: 
                 # (수정) 의도 불명확 시, 초기화 대신 재질문
                 log_debug(f"의도 불명확({primary_intent}) - 재질문 시도")
                 response_text = f"죄송해요, '{user_input}'(이)라고 하신 게 '네'라는 뜻인지 '아니오'라는 뜻인지 잘 모르겠어요. '{next_concept}' 개념을 설명해드릴까요?"
                 
                 # (수정) 현재 상태와 큐를 유지한 채, 질문 방식만 변경
                 new_state["mode"] = "WAITING_CONTINUATION"
                 new_state["last_tutor_question_type"] = "shall_i_explain" # 질문을 "설명해줄까요?"로 명확하게
           
            return {"response_prefix": response_prefix, "response_text": response_text, "response_stream": None, "new_state": new_state}
      
        #후속 처리
        if current_queue:
            next_concept_name = current_queue[0]
            is_next_unmentioned = next_concept_name in new_state.get("unmentioned_concepts", [])
            
            if is_next_unmentioned:
                q_type = "do_you_know"
                response_text = f"\n\n💡 그럼 다음으로 '{next_concept_name}'(은)는 알고 계신가요?"
            else:
                q_type = "shall_i_explain"
                response_text = f"\n\n💡 이 개념이 이해되셨나요? 다음으로 '{next_concept_name}'(을)를 설명해드릴까요?"
            
            new_state["mode"] = "WAITING_CONTINUATION"
            new_state["queue"] = current_queue
            new_state["last_tutor_question_type"] = q_type
        else:
            response_text = f"\n\n💡 모든 설명이 끝났어요! 더 궁금한 것이 있나요?"
            new_state["mode"] = "POST_EXPLANATION"

        response_stream = explanation_stream

    # --- 상태 2: "방정식 알아?"에 대한 답변 처리 ---
    elif current_mode == "WAITING_DIAGNOSTIC":
        # (수정) 진단 답변도 의도 분류를 먼저 수행 (새 질문/재설명 등 중단 요청 감지)
        prereq_names = [p["name"] for p in new_state.get("prerequisites", [])]
        intent_data = classify_continuation_intent(user_input, 
                                                   next_concept=", ".join(prereq_names), 
                                                   question_type="do_you_know", 
                                                   last_explained_concept=new_state.get("last_explained_concept", "none"))
        
        primary_intent = intent_data.get("primary_intent")
        topic = intent_data.get("topic")
        log_debug(f"WAITING_DIAGNOSTIC 의도 분석: 주={primary_intent}, 주제={topic}")

        if primary_intent == "new_question":
             log_debug(f"진단 중 새 질문 감지: {topic}")
             response_text = f"알겠습니다! 그럼 '{topic}'에 대해 먼저 알아볼까요?"
             reset_conversation_flow(new_state)
             new_state["pending_input"] = topic if topic != "none" else user_input
             return {"response_prefix": "", "response_text": response_text, "response_stream": None, "new_state": new_state}
        
        # "continue", "skip", "unclear" (기존 답변)일 때만 진단 응답 처리
        # "re-explain"은 이 상태에서 "unclear"로 처리되어도 무방
        result = handle_diagnostic_response(
            new_state["target_concept_info"],
            user_input,
            new_state["prerequisites"],
            new_state["explanation_count"]
        )
        response_stream = result['explanation_stream']
        response_text = result.get('follow_up_text', '') 
        understanding_map = result.get("understanding_map", {})
        for name, understood in understanding_map.items():
            if understood is True:
                new_state["explained_concepts"].add(name)
        
        explained_name = result["explained_concept_name"]
        new_state["explained_concepts"].add(explained_name)
        count = new_state["explanation_count"].get(explained_name, 0)
        new_state["explanation_count"][explained_name] = count + 1
        new_state["last_explained_concept"] = explained_name

        if result["queue"]:
            new_state["mode"] = "WAITING_CONTINUATION"
            new_state["queue"] = result["queue"]
            unmentioned = result.get("unmentioned_concepts", []) 
            new_state["unmentioned_concepts"] = unmentioned 
            next_q = result["queue"][0]
            if next_q in unmentioned:
                new_state["last_tutor_question_type"] = "do_you_know"
            else:
                new_state["last_tutor_question_type"] = "shall_i_explain"
        else:
            new_state["mode"] = "POST_EXPLANATION"

    # --- 상태 3: 새로운 질문 처리 (IDLE 상태) ---
    elif current_mode == "IDLE":
        result = intelligent_tutor(
            user_input,
            new_state["explained_concepts"],
            new_state["explanation_count"]
        )
        
        # learning_path가 있으면 new_state에 저장 (신규) 
        if result.get("learning_path"):
            new_state["learning_path"] = result["learning_path"]

        if result.get("error"):
            response_text = f"{result['error']}. 다른 질문이 있을까요?"
            new_state["mode"] = "IDLE"

        elif result.get("fallback_needed"):
            concept_name = result["concept"]
            # (수정) 접두사(response_prefix)로 분리하고, 스트림 래핑(wrapping) 제거
            response_prefix = f"'{concept_name}'에 대해 제가 아는 선에서 설명해 드릴게요.\n\n"
            fallback_stream = generate_general_explanation(concept_name)
            
            response_stream = fallback_stream
            new_state["last_explained_concept"] = concept_name
            new_state["mode"] = "POST_EXPLANATION"

        elif result.get("needs_diagnosis"):
            response_stream = result['diagnostic_question_stream']
            
            new_state["mode"] = "WAITING_DIAGNOSTIC"
            new_state["target_concept_info"] = result["concept_info"]
            new_state["prerequisites"] = result["prerequisites"]
            new_state["queue"] = [] 
            new_state["unmentioned_concepts"] = []
            new_state["last_tutor_question_type"] = None
            new_state["primary_goal_concept"] = result["concept"]

        else: 
            response_stream = result['explanation_stream']
            
            concept_name = result["concept"]
            new_state["explained_concepts"].add(concept_name)
            count = new_state["explanation_count"].get(concept_name, 0)
            new_state["explanation_count"][concept_name] = count + 1
            new_state["last_explained_concept"] = concept_name
            new_state["mode"] = "POST_EXPLANATION"
            response_text = "\n\n💡 더 궁금한 것이 있나요?"
            
    return {"response_prefix": response_prefix, "response_stream": response_stream, "response_text": response_text, "new_state": new_state}

# 10. 마스터 함수: process_turn (교통 정리 담당)
def get_initial_state() -> dict:
    """Streamlit 세션 초기화를 위한 기본 상태값을 반환합니다."""
    
    # (수정) JSON 파일에서 프로필을 로드합니다.
    profile_data = load_profile()
    
    # (수정) 세션 상태 기본값을 추가합니다.
    initial_state = {
        "mode": "IDLE",
        "primary_goal_concept": None,
        "target_concept_info": None,
        "prerequisites": [],
        "queue": [],
        "unmentioned_concepts": [],
        "last_tutor_question_type": None,
        "last_explained_concept": None,
        **profile_data  # (수정) 로드된 'explained_concepts'와 'explanation_count'를 병합
    }
    return initial_state

def process_turn(user_input: str, current_state: dict) -> dict:
    """
    모든 대화 로직을 처리하는 마스터 함수.
    라우터를 호출하여 '교통 정리' 후 담당 핸들러에게 작업을 위임합니다.
    (수정) prefix, stream, text를 모두 결합하여 최종 스트림 또는 텍스트를 반환합니다.
    """
    
    # 1) 상태 복사 및 기본값 설정
    response_prefix = ""
    response_stream = None
    response_text = ""
    new_state = current_state.copy() 
    
    new_state["explained_concepts"] = set(current_state.get("explained_concepts", []))
    new_state["explanation_count"] = current_state.get("explanation_count", {}).copy()
    new_state["queue"] = current_state.get("queue", []).copy()
    new_state["unmentioned_concepts"] = current_state.get("unmentioned_concepts", []).copy()
    new_state["prerequisites"] = current_state.get("prerequisites", []).copy()
    if current_state.get("target_concept_info"):
        new_state["target_concept_info"] = current_state["target_concept_info"].copy()
        
    final_stream = None
    final_text = ""
        
    try:
        log_debug(f"현재 상태: {new_state['mode']}, 큐: {new_state['queue']}, 기억: {new_state['explained_concepts']}")
        
        # 2) 입력 처리 (pending_input, 필터링 등)
        if new_state.get("pending_input"):
            user_input = new_state.pop("pending_input")
            print(f"\n📚 학생 (보류된 입력 처리): {user_input}")
        
        if not new_state.get("pending_input") and is_system_command(user_input):
            final_text = "(명령어 또는 코드 입력으로 보여 무시합니다. 수학 질문을 해주세요.)"
            new_state["explained_concepts"] = list(new_state["explained_concepts"])
            return {"response_text": final_text, "explanation_stream": None, "new_state": new_state} 

        if user_input.lower() in ["종료", "exit", "quit"]:
            final_text = "다음에 또 만나요! 👋"
            new_state = get_initial_state()
            new_state["explained_concepts"] = list(new_state["explained_concepts"])
            return {"response_text": final_text, "explanation_stream": None, "new_state": new_state}
        if not user_input:
            final_text = "(입력이 없습니다. 다시 말씀해주세요.)"
            new_state["explained_concepts"] = list(new_state["explained_concepts"])
            return {"response_text": final_text, "explanation_stream": None, "new_state": new_state}

        # 3) (핵심) 마스터 라우터 호출
        task, topic = call_master_router(user_input, new_state) # (수정) topic 반환
        log_debug(f"마스터 라우터 분류 결과: '{task}', 주제: '{topic}'")

        # 4) 작업 분배 (라우팅)
        if task == "greeting":
            response_stream = iter(["안녕하세요! 🤖 수학 개념에 대해 질문해주시면 자세히 설명해 드릴게요."])
        
        elif task == "ask_problem":
            concept_for_problem = None
            if topic != "none":
                log_debug(f"요청된 주제 '{topic}'(으)로 문제 생성 시도")
                concept_for_problem = topic
            else:
                last_concept = new_state.get("last_explained_concept")
                if last_concept:
                    log_debug(f"마지막 학습 개념 '{last_concept}'(으)로 문제 생성 시도")
                    concept_for_problem = last_concept
            
            if concept_for_problem:
                # (신규) 이 개념에 대한 설명/문제풀이 횟수를 가져옴
                count = new_state.get("explanation_count", {}).get(concept_for_problem, 0)
                
                # (수정) generate_problem 호출 시 count 전달
                problem_result = generate_problem(concept_for_problem, count)
                response_stream = problem_result["problem_stream"]
                
                if problem_result["problem_data"]:
                    # (수정) 새 상태와 정답 데이터를 new_state에 저장
                    new_state["mode"] = "WAITING_PROBLEM_ANSWER" # (중요) 새 모드 설정
                    new_state["current_problem"] = problem_result["problem_data"]
                    log_debug(f"새 문제 상태 저장: {new_state['current_problem']}")
                else:
                    # 문제 생성 실패 시
                    new_state["mode"] = "POST_EXPLANATION" 
            else:
                log_debug("문제 생성 요청 실패: 주제 및 마지막 개념 없음")
                response_text = "먼저 학습할 개념을 알려주세요! 어떤 개념에 대한 문제를 내드릴까요?"
                new_state["mode"] = "IDLE"

        elif task == "chitchat":
            log_debug("잡담 처리 요청")
            response_stream = handle_chitchat(user_input)
        
        elif task == "solve_problem":
            log_debug("문제 풀이 답변 처리 요청")
            
            # (수정) new_state에서 현재 문제 정보 가져오기
            problem_data = new_state.get("current_problem")
            
            if problem_data:
                # (수정) 새 핸들러를 호출하여 피드백 스트림 생성
                response_stream = handle_solve_problem(user_input, problem_data)
                new_state["mode"] = "POST_EXPLANATION" # 채점 후 다시 일반 대기 모드
                new_state["current_problem"] = None # (중요) 풀이가 끝났으므로 문제 데이터 비우기
            else:
                # 비정상적인 상황 (버그)
                log_debug("오류: WAITING_PROBLEM_ANSWER 상태였으나 current_problem 데이터가 없음")
                response_text = "어떤 문제에 대한 답인지 잘 모르겠어요. 다시 질문해주시겠어요?"
                new_state["mode"] = "IDLE"
            
        elif task == "tutor_flow":
            log_debug("핵심 튜터 흐름(tutor_flow) 핸들러 호출")
            result_dict = handle_tutor_flow(user_input, new_state)
            
            response_prefix = result_dict.get("response_prefix", "")
            response_stream = result_dict.get("response_stream")
            response_text = result_dict.get("response_text", "")
            new_state = result_dict.get("new_state", new_state)

        else:
            log_debug(f"알 수 없는 라우터 작업: {task}")
            response_text = "죄송합니다. 요청을 이해하지 못했어요. 다시 말씀해주시겠어요?"
            reset_conversation_flow(new_state)

        # 3가지 요소 (prefix, stream, text)가 모두 있는지 확인
        has_prefix = response_prefix and response_prefix.strip()
        has_stream = response_stream is not None
        has_suffix = response_text and response_text.strip()
        
        if not has_prefix and not has_stream and not has_suffix:
            log_debug("반환할 응답이 없습니다. (라우팅 오류 가능성)")
            final_text = "죄송합니다. 응답을 생성하지 못했습니다."
            
        elif not has_stream:
            # 스트림 없이 텍스트(접두사, 후속질문)만 있는 경우 (e.g. greeting)
            log_debug("스트림 없이 prefix/suffix 텍스트만 반환합니다.")
            final_text = (response_prefix if has_prefix else "") + (response_text if has_suffix else "")
            
        else:
            log_debug("스트림과 optional prefix/suffix를 결합합니다.")
            
            def combined_stream_generator():
                # 1. Prefix (접두사)
                if has_prefix:
                    yield response_prefix
                    
                # 2. Stream (메인 스트림)
                stream_content = ""
                for chunk in response_stream:
                    stream_content += chunk
                    yield chunk
                
                # 3. Suffix (후속 질문)
                if has_suffix:
                    stream_content_normalized = " ".join(stream_content.split())
                    response_text_normalized = " ".join(response_text.split())
                    
                    if not stream_content_normalized.endswith(response_text_normalized):
                        log_debug("스트림 끝에 후속 텍스트(suffix)를 추가합니다.")
                        yield response_text 
                    else:
                        log_debug("스트림에 이미 후속 텍스트가 포함되어 있어 추가하지 않습니다.")

            final_stream = combined_stream_generator()

    # 5. 예외 처리 (전체 process_turn 함수를 감싸는 try-except)
    except Exception as e:
        print(f"--- 🚨 FATAL ERROR in process_turn ---")
        import traceback
        traceback.print_exc()
        print(f"--------------------------------------")
        final_stream = None
        final_text = f"죄송합니다. 튜터와 대화 중 심각한 오류가 발생했습니다: {e}. 기록을 초기화합니다."
        new_state = get_initial_state() 
            
    # 6. 최종 반환 (app.py가 기대하는 형식)
        
    save_profile(new_state)
    
    if "explained_concepts" in new_state:
        new_state["explained_concepts"] = list(new_state["explained_concepts"])
             
    current_mode = new_state.get("mode")
    if current_mode not in ["WAITING_DIAGNOSTIC", "WAITING_CONTINUATION"]:
        if "target_concept_info" in new_state:
            log_debug(f"대화 흐름(mode: {current_mode})이 종료되어 target_concept_info를 비웁니다.")
            new_state["target_concept_info"] = None
        
    final_state_summary = {
        k: v for k, v in new_state.items() 
        if k not in ["target_concept_info", "prerequisites"]
    }
    log_debug(f"반환 상태: {final_state_summary}")
        
    return {
            "explanation_stream": final_stream,
            "response_text": final_text,
            "new_state": new_state
    }