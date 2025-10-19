import os
import json
import re

def get_latest_standard(source_info):
    """가장 최신 성취기준을 찾아 코드와 설명으로 분리하여 딕셔너리로 반환하는 함수"""
    standard_keys = ['2022_achievement_standard', '2015_achievement_standard', '2009_achievement_standard']
    full_text = ""
    for key in standard_keys:
        if key in source_info and source_info[key][0].strip():
            full_text = source_info[key][0]
            break
    if not full_text:
        return {"code": "N/A", "desc": "N/A"}
    match = re.match(r'\[(.*?)\]\s*(.*)', full_text)
    if match:
        code, desc = match.groups()
        return {"code": code, "desc": desc}
    else:
        return {"code": "N/A", "desc": full_text}

# 경로 설정
DIRECTORY_PATH = "/Users/Seohyeon/Desktop/math/TL_06.중학교 1학년_03.수학_01.텍스트"
# 저장할 파일 경로 설정 
OUTPUT_FILE_PATH = "/Users/Seohyeon/math-tutor-rag/data/processed_data.jsonl" 

# 결과를 저장할 파일을 쓰기('w') 모드로 
with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as outfile:
    for filename in os.listdir(DIRECTORY_PATH):
        if filename.endswith(".json"):
            file_path = os.path.join(DIRECTORY_PATH, filename)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

                achievement_standard = get_latest_standard(data['source_data_info'])
                
                # 저장할 데이터들을 하나의 딕셔너리로 묶기
                processed_record = {
                    "source_file": filename,
                    "grade": data['raw_data_info']['grade'],
                    "semester": data['raw_data_info']['semester'],
                    "achievement_code": achievement_standard['code'],
                    "achievement_desc": achievement_standard['desc'],
                    "text_description": data['learning_data_info']['text_description']
                }

                #json파일 변환해서 하나씩 쓰기
                outfile.write(json.dumps(processed_record, ensure_ascii=False) + '\n')

print(f"'{OUTPUT_FILE_PATH}' 파일 생성이 완료되었습니다!")