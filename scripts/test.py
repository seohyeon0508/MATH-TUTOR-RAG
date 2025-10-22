import os
import json
from collections import Counter

# 🔴 이 경로를 본인의 '원본 데이터' 폴더 경로로 수정해주세요.
RAW_DATA_DIRECTORY = "/Users/Seohyeon/Desktop/math/TL_06.중학교 1학년_03.수학_01.텍스트"

version_counter = Counter()

try:
    filenames = os.listdir(RAW_DATA_DIRECTORY)
    total_files = 0

    print(f"'{RAW_DATA_DIRECTORY}' 폴더의 파일들을 분석합니다...")

    for filename in filenames:
        if filename.endswith(".json"):
            total_files += 1
            file_path = os.path.join(RAW_DATA_DIRECTORY, filename)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                source_info = data.get("source_data_info", {})

                # --- 🔥 여기가 수정된 부분! ---
                # 리스트가 비어있는지(is not empty) 먼저 확인하는 'source_info[...] and' 로직을 추가합니다.
                has_2022 = ('2022_achievement_standard' in source_info and 
                            source_info['2022_achievement_standard'] and 
                            source_info['2022_achievement_standard'][0].strip())
                
                has_2015 = ('2015_achievement_standard' in source_info and 
                            source_info['2015_achievement_standard'] and 
                            source_info['2015_achievement_standard'][0].strip())
                
                if has_2022:
                    version_counter['2022_존재'] += 1
                if has_2015:
                    version_counter['2015_존재'] += 1
                if not has_2022 and not has_2015:
                    version_counter['둘 다 없음'] += 1
    
    print("\n--- 📊 교육과정 버전 분포 분석 결과 ---")
    if total_files > 0:
        print(f"총 {total_files}개의 JSON 파일을 분석했습니다.")
        
        for version, count in version_counter.items():
            percentage = (count / total_files) * 100
            print(f"- '{version}' 파일 수: {count}개 ({percentage:.2f}%)")
        
        print("\n--- 결론 ---")
        count_2022 = version_counter.get('2022_존재', 0)
        if (count_2022 / total_files) > 0.5:
             print("✅ 2022 개정 교육과정 기준 파일이 절반 이상으로, 데이터 일관성을 위해 2022 기준으로 통일하는 것이 좋아 보입니다.")
        else:
             print("⚠️ 2022 개정 교육과정 기준 파일의 비율이 낮습니다. 2022 기준이 없을 경우 2015 기준을 사용하는 등의 대안을 고려해볼 수 있습니다.")

    else:
        print("분석할 JSON 파일이 없습니다.")

except FileNotFoundError:
    print(f"오류: '{RAW_DATA_DIRECTORY}' 경로를 찾을 수 없습니다. 경로를 다시 확인해주세요.")
except Exception as e:
    print(f"분석 중 오류 발생: {e}")
    import os



import os
import json
import re
from collections import Counter

