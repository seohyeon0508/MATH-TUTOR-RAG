import os
import json
import openai
from neo4j import GraphDatabase
from dotenv import load_dotenv

#환경설정
load_dotenv()
NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USER = os.getenv('NEO4J_USER')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
openai.api_key = os.getenv('OPENAI_API_KEY')

# LLM 호출함수
def extract_core_concepts_with_llm(texts):
    system_prompt = """
    당신은 중학교 수학 교과서의 '소단원 목차'를 만드는 편집자입니다.
    주어진 문장들을 바탕으로, 학생들이 실제로 배우게 될 '소단원의 제목'이 될 만한 구체적인 학습 개념을 1~2개 정도 추출해주세요.
    
    지켜야 할 규칙:
    1. 개념의 이름은 가장 보편적이고 간결한 핵심 용어를 사용해주세요. 예를 들어, '정비례 관계'나 '정비례의 개념' 대신 '정비례'를 사용하세요.
    2. 만약 'A 및 B'와 같이 두 개념이 함께 언급되면, 각각을 별개의 개념으로 추출해주세요. (예: '동위각 및 엇각' -> '동위각', '엇각')
    
    각 개념에 대해 'name'과 'definition'을 JSON 형식의 리스트로 반환해주세요.
    예시: {"concepts": [{"name": "최대공약수", "definition": "둘 이상의 자연수의 공통된 약수 중 가장 큰 수."}]}
    """
    user_prompt = "다음 문장들에서 핵심 개념을 추출해줘:\n\n" + "\n".join(texts)
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            response_format={"type": "json_object"}
        )
        result_json = response.choices[0].message.content
        result_data = json.loads(result_json)
        concepts = result_data.get("concepts", result_data)
        if isinstance(concepts, dict): return [concepts]
        elif isinstance(concepts, list): return concepts
        else: return []
    except Exception as e:
        print(f"LLM 호출 중 오류 발생: {e}")
        return []

class Neo4jGraph:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
    def close(self):
        self._driver.close()
    def run_query(self, query, parameters=None):
        with self._driver.session() as session:
            result = session.run(query, parameters)
            # 쓰기 작업 후에도 요약 정보 등이 필요할 수 있으므로, 항상 결과를 리스트로 반환
            return [record for record in result]

def link_concepts(graph_db):
    print("그래프에서 모든 성취기준을 가져옵니다...")
    # 필요한 속성만 가져오기
    query = "MATCH (s:AchievementStandard) RETURN s.code AS code, s.domain AS domain, s.grade AS grade, s.semester AS semester"
    standards = graph_db.run_query(query)
    
    for standard_record in standards:
        ach_code = standard_record["code"]
        print(f"\n--- 성취기준 '{ach_code}' 처리 중 ---")

        query = """
        MATCH (c:Concept)-[:BELONGS_TO]->(s:AchievementStandard {code: $code})
        RETURN c.definition AS text
        """
        raw_concept_records = graph_db.run_query(query, parameters={"code": ach_code})
        
        if not raw_concept_records:
            print("  -> 연결된 Concept이 없어 건너뜁니다.")
            continue
            
        raw_texts = [rec["text"] for rec in raw_concept_records]
            
        print(f"  -> {len(raw_texts)}개의 문장을 LLM으로 분석합니다...")
        core_concepts = extract_core_concepts_with_llm(raw_texts)
        
        if not core_concepts:
            print("  -> LLM이 핵심 개념을 추출하지 못했습니다.")
            continue
            
        print(f"  -> 추출된 핵심 개념: {[c['name'] for c in core_concepts]}")

        for concept in core_concepts:
            merge_query = """
            MERGE (core:CoreConcept {name: $name})
            ON CREATE SET core.definition = $definition,
                          core.domain = $domain,
                          core.grade = $grade,
                          core.semester = $semester
            
            WITH core
            MATCH (raw:Concept)-[:BELONGS_TO]->(s:AchievementStandard {code: $ach_code})
            WHERE raw.definition IN $raw_definitions
            
            MERGE (raw)-[:IS_EXAMPLE_OF]->(core)
            """
            graph_db.run_query(merge_query, parameters={
                "name": concept["name"], "definition": concept["definition"],
                "domain": standard_record["domain"], 
                "grade": standard_record["grade"], # standard_record에서 직접 가져옴
                "semester": standard_record["semester"], # standard_record에서 직접 가져옴
                "ach_code": ach_code, 
                "raw_definitions": raw_texts
            })
    print("\n핵심 개념 추출 및 연결 작업이 완료되었습니다!")

if __name__ == "__main__":
    db = Neo4jGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    link_concepts(db)
    db.close()