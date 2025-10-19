import json
from neo4j import GraphDatabase
import hashlib
from dotenv import load_dotenv
import os

load_dotenv()

# 환경 변수 읽기
NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USER = os.getenv('NEO4J_USER')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
INPUT_FILE_PATH = "/Users/Seohyeon/math-tutor-rag/data/processed_data.jsonl"

DOMAIN_MAP = {
    "01": "수와 연산",
    "02": "문자와 식",
    "03": "함수",
    "04": "기하",
    "05": "확률과 통계"
}

class Neo4jGraph:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
    def close(self):
        self._driver.close()
    def run_query(self, query, parameters=None):
        with self._driver.session() as session:
            result = session.run(query, parameters)
            # 쓰기/읽기 모두에 대응할 수 있도록 데이터를 반환하고, 호출하는 쪽에서 사용 여부 결정
            return [record for record in result]
    def clear_database(self):
        print("기존 데이터베이스를 초기화합니다...")
        query = "MATCH (n) DETACH DELETE n"
        self.run_query(query)
        print("초기화 완료.")

def build_graph(graph_db):
    graph_db.clear_database()
    print(f"'{INPUT_FILE_PATH}' 파일을 읽어 그래프 생성을 시작합니다...")
    
    total_lines = sum(1 for line in open(INPUT_FILE_PATH, 'r', encoding='utf-8'))
    line_counter = 0
    
    with open(INPUT_FILE_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line_counter += 1
            record = json.loads(line)

            # record에서 데이터를 추출해서 각 변수에 할당
            ach_code = record.get("achievement_code")
            ach_desc = record.get("achievement_desc")
            text_desc = record.get("text_description")
            
            if ach_code == "N/A":
                continue # 성취기준 코드 없으면 건너뛰기? 굳이하지말까..
            
            domain_code = ach_code[2:4]
            domain_name = DOMAIN_MAP.get(domain_code, "기타")
            
            concept_id = "concept_" + hashlib.md5(text_desc.encode()).hexdigest()

            # 쿼리를 하나로 합쳐서 DB 통신을 한 번만 하도록 수정
            combined_query = """
            MERGE (s:AchievementStandard {code: $code})
            SET s.description = $desc, s.domain = $domain, s.grade = $grade, s.semester = $semester

            MERGE (c:Concept {concept_id: $id})
            SET c.name = $name, c.definition = $def, c.grade = $grade, 
                c.semester = $semester, c.domain = $domain, c.text_snippets = [$text]

            MERGE (c)-[:BELONGS_TO]->(s)
            """
            parameters = {
                "code": ach_code, "desc": ach_desc, "domain": domain_name,
                "grade": record.get("grade"), "semester": record.get("semester"),
                "id": concept_id, "name": text_desc[:30] + "...", 
                "def": text_desc, "text": text_desc
            }
            graph_db.run_query(combined_query, parameters)

            if line_counter % 500 == 0:
                print(f"   ... {line_counter} / {total_lines} 라인 처리 중 ...")

    print("그래프 생성이 완료되었습니다!")


if __name__ == "__main__":
    db = Neo4jGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    build_graph(db)
    db.close()