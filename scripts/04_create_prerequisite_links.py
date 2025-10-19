import os
import json
import openai
from neo4j import GraphDatabase
from dotenv import load_dotenv
from itertools import combinations

# 환경설정
load_dotenv()
NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USER = os.getenv('NEO4J_USER')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
openai.api_key = os.getenv('OPENAI_API_KEY')

#LLM 호출
def find_prerequisites_with_llm(target_concept, candidate_concepts):
    """LLM을 이용해 후보 목록에서 실제 선수 지식을 찾아내는 함수"""
    
    # 후보가 없으면 종료
    if not candidate_concepts:
        return []
    
    #프롬프트 엔지니어링 개선 필요함
    system_prompt = """
    당신은 중학교 수학 교육과정 전문가입니다.
    학생이 목표 개념을 배우기 위해 반드시 먼저 알아야 하는 최소한의 핵심 개념만 선수 지식으로 판단하세요.

    **엄격한 선수 지식 기준 (모두 충족해야 함)**

    1. **직접성**: 목표 개념의 정의나 핵심 설명에 후보 개념이 직접 등장한다
    2. **불가피성**: 후보 개념 없이는 목표 개념을 이해하거나 사용하는 것이 불가능하다
    3. **즉시성**: 목표 개념을 배우는 바로 그 시점에 후보 개념이 필요하다 (나중에 응용할 때가 아님)

    **선수 지식이 아닌 경우**

    ❌ 간접적으로만 관련됨 (예: "회전체" 배울 때 "좌표평면"은 불필요)
    ❌ 같은 영역이지만 병렬 개념 (예: "부피"와 "겉넓이")
    ❌ 응용 단계에서 만나는 개념
    ❌ "알면 좋지만" 수준의 개념

    **목표: 평균 1~2개만 선택** (0개도 가능, 3개 이상은 드묾)

    ---

    **판단 프로세스**

    각 후보에 대해:
    1. "이 개념의 정의/설명에 후보가 명시적으로 사용되는가?" 
    → 아니오면 제외
    2. "이 개념을 모르면 목표 개념을 절대 이해 못하는가?"
    → "어렵긴 하지만 가능"이면 제외
    3. "지금 당장 필요한가, 나중 응용에서 필요한가?"
    → 나중이면 제외

    ---

    **좋은 예시**

    목표: 일차방정식 (ax + b = 0 형태의 방정식)
    후보: [등식, 미지수, 방정식, 부등식, 함수]

    분석:
    - "등식": 방정식의 정의가 "미지수의 값에 따라 참/거짓이 정해지는 등식" → 정의에 직접 사용 ✅
    - "미지수": ax+b=0의 'x'가 미지수 → 정의에 직접 사용 ✅
    - "방정식": "일차방정식"은 방정식의 한 종류 → 상위 개념 ✅
    - "부등식": 방정식과 병렬 개념, 서로 독립적 ❌
    - "함수": 나중에 연결되지만 일차방정식 자체 이해엔 불필요 ❌

    **결과: ["등식", "미지수", "방정식"]** (3개 - 모두 정의에 직접 등장)

    ---

    **나쁜 예시 (너무 많이 잡은 경우)**

    목표: 회전체 (평면도형을 회전축을 중심으로 회전시켜 만든 입체도형)
    후보: [좌표평면, 다면체, 좌표, 겉넓이, 그래프, 입체도형, 평면도형]

    잘못된 판단:
    - "좌표평면": 회전체를 좌표평면에 그릴 수 있지만, 정의 자체엔 불필요 ❌
    - "다면체": 회전체는 곡면이므로 다면체 개념 불필요 ❌
    - "겉넓이": 회전체를 배운 후 계산하는 것, 선수 지식 아님 ❌
    - "그래프": 전혀 관련 없음 ❌
    - "입체도형": 회전체는 입체도형의 일종 → 상위 개념 ✅
    - "평면도형": 정의에 "평면도형을 회전"이라고 명시 ✅

    **올바른 결과: ["입체도형", "평면도형"]** (2개만)

    ---

    **또 다른 예시**

    목표: 부피 (입체도형이 차지하는 공간의 크기)
    후보: [다면체, 겉넓이, 입체도형, 길이, 넓이]

    분석:
    - "다면체": 부피는 모든 입체도형에 적용, 다면체만의 개념 아님 ❌
    - "겉넓이": 부피와 병렬 개념 (둘 다 입체도형의 속성) ❌
    - "입체도형": 부피의 정의에 "입체도형이 차지하는" 명시 ✅
    - "길이": 1차원 개념, 부피는 3차원 → 간접 관련 ❌
    - "넓이": 부피를 설명할 때 "넓이 × 높이"처럼 사용 → 개념적 확장 ✅

    **결과: ["입체도형", "넓이"]** (2개)

    ---

    **중요 원칙**

    - **보수적으로 판단하세요**: 확신이 없으면 제외
    - **정의 중심으로 생각하세요**: 응용/계산은 나중 문제
    - **최소주의**: 꼭 필요한 것만

    <result>
    {"prerequisites": ["개념1", "개념2"]}
    </result>

    형식으로 답하되, **보통 0~2개, 최대 3개**를 목표로 하세요.
    """
    
    # 프롬프트 구성
    target_str = f"- 목표 개념: {target_concept['name']} ({target_concept['definition']})"
    candidates_str = "\n".join([f"- {c['name']} ({c['definition']})" for c in candidate_concepts])
    user_prompt = f"{target_str}\n\n[후보 목록]\n{candidates_str}"

    # find_prerequisites_with_llm 함수 안의 try...except 블록 교체

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # 응답 형식을 자유롭게
        )
        # LLM의 응답에서 <result> 태그 안의 JSON 부분만 추출
        full_response = response.choices[0].message.content
        
        # 정규식을 사용하여 <result> 태그 안의 내용 추출
        import re
        match = re.search(r'<result>(.*?)</result>', full_response, re.DOTALL)
        
        if match:
            result_json = match.group(1).strip()
            result_data = json.loads(result_json)
            return result_data.get("prerequisites", [])
        else:
            return [] # result 태그를 찾지 못한 경우

    except Exception as e:
        print(f"  -> LLM 호출 또는 파싱 중 오류 발생: {e}")
        return []