# --- 기준 정보 (Ground Truth) ---
# 2022 개정 교육과정 (중1) 성취기준 전체
STANDARDS_2022_SET = {
    "소인수분해의 뜻을 알고, 자연수를 소인수분해할 수 있다.", "소인수분해를 이용하여 최대공약수와 최소공배수를 구할 수 있다.",
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

# 2015 개정 교육과정 성취기준 전체 (이전에 제공해주신 목록 기반)
STANDARDS_2015_SET = {
    "소인수분해의 뜻을 알고, 자연수를 소인수분해 할 수 있다.", "최대공약수와 최소공배수의 성질을 이해하고, 이를 구할 수 있다.",
    "양수와 음수, 정수와 유리수의 개념을 이해한다.", "정수와 유리수의 대소 관계를 판단할 수 있다.",
    "정수와 유리수의 사칙계산의 원리를 이해하고, 그 계산을 할 수 있다.", "순환소수의 뜻을 알고, 유리수와 순환소수의 관계를 이해한다.",
    "제곱근의 뜻을 알고, 그 성질을 이해한다.", "무리수의 개념을 이해한다.", "실수의 대소 관계를 판단할 수 있다.",
    "근호를 포함한 식의 사칙계산을 할 수 있다.", "다양한 상황을 문자를 사용한 식으로 나타낼 수 있다.", "식의 값을 구할 수 있다.",
    "일차식의 덧셈과 뺄셈의 원리를 이해하고, 그 계산을 할 수 있다.", "방정식과 그 해의 의미를 알고, 등식의 성질을 이해한다.",
    "일차방정식을 풀 수 있고, 이를 활용하여 문제를 해결할 수 있다.", "지수법칙을 이해한다.",
    "다항식의 덧셈과 뺄셈의 원리를 이해하고, 그 계산을 할 수 있다.", "‘(단항식)×(다항식)’, ‘(다항식)÷(단항식)’과 같은 곱셈과 나눗셈의 원리를 이해하고, 그 계산을 할 수 있다.",
    "부등식과 그 해의 의미를 알고, 부등식의 성질을 이해한다.", "일차부등식을 풀 수 있고, 이를 활용하여 문제를 해결할 수 있다.",
    "미지수가 2개인 연립일차방정식을 풀 수 있고, 이를 활용하여 문제를 해결할 수 있다.", "다항식의 곱셈과 인수분해를 할 수 있다.",
    "이차방정식을 풀 수 있고, 이를 활용하여 문제를 해결할 수 있다.", "순서쌍과 좌표를 이해한다.",
    "다양한 상황을 그래프로 나타내고, 주어진 그래프를 해석할 수 있다.", "정비례, 반비례 관계를 이해하고, 그 관계를 표, 식, 그래프로 나타낼 수 있다.",
    "함수의 개념을 이해한다.", "일차함수의 의미를 이해하고, 그 그래프를 그릴 수 있다.", "일차함수의 그래프의 성질을 이해하고, 이를 활용하여 문제를 해결할 수 있다.",
    "일차함수와 미지수가 2개인 일차방정식의 관계를 이해한다.", "두 일차함수의 그래프와 연립일차방정식의 관계를 이해한다.",
    "이차함수의 의미를 이해하고, 그 그래프를 그릴 수 있다.", "이차함수의 그래프의 성질을 이해한다.",
    "점, 선, 면, 각을 이해하고, 점, 직선, 평면의 위치 관계를 설명할 수 있다.", "평행선에서 동위각과 엇각의 성질을 이해한다.",
    "삼각형을 작도할 수 있다.", "삼각형의 합동 조건을 이해하고, 이를 이용하여 두 삼각형이 합동인지 판별할 수 있다.",
    "다각형의 성질을 이해한다.", "부채꼴의 중심각과 호의 관계를 이해하고, 이를 이용하여 부채꼴의 넓이와 호의 길이를 구할 수 있다.",
    "다면체의 성질을 이해한다.", "회전체의 성질을 이해한다.", "입체도형의 겉넓이와 부피를 구할 수 있다.",
    "이등변삼각형의 성질을 이해하고 설명할 수 있다.", "삼각형의 외심과 내심의 성질을 이해하고 설명할 수 있다.",
    "사각형의 성질을 이해하고 설명할 수 있다.", "도형의 닮음의 의미와 닮은 도형의 성질을 이해한다.",
    "삼각형의 닮음 조건을 이해하고, 이를 이용하여 두 삼각형이 닮음인지 판별할 수 있다.", "평행선 사이의 선분의 길이의 비를 구할 수 있다.",
    "피타고라스 정리를 이해하고 설명할 수 있다.", "삼각비의 뜻을 알고, 간단한 삼각비의 값을 구할 수 있다.",
    "삼각비를 활용하여 여러 가지 문제를 해결할 수 있다.", "원의 현에 관한 성질과 접선에 관한 성질을 이해한다.",
    "원주각의 성질을 이해한다.", "자료를 줄기와 잎 그림, 도수분포표, 히스토그램, 도수분포다각형으로 나타내고 해석할 수 있다.",
    "상대도수를 구하며, 이를 그래프로 나타내고, 상대도수의 분포를 이해한다.", "공학적 도구를 이용하여 실생활과 관련된 자료를 수집하고 표나 그래프로 정리하고 해석할 수 있다.",
    "경우의 수를 구할 수 있다.", "확률의 개념과 그 기본 성질을 이해하고, 확률을 구할 수 있다.",
    "중앙값, 최빈값, 평균의 의미를 이해하고, 이를 구할 수 있다.", "분산과 표준편차의 의미를 이해하고, 이를 구할 수 있다.",
    "자료를 산점도로 나타내고, 이를 이용하여 상관관계를 말할 수 있다."
}

# --- 메인 스크립트 ---
RAW_DATA_DIRECTORY = "/Users/Seohyeon/Desktop/math/TL_06.중학교 1학년_03.수학_01.텍스트" 
results_counter = Counter()
unknown_samples = []
total_files = 0

print(f"'{RAW_DATA_DIRECTORY}' 폴더 및 하위 폴더 전체를 분석합니다...")

try:
    for dirpath, _, filenames in os.walk(RAW_DATA_DIRECTORY):
        for filename in filenames:
            if not filename.endswith(".json"): continue
            
            total_files += 1
            file_path = os.path.join(dirpath, filename)
            
            # 파일명 패턴 분석
            filename_pattern = "기타"
            match = re.search(r'_(\d+)\.json', filename)
            if match:
                numeric_part = match.group(1)
                if len(numeric_part) == 7 and numeric_part.startswith('3'):
                    filename_pattern = "3으로 시작 (7자리)"
                elif numeric_part.startswith('09'):
                    filename_pattern = "09로 시작"

            # 내용 출처 분석
            content_origin = "2022 필드 없음"
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                source_info = data.get("source_data_info", {})
                
                if ('2022_achievement_standard' in source_info and 
                    source_info['2022_achievement_standard'] and 
                    source_info['2022_achievement_standard'][0].strip()):
                    
                    full_text = source_info['2022_achievement_standard'][0]
                    match = re.search(r'\]\s*(.*)', full_text)
                    
                    if match:
                        description = match.group(1).strip()
                        
                        is_2022 = description in STANDARDS_2022_SET
                        is_2015 = description in STANDARDS_2015_SET

                        if is_2022 and is_2015: content_origin = '공통 (2015 & 2022)'
                        elif is_2022: content_origin = '2022 버전 고유'
                        elif is_2015: content_origin = '2015 버전 내용'
                        else:
                            content_origin = '알 수 없음'
                            if len(unknown_samples) < 5:
                                unknown_samples.append(description)
                    else: content_origin = '형식 오류'

            results_counter[(filename_pattern, content_origin)] += 1

    # 결과 출력
    print(f"\n--- 📊 분석 완료: 총 {total_files}개 파일 ---")
    results = {}
    for (pattern, origin), count in results_counter.items():
        if pattern not in results: results[pattern] = {}
        results[pattern][origin] = count
            
    for pattern, origin_counts in sorted(results.items()):
        print(f"\n📁 파일명 패턴: '{pattern}'")
        total_pattern_count = sum(origin_counts.values())
        print(f"   - 총 파일 수: {total_pattern_count}개")
        for origin, count in sorted(origin_counts.items()):
            percentage = (count / total_pattern_count) * 100
            print(f"     - {origin}: {count}개 ({percentage:.1f}%)")
    
    if unknown_samples:
        print("\n\n### ❓ '알 수 없는 내용' 샘플 (최대 5개) ###")
        print("이 샘플들은 2015와 2022 목록에 모두 없는 텍스트입니다. (오탈자, 다른 학년 내용 등)")
        for i, sample in enumerate(unknown_samples):
            print(f"{i+1}: {sample}")

except Exception as e:
    print(f"분석 중 오류 발생: {e}")