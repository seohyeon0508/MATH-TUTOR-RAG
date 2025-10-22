import os
import openai
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()
NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USER = os.getenv('NEO4J_USER')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
openai.api_key = os.getenv('OPENAI_API_KEY')

# ============ 선수 관계 규칙 정의 ============
PREREQUISITE_RULES = {
    # 수와 연산
    "유리수": ["정수"],
    "절댓값": ["정수"],
    "소인수분해": ["소수", "약수"],
    "최대공약수": ["소인수분해"],
    "최소공배수": ["소인수분해"],
    
    # 문자와 식
    "곱셈 기호 생략": ["문자를 사용한 식"],
    "계수": ["항"],
    "상수항": ["항"],
    "동류항": ["항", "계수"],
    "다항식": ["항"],
    "일차식": ["다항식", "동류항"],
    
    # 방정식
    "방정식": ["등식의 성질"],
    "항등식": ["등식의 성질"],
    "이항": ["등식의 성질"],
    "일차방정식": ["방정식", "일차식"],
    
    # 좌표와 그래프
    "좌표평면": ["순서쌍"],
    "사분면": ["좌표평면"],
    "대칭인 점의 좌표": ["좌표평면"],
    "그래프": ["좌표평면"],
    "정비례": ["그래프"],
    "반비례": ["그래프", "역수"],
    
    # 도형
    "교점": ["직선"],
    "평행선": ["직선"],
    "동위각": ["평행선"],
    "엇각": ["평행선"],
    "수선": ["직선"],
    "맞꼭지각": ["교점"],
    
    # 다각형
    "내각": ["다각형"],
    "외각": ["다각형"],
    "대각선": ["다각형"],
    "정다각형": ["다각형"],
    "다각형의 내각의 크기의 합": ["내각"],
    "다각형의 외각의 크기의 합": ["외각"],
    "대각선의 개수": ["대각선"],
    
    # 입체도형
    "다면체": ["입체도형"],
    "각기둥": ["다면체"],
    "각뿔": ["다면체"],
    "각뿔대": ["각뿔"],
    "정다면체": ["다면체"],
    "각기둥의 부피": ["각기둥"],
    "각뿔의 부피": ["각뿔"],
    
    # 원
    "원주": ["원"],
    "부채꼴": ["원"],
    "중심각": ["부채꼴"],
    "호의 길이": ["부채꼴", "중심각"],
    "현": ["원"],
    
    # 회전체
    "회전체": ["입체도형"],
    "원기둥": ["회전체"],
    "원뿔": ["회전체"],
    "구": ["회전체"],
    "원기둥의 부피": ["원기둥"],
    "원뿔의 부피": ["원뿔"],
    "구의 부피": ["구"],
    "겉넓이": ["입체도형"],
    
    # 통계
    "계급": ["도수분포표"],
    "계급의 크기": ["계급"],
    "상대도수": ["도수분포표"],
    "히스토그램": ["도수분포표"],
    "도수분포다각형": ["히스토그램"],
    
    # 합동
    "삼각형의 합동 조건": ["합동"],
    "SSS 조건": ["삼각형의 합동 조건"],
    "SAS 조건": ["삼각형의 합동 조건"],
    "ASA 조건": ["삼각형의 합동 조건"],
    "AAS 조건": ["삼각형의 합동 조건"],
    "RHS 조건": ["삼각형의 합동 조건"],
    
        # 도형 기초 (누락된 부분 추가)
    "교선": ["입체도형"],
    "수선": ["평행선"],  # 직선 대신 평행선으로
    "점과 직선 사이의 거리": ["수선"],
    "꼬인 위치": ["평행선"],
    "직교": ["수선"],
    
    # 입체도형 세부
    "정육면체": ["직육면체"],
    "직육면체": ["각기둥"],
    "부피": ["입체도형"],
    "넓이": ["다각형"],
    
    # 문자와 식 세부
    "분배법칙": ["다항식"],
    "음수 대입 시 괄호 사용": ["문자를 사용한 식"],
    
    # 기타
    "대소 관계": ["정수"],
    "부호": ["정수"],
    "속력": ["그래프"],
    "주기 운동": ["그래프"],
    "그래프 해석": ["그래프"],
    "삼각형 작도": ["합동"],
    "줄기와 잎 그림": ["도수분포표"],
}