class Neo4jGraph:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def run_query(self, query, parameters=None):
        with self._driver.session() as session:
            result = session.run(query, parameters)
            # result.consume() 코드를 삭제하여, 결과를 반환
            return [record for record in result]


#메인
def create_prerequisite_links(graph_db):
    print("그래프에서 모든 핵심 개념(CoreConcept) 노드와 학년/학기 정보를 가져옵니다...")
    
    # CoreConcept 노드를 가져올 때, Concept 노드로부터 grade와 semester 정보를 가져와 합치기
    query = """
    MATCH (core:CoreConcept)<-[:IS_EXAMPLE_OF]-(raw:Concept)
    WITH core, head(collect(raw)) AS example_raw_node
    RETURN core { .*, grade: example_raw_node.grade, semester: example_raw_node.semester } AS concept_data
    """
    
    all_concepts = []
    result = graph_db.run_query(query)
    for record in result:
        all_concepts.append(record['concept_data'])

    print(f"총 {len(all_concepts)}개의 핵심 개념에 대해 선수 지식 관계를 생성합니다.")

    # 2. 각 개념(target)에 대해 루프를 돌며 선수 지식(prereq)을 찾음
    for i, target_concept in enumerate(all_concepts):
        print(f"\n--- [{i+1}/{len(all_concepts)}] '{target_concept['name']}' 개념 처리 중 ---")
        
        # 3. 선수 지식 후보군 필터링 (학년/학기 기준)
        candidates = []
        for prereq_concept in all_concepts:
            if prereq_concept['name'] == target_concept['name']:
                continue # 자기 자신은 제외
            # 학년이 더 낮으면 후보에 포함
            if int(prereq_concept['grade'][0]) < int(target_concept['grade'][0]):
                candidates.append(prereq_concept)
            # 학년이 같고, 학기가 더 낮으면 후보에 포함 ('공통'은 0학기로 취급)
            elif prereq_concept['grade'] == target_concept['grade']:
                target_semester = 0 if '공통' in target_concept['semester'] else int(target_concept['semester'][0])
                prereq_semester = 0 if '공통' in prereq_concept['semester'] else int(prereq_concept['semester'][0])
                if prereq_semester < target_semester:
                    candidates.append(prereq_concept)

        if not candidates:
            print("  -> 후보가 없어 건너뜁니다.")
            continue
        
        print(f"  -> {len(candidates)}개의 후보를 LLM으로 분석합니다...")
        
        # 4. LLM을 호출하여 최종 선수 지식 리스트를 받음
        prerequisite_names = find_prerequisites_with_llm(target_concept, candidates)
        
        if not prerequisite_names:
            print("  -> LLM이 선택한 선수 지식이 없습니다.")
            continue
            
        print(f"  -> LLM이 선택한 선수 지식: {prerequisite_names}")

        # 선택된 선수 지식들에 대해 IS_PREREQUISITE_OF 관계 생성
        for prereq_name in prerequisite_names:
            query = """
            MATCH (prereq:CoreConcept {name: $prereq_name})
            MATCH (target:CoreConcept {name: $target_name})
            MERGE (prereq)-[:IS_PREREQUISITE_OF]->(target)
            """
            graph_db.run_query(query, parameters={
                "prereq_name": prereq_name,
                "target_name": target_concept['name']
            })
            
    print("\n\n🎉 모든 선수 지식 관계 생성이 완료되었습니다!")

if __name__ == "__main__":
    db = Neo4jGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    create_prerequisite_links(db)
    db.close()