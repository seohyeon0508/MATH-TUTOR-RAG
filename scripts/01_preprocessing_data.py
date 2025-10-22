import os
import json
import re

# --- 기준 정보 (Ground Truth): 진짜 '2022 개정 교육과정 (중1)' 성취기준 내용 ---
STANDARDS_2022_SET = {
    "소인수분해의 뜻을 알고, 자연수를 소인수분해 할 수 있다.", "소인수분해를 이용하여 최대공약수와 최소공배수를 구할 수 있다.",
    "다양한 상황을 이용하여 음수의 필요성을 인식하고, 양수와 음수, 정수와 유리수의 개념을 이해한다.", "정수와 유리수의 대소 관계를 판단할 수 있다.",
    "정수와 유리수의 사칙 계산의 원리를 이해하고, 그 계산을 할 수 있다.", "다양한 상황을 문자를 사용한 식으로 나타내어 그 유용성을 인식하고, 식의 값을 구할 수 있다.",
    "일차식의 덧셈과 뺄셈의 원리를 이해하고, 그 계산을 할 수 있다.", "방정식과 그 해의 뜻을 알고, 등식의 성질을 설명할 수 있다.",
    "일차방정식을 풀 수 있고, 이를 활용하여 문제를 해결할 수 있다.", "순서쌍과 좌표를 이해하고, 그 편리함을 인식할 수 있다.",
    "다양한 상황을 그래프로 나타내고, 주어진 그래프를 해석할 수 있다.", "정비례, 반비례 관계를 이해하고, 그 관계를 표, 식, 그래프로 나타낼 수 있다.",
    "점, 선, 면, 각을 이해하고, 실생활 상황과 연결하여 점, 직선, 평면의 위치 관계를 설명할 수 있다.", "평행선에서 동위각과 엇각의 성질을 이해하고 설명할 수 있다.",
    "삼각형을 작도하고, 그 과정을 설명할 수 있다.", "삼각형의 합동 조건을 이해하고, 이를 이용하여 두 삼각형이 합동인지 판별할 수 있다.",
    "다각형의 성질을 이해하고 설명할 수 있다.", "부채꼴의 중심각과 호의 관계를 이해하고, 이를 이용하여 부채꼴의 호의 길이와 넓이를 구할 수 있다.",
    "구체적인 모형이나 공학 도구를 이용하여 다면체와 회전체의 성질을 탐구하고, 이를 설명할 수 있다.", "입체도형의 겉넓이와 부피를 구할 수 있다.",
    "중앙값, 최빈값의 뜻을 알고, 자료의 특성에 따라 적절한 대푯값을 선택하여 구할 수 있다.", "자료를 줄기와 잎 그림, 도수분포표, 히스토그램, 도수분포다각형으로 나타내고 해석할 수 있다.",
    "상대도수를 구하고, 상대도수의 분포를 표나 그래프로 나타내고 해석할 수 있다.", "통계적 탐구 문제를 설정하고, 공학 도구를 이용하여 자료를 수집하여 분석하고, 그 결과를 해석할 수 있다."
}

# get_true_2022_standard 함수만 이걸로 교체

def get_true_2022_standard(source_info):
    """'내용'과 '코드 형식'을 모두 검사하여 진짜 2022 기준만 반환"""
    key = '2022_achievement_standard'
    if (key in source_info and source_info[key] and source_info[key][0].strip()):
        full_text = source_info[key][0]
        
        desc_match = re.search(r'\]\s*(.*)', full_text)
        code_match = re.match(r'\[(.*?)\]', full_text)

        if desc_match and code_match:
            description = desc_match.group(1).strip()
            code = code_match.group(1).strip()
            
            # 1. 내용(description)이 2022 목록에 있는지 확인
            is_valid_content = description in STANDARDS_2022_SET
            
            # 2. 코드(code)의 도메인 부분이 2022 중1 형식('01'~'04')에 맞는지 확인
            domain_code = code[2:4]
            is_valid_format = domain_code in ["01", "02", "03", "04"]
            
            # 두 조건을 모두 만족해야만 진짜 2022 데이터로 인정!
            if is_valid_content and is_valid_format:
                return {"code": code, "desc": description}

    # 조건을 하나라도 만족하지 못하면 None 반환
    return None

# --- 메인 로직 ---
RAW_DATA_DIRECTORY = "/Users/Seohyeon/Desktop/math/TL_06.중학교 1학년_03.수학_01.텍스트" 
OUTPUT_FILE_PATH = "/Users/Seohyeon/math-tutor-rag/data/processed_data.jsonl" 

with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as outfile:
    print(f"'{RAW_DATA_DIRECTORY}'에서 '진짜 2022' 데이터만 선별하여 추출합니다...")
    total_files = 0
    processed_count = 0
    
    for dirpath, _, filenames in os.walk(RAW_DATA_DIRECTORY):
        for filename in filenames:
            if not filename.endswith(".json"): continue
            total_files += 1
            file_path = os.path.join(dirpath, filename)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                achievement_standard = get_true_2022_standard(data['source_data_info'])
                
                # 진짜 2022 기준이 아닌 파일은 건너뜀
                if achievement_standard is None:
                    continue
                
                processed_record = {
                    "source_file": filename, "grade": data['raw_data_info']['grade'],
                    "semester": data['raw_data_info']['semester'],
                    "achievement_code": achievement_standard['code'],
                    "achievement_desc": achievement_standard['desc'],
                    "text_description": data['learning_data_info']['text_description']
                }
                outfile.write(json.dumps(processed_record, ensure_ascii=False) + '\n')
                processed_count += 1

print(f"\n총 {total_files}개의 파일 중 {processed_count}개의 '진짜 2022' 파일만 처리 완료.")
print(f"'{OUTPUT_FILE_PATH}' 파일 생성이 완료되었습니다!")