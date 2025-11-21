

# MATH-TUTOR-RAG

**RAG(Retrieval-Augmented Generation) + 지식 그래프 기반 중학교 수학 개인 맞춤형 AI 튜터**

**MATH-TUTOR-RAG**는 2022 개정 교육과정(중학교 1학년 수학) 데이터를 Knowledge Graph로 구조화하여, 
학생의 지식 상태를 진단하고 **개별화된 학습 경로**를 제시하는 AI 튜터링 시스템입니다.
수학은 위계성이 강한 과목으로, 이전 단계의 지식 공백이 현재 학습의 가장 큰 걸림돌이 됩니다. 
본 프로젝트는 LLM의 추론 능력과 Knowledge Graph의 구조적 엄밀성을 결합하여, 
**"학생이 무엇을 모르는지 스스로 인지하지 못할 때에도"** 교육과정 체계에 따라 결손 지식을 찾아내고 보완해주는 것을 목표로 합니다.

---

## ✨ 주요 기능

### 🎯 핵심 특징
- **선수 개념 자동 진단**: 학생이 특정 개념을 질문하면, 이를 이해하기 위해 필요한 선수 지식을 자동으로 탐지하고 확인합니다.
- **적응형 설명 생성**: LLM을 활용하여 학생의 이해도에 따라 설명 방식을 동적으로 조정합니다.
- **지식 그래프 기반 학습 경로**: Neo4j 그래프 DB에 개념 간 선수 관계를 구조화하여 체계적인 학습 경로를 제공합니다.
- **학습 이력 추적**: 학생이 학습한 개념과 설명 횟수를 기록하여 취약 개념을 식별하고 복습을 추천합니다.
- **대화형 인터페이스**: Streamlit 기반의 직관적인 챗봇 UI로 자연스러운 학습 경험을 제공합니다.

### 📊 대화 흐름 예시
```
학생: "일차방정식이 뭐야?"
튜터: "좋은 질문이에요! 일차방정식을 이해하려면 '방정식'과 '일차식' 개념부터 확인해보면 좋은데, 
      혹시 이 개념들은 기억나시나요?"

학생: "방정식은 알아요, 일차식은 잘 모르겠어요."
튜터: [일차식 개념 설명]
      "이 개념이 이해되셨나요? 다음으로 '일차방정식'을 설명해드릴까요?"

학생: "네"
튜터: [일차방정식 개념 설명]
      "더 궁금한 것이 있나요?"
```


---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────┐
│   Streamlit UI      │ ← 사용자 인터페이스
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  Tutor State        │ ← 대화 상태 관리
│  Machine            │    (IDLE/WAITING_DIAGNOSTIC/
└──────────┬──────────┘     WAITING_CONTINUATION 등)
           │
┌──────────▼──────────┐
│  LLM (GPT-4o-mini)  │ ← 의도 분류, 설명 생성
│  - 개념 추출        │
│  - 이해도 평가      │
│  - 맞춤 설명        │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  Neo4j Graph DB     │ ← 지식 그래프
│  - CoreConcept      │    (개념 노드)
│  - IS_PREREQUISITE  │    (선수 관계)
│  - RELATED_TO       │    (관련 관계)
└─────────────────────┘
```

### 데이터 흐름
1. **전처리**: 2022 교육과정 JSON 데이터에서 성취기준 필터링
2. **그래프 구축**: 개념(Concept)과 성취기준(AchievementStandard) 노드 생성
3. **개념 추출**: LLM을 활용하여 핵심 개념(CoreConcept) 병합 및 연결
4. **관계 설정**: 규칙 기반으로 선수 관계(IS_PREREQUISITE_OF) 생성
5. **튜터링**: RAG 방식으로 그래프에서 관련 개념을 검색하여 맞춤 설명 제공

---

## 🛠️ 기술 스택

| 분류 | 기술 |
|------|------|
| **언어** | Python 3.8+ |
| **LLM** | OpenAI GPT-4o-mini |
| **그래프 DB** | Neo4j (on-premise) |
| **프레임워크** | LangChain, Streamlit |
| **시각화** | streamlit-agraph |
| **기타** | dotenv, hashlib, json |

---

## 📦 설치 및 실행

### 1. 환경 설정
```bash
# 저장소 클론
git clone https://github.com/seohyeon0508/MATH-TUTOR-RAG.git
cd MATH-TUTOR-RAG

# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env` 파일 생성 (루트 디렉토리):
```env
# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# Neo4j 설정
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

### 3. Neo4j 설치 및 실행
- [Neo4j Desktop](https://neo4j.com/download/) 다운로드 및 설치
- 새 데이터베이스 생성 (비밀번호 설정)
- 데이터베이스 시작

### 4. 데이터 전처리 및 그래프 구축
```bash
# 1단계: 원본 데이터 전처리
python scripts/01_preprocessing_data.py

# 2단계: Neo4j 그래프 생성
python scripts/02_build_graph.py

# 3단계: 핵심 개념 추출 및 병합
python scripts/03_extract_and_merge_concepts.py

# 4단계: 선수 관계 생성
python scripts/04_create_prerequisite_links.py
```

### 5. 애플리케이션 실행
```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

---

## 📁 프로젝트 구조