# ============ 관련 개념 규칙 ============
RELATED_CONCEPTS = {
    ("동위각", "엇각"): "평행선의 성질",
    ("정비례", "반비례"): "함수의 기본 유형",
    ("최대공약수", "최소공배수"): "약수와 배수",
    ("SSS 조건", "SAS 조건"): "삼각형 합동 조건",
    ("ASA 조건", "AAS 조건"): "삼각형 합동 조건",
    ("도수분포표", "히스토그램"): "자료의 정리",
    ("히스토그램", "도수분포다각형"): "자료의 시각화",
    ("양수", "음수"): "수의 부호",
    ("소수", "합성수"): "자연수의 분류",
    ("내각", "외각"): "다각형의 각",
    ("원주", "원주율"): "원의 둘레",
    ("부채꼴", "호의 길이"): "원의 일부",
    ("다면체", "회전체"): "입체도형의 분류",
    ("각기둥", "각뿔"): "다면체의 종류",
    ("원기둥", "원뿔"): "회전체의 종류",
    ("정육면체", "직육면체"): "각기둥의 특수한 형태",
    ("부피", "겉넓이"): "입체도형의 측정",
    ("넓이", "부피"): "도형의 측정",
    ("교점", "교선"): "도형이 만나는 방식",
    ("수선", "점과 직선 사이의 거리"): "수직과 거리",
    ("평행선", "꼬인 위치"): "직선의 위치 관계",
    ("히스토그램", "줄기와 잎 그림"): "자료의 시각화",
    ("속력", "그래프"): "변화량의 표현",
    ("분배법칙", "이항"): "식의 변형",
}

class Neo4jGraph:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self._driver.close()
    
    def run_query(self, query, parameters=None):
        with self._driver.session() as session:
            result = session.run(query, parameters)
            return [record for record in result]


#PREREQUISITE_RULES에 정의된 내용에 따라, 
#개념들 사이에 '선수 지식(IS_PREREQUISITE_OF)' 관계를 생성
def create_prerequisite_relationships(graph_db):
    """규칙 기반 선수 관계 생성"""
    print("=== 선수 관계(IS_PREREQUISITE_OF) 생성 중 ===\n")
    
    created_count = 0
    failed_count = 0
    
    for concept, prerequisites in PREREQUISITE_RULES.items():
        for prereq in prerequisites:
            try:
                query = """
                MATCH (from:CoreConcept {name: $prereq})
                MATCH (to:CoreConcept {name: $concept})
                MERGE (from)-[r:IS_PREREQUISITE_OF]->(to)
                ON CREATE SET 
                    r.confidence = 1.0,
                    r.source = 'rule-based',
                    r.created_at = datetime()
                RETURN from.name AS from_name, to.name AS to_name
                """
                result = graph_db.run_query(query, {
                    "prereq": prereq,
                    "concept": concept
                })
                
                if result:
                    print(f"✓ {prereq} → {concept}")
                    created_count += 1
                else:
                    print(f"✗ 개념을 찾을 수 없음: {prereq} 또는 {concept}")
                    failed_count += 1
                    
            except Exception as e:
                print(f"✗ 오류 ({prereq} → {concept}): {e}")
                failed_count += 1
    
    print(f"\n총 {created_count}개 관계 생성, {failed_count}개 실패\n")

#RELATED_CONCEPTS 규칙에 따라, '관련 개념(RELATED_TO)' 관계를 생성
def create_related_relationships(graph_db):
    """관련 개념 관계 생성"""
    print("=== 관련 개념(RELATED_TO) 관계 생성 중 ===\n")
    
    created_count = 0
    
    for (concept1, concept2), description in RELATED_CONCEPTS.items():
        try:
            query = """
            MATCH (c1:CoreConcept {name: $c1})
            MATCH (c2:CoreConcept {name: $c2})
            MERGE (c1)-[r:RELATED_TO]-(c2)
            ON CREATE SET 
                r.description = $desc,
                r.created_at = datetime()
            RETURN c1.name AS c1_name, c2.name AS c2_name
            """
            result = graph_db.run_query(query, {
                "c1": concept1,
                "c2": concept2,
                "desc": description
            })
            
            if result:
                print(f"✓ {concept1} ↔ {concept2} ({description})")
                created_count += 1
                
        except Exception as e:
            print(f"✗ 오류 ({concept1} ↔ {concept2}): {e}")
    
    print(f"\n총 {created_count}개 관계 생성\n")

