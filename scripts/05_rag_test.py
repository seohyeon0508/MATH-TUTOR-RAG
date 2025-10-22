# GraphCypherQAChain을 이용한 간단한 테스트 코드
# AI가 데이터베이스에서 찾아낸 사실 외에는 다른 말을 덧붙이지 못하도록 제한. 최대한 간결하게 답변.
# ex) 선수 지식이 없으면 DB에서 찾을수 없다고 답변.

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_neo4j import GraphCypherQAChain #1.0 ver로 작성함
from langchain_community.graphs import Neo4jGraph
from langchain_core.prompts import PromptTemplate # 👈 프롬프트 템플릿 import

load_dotenv()
NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USER = os.getenv('NEO4J_USER')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

#모델 설정
llm = ChatOpenAI(model='gpt-4o-mini', 
                 temperature=0)

#LangChain 전용 Neo4jGraph 객체 생성
graph = Neo4jGraph(
    url=NEO4J_URI,
    username=NEO4J_USER,
    password=NEO4J_PASSWORD
)

#그래프 스키마 확인
schema = graph.schema
print("그래프 스키마:", schema)

#Cypher 쿼리 생성을 위한 프롬프트 템플릿 정의
CYPHER_GENERATION_TEMPLATE = """
Task:Generate Cypher statement to query a graph database.
Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.
Schema:
{schema}
Note: Do not include any explanations or apologies in your responses.
Do not respond to questions that might ask for anything else than for you to construct a Cypher statement.
Do not include any text except the generated Cypher statement.

# 중요 규칙:
# (a)-[:IS_PREREQUISITE_OF]->(b) 관계는 'a가 b의 선수 지식이다'를 의미합니다.
# 따라서 'b의 선수 지식'을 물으면 a를 찾아야 합니다.

Example Cypher Statements:
Question: 일차방정식의 선수 지식은 뭐야?
Cypher: MATCH (p:CoreConcept)-[:IS_PREREQUISITE_OF]->(t:CoreConcept {{name: '일차방정식'}}) RETURN p.name

Question: {question}
Cypher:"""

cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)

#GraphCypherQAChain 생성 및 실행
#from_llm을 호출할 때 우리가 만든 cypher_prompt를 전달
chain = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    cypher_prompt=cypher_prompt, #커스텀 프롬프트 적용
    verbose=True,
    allow_dangerous_requests=True 
)

question = "일차방정식이 뭐야?"
print(f"질문: {question}")
result = chain.invoke({"query": question})

question2 = "일차방정식의 선수 개념이 뭐야?"
print(f"질문: {question2}")
result2 = chain.invoke({"query": question2})

question3 = "계수 개념이 이해가 안돼. 쉽게 설명해줘."
print(f"질문: {question3}")
result3 = chain.invoke({"query": question3})

question4 = "입체도형의 선수개념이 뭐야?"
print(f"질문: {question4}")
result4 = chain.invoke({"query": question4})


print("\n" + "="*30)
# 결과가 딕셔너리 형태이므로 전체를 출력
print("✅ 최종 답변:")
print('\n'.join([result.get("result"), result2.get("result"), result3.get("result"), result4.get("result")]))
print("="*30 + "\n")