```
MATH-TUTOR-RAG/
├── data/                      # 데이터 디렉토리
│   ├── processed_data.jsonl   # 전처리된 학습 데이터
│   └── user_profile.json      # 학생 학습 이력
├── scripts/                   # 파이프라인 스크립트
│   ├── 01_preprocessing_data.py       # 데이터 전처리
│   ├── 02_build_graph.py              # 그래프 초기 구축
│   ├── 03_extract_and_merge_concepts.py  # 핵심 개념 추출
│   ├── 04_create_prerequisite_links.py   # 선수 관계 생성
│   ├── 05_rag_test.py                 # RAG 테스트 (GraphCypherQAChain)
│   └── 06_tutor_rag.py                # 튜터 핵심 로직
├── utils/                     # 유틸리티 함수
│   └── student_profile.py     # 프로필 관리
├── chroma_db/                 # (미사용) 벡터 DB 디렉토리
├── app.py                     # Streamlit 메인 앱
├── .env                       # 환경 변수 (git ignored)
├── .gitignore
└── README.md
```

---

## 🔑 핵심 모듈 설명

### `06_tutor_rag.py` - 튜터 상태 머신
- **`intelligent_tutor()`**: 질문 분석, 선수 개념 탐색, 진단 질문 생성
- **`handle_diagnostic_response()`**: 진단 답변 처리 및 설명 큐 생성
- **`process_turn()`**: 마스터 라우터 (greeting/ask_problem/tutor_flow/chitchat 분류)
- **`classify_continuation_intent()`**: LLM 기반 의도 분류 (continue/skip/re-explain)

### 대화 상태 (State)
- `IDLE`: 대기 상태 (새 질문 수신 대기)
- `WAITING_DIAGNOSTIC`: 선수 지식 진단 중
- `WAITING_CONTINUATION`: "다음 개념 설명해줄까?" 응답 대기
- `POST_EXPLANATION`: 설명 완료 후 추가 질문 대기
- `WAITING_PROBLEM_ANSWER`: 문제 풀이 답변 대기

---

## 📊 그래프 스키마

### 노드 (Node)
- **`CoreConcept`**: 핵심 개념 (예: "일차방정식", "소인수분해")
  - Properties: `name`, `definition`, `domain`, `grade`, `semester`
- **`Concept`**: 원본 교과서 문장 (예시 역할)
  - Properties: `concept_id`, `definition`, `grade`, `semester`
- **`AchievementStandard`**: 성취기준
  - Properties: `code`, `description`, `domain`

### 관계 (Relationship)
- **`IS_PREREQUISITE_OF`**: A가 B의 선수 지식임 (예: 방정식 → 일차방정식)
- **`RELATED_TO`**: 관련 개념 (예: 정비례 ↔ 반비례)
- **`IS_EXAMPLE_OF`**: Concept이 CoreConcept의 예시임
- **`BELONGS_TO`**: Concept이 AchievementStandard에 속함

---

## 🧪 테스트

### RAG 테스트 (GraphCypherQAChain)
```bash
python scripts/05_rag_test.py
```
- LangChain의 GraphCypherQAChain을 사용한 간단한 질의응답 테스트
- Cypher 쿼리 자동 생성 및 실행

### 수동 테스트
```python
from scripts.tutor_rag_06 import process_turn, get_initial_state

state = get_initial_state()
result = process_turn("일차방정식이 뭐야?", state)
print(result["response_text"])
```

---

## 🎓 사용 예시

### 1. 기본 개념 학습
```
학생: "소인수분해가 뭐야?"
튜터: [소인수분해 설명]
      "더 궁금한 것이 있나요?"
```

### 2. 선수 지식 진단
```
학생: "최대공약수 구하는 법 알려줘"
튜터: "좋은 질문이에요! 최대공약수를 제대로 이해하려면 '소인수분해' 개념부터 
      확인해보면 좋은데, 혹시 이 개념은 기억나시나요?"
```

### 3. 문제 풀이
```
학생: "일차방정식 문제 내줘"
튜터: [문제 출제]
학생: "x=4"
튜터: "정답입니다! 🥳 '+3'을 넘기는 '이항' 개념을 정확히 사용하셨네요."
```

### 4. 재설명 요청
```
학생: "아직 이해 안 돼"
튜터: [다른 방식으로 재설명]
```

---

## 🔧 커스터마이징

### 선수 관계 추가
`scripts/04_create_prerequisite_links.py`의 `PREREQUISITE_RULES` 딕셔너리 수정:
```python
PREREQUISITE_RULES = {
    "새개념": ["선수개념1", "선수개념2"],
    # ...
}
```

### LLM 모델 변경
`.env` 파일에서 모델 지정 또는 `tutor_rag_06.py`에서 직접 수정:
```python
llm = ChatOpenAI(model='gpt-4o', temperature=0.3)
```

---

## 🐛 프로젝트 한계 (-2025.11)

1. **교육과정 범위**: 현재 2022 개정 중1 수학만 지원
2. **선수 관계**: 수동으로 정의한 규칙 기반 (일부 누락 가능)
3. **Fallback 모드**: 그래프에 없는 개념은 LLM의 일반 지식으로 대체

---

## 🚀 향후 개선 계획

- [ ] 중2, 중3 교육과정 데이터 추가
- [ ] Chroma DB 를 통한 벡터 검색을 활성화
- [ ] 외부 신뢰할 수 있는 수학 지식 베이스의 추가적인 연동