def analyze_coverage(graph_db):
    """관계 생성 커버리지 분석"""
    print("=== 커버리지 분석 ===\n")
    
    # 전체 개념 수
    total_query = "MATCH (c:CoreConcept) RETURN count(c) AS total"
    total = graph_db.run_query(total_query)[0]["total"]
    
    # 선수 관계가 있는 개념 수
    with_prereq_query = """
    MATCH (c:CoreConcept)
    WHERE EXISTS((c)-[:IS_PREREQUISITE_OF]->()) 
       OR EXISTS(()-[:IS_PREREQUISITE_OF]->(c))
    RETURN count(DISTINCT c) AS count
    """
    with_prereq = graph_db.run_query(with_prereq_query)[0]["count"]
    
    # 관련 관계가 있는 개념 수
    with_related_query = """
    MATCH (c:CoreConcept)
    WHERE EXISTS((c)-[:RELATED_TO]-())
    RETURN count(DISTINCT c) AS count
    """
    with_related = graph_db.run_query(with_related_query)[0]["count"]
    
    # 고립된 개념 (관계 없음)
    isolated_query = """
    MATCH (c:CoreConcept)
    WHERE NOT EXISTS((c)-[:IS_PREREQUISITE_OF]->())
      AND NOT EXISTS(()-[:IS_PREREQUISITE_OF]->(c))
      AND NOT EXISTS((c)-[:RELATED_TO]-())
    RETURN c.name AS name, c.domain AS domain
    ORDER BY c.domain, c.name
    """
    isolated = graph_db.run_query(isolated_query)
    
    print(f"전체 개념 수: {total}")
    print(f"선수 관계 포함: {with_prereq} ({with_prereq/total*100:.1f}%)")
    print(f"관련 관계 포함: {with_related} ({with_related/total*100:.1f}%)")
    print(f"\n고립된 개념 ({len(isolated)}개):")
    
    current_domain = None
    for record in isolated:
        if record["domain"] != current_domain:
            current_domain = record["domain"]
            print(f"\n[{current_domain}]")
        print(f"  - {record['name']}")

def verify_relationships(graph_db):
    """관계 유효성 검증"""
    print("\n=== 관계 유효성 검증 ===\n")
    
    # 순환 참조 검사
    cycle_query = """
    MATCH path = (c:CoreConcept)-[:IS_PREREQUISITE_OF*]->(c)
    RETURN [node in nodes(path) | node.name] AS cycle
    LIMIT 5
    """
    cycles = graph_db.run_query(cycle_query)
    
    if cycles:
        print(f"⚠️  순환 참조 발견 ({len(cycles)}개):")
        for record in cycles:
            print(f"  {' → '.join(record['cycle'])}")
    else:
        print("✓ 순환 참조 없음")
    
    # 선수 관계 깊이 확인
    depth_query = """
    MATCH (c:CoreConcept)
    OPTIONAL MATCH path = (c)-[:IS_PREREQUISITE_OF*]->(end)
    WHERE NOT EXISTS(()-[:IS_PREREQUISITE_OF]->(c))
    WITH c, length(path) AS depth
    RETURN c.name AS root, max(depth) AS max_depth
    ORDER BY max_depth DESC
    LIMIT 5
    """
    depths = graph_db.run_query(depth_query)
    
    print("\n최대 선수 관계 깊이:")
    for record in depths:
        if record["max_depth"]:
            print(f"  {record['root']}: {record['max_depth']}단계")

if __name__ == "__main__":
    db = Neo4jGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        # 1. 선수 관계 생성
        create_prerequisite_relationships(db)
        
        # 2. 관련 개념 관계 생성
        create_related_relationships(db)
        
        # 3. 커버리지 분석
        analyze_coverage(db)
        
        # 4. 유효성 검증
        verify_relationships(db)
        
        print("\n✅ 모든 작업이 완료되었습니다!")
        
    finally:
        db.close()