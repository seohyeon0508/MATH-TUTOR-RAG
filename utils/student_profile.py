import json
import os
import traceback

# 프로필을 저장할 경로 설정
DATA_DIR = "data"
PROFILE_FILE = os.path.join(DATA_DIR, "user_profile.json")

def log_debug(message: str):
    """디버그용 로그 출력 (06_tutor_rag.py의 것을 임시로 사용)"""
    print(f"🐛 DEBUG (Profile): {message}")

def load_profile() -> dict:
    """
    JSON 파일에서 학생 프로필(학습 기록)을 불러옵니다.
    파일이 없으면 기본값을 반환합니다.
    """
    if not os.path.exists(PROFILE_FILE):
        log_debug("프로필 파일이 없어 새 프로필을 시작합니다.")
        # (중요) explained_concepts는 set으로 반환
        return {"explained_concepts": set(), "explanation_count": {}, "learning_path": {"nodes": [], "edges": []}}
    
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # (매우 중요) JSON에서 list로 읽어온 것을 set으로 다시 변환
            data["explained_concepts"] = set(data.get("explained_concepts", []))
            data.setdefault("explanation_count", {}) # 키가 없을 경우 대비
            data.setdefault("learning_path", {"nodes": [], "edges": []})
            
            log_debug(f"프로필 로드 성공. (학습 개념 {len(data['explained_concepts'])}개)")
            return data
            
    except Exception as e:
        print(f"⚠️ 프로필 로드 실패: {e}")
        traceback.print_exc()
        # 로드 실패 시 안전하게 기본값 반환
        return {"explained_concepts": set(), "explanation_count": {}, "learning_path": {"nodes": [], "edges": []}}
    
def save_profile(state: dict):
    """
    현재 state에서 학습 기록만 추출하여 JSON 파일로 저장합니다.
    """
    # 저장할 데이터만 추출
    profile_data = {
        "explained_concepts": list(state.get("explained_concepts", set())),
        "explanation_count": state.get("explanation_count", {}),
        "learning_path": state.get("learning_path", {"nodes": [], "edges": []}) # <-- 이 줄 추가
    }

    try:
        # data/ 디렉토리가 없으면 생성
        os.makedirs(DATA_DIR, exist_ok=True)
        
        with open(PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=4)
        log_debug("프로필 저장 완료.")
        
    except Exception as e:
        print(f"⚠️ 프로필 저장 실패: {e}")
        traceback.print_exc()