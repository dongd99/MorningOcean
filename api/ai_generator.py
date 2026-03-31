import os
import json
from openai import OpenAI

def generate_quiz(markdown_content):
    """
    마크다운을 바탕으로 AI에게 분석을 시키되, [앱 개발 및 DB 활용]을 위해
    반드시 10개의 '객관식' 문제를 'JSON' 구조로만 반환하도록 강제합니다!
    """
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE")
    
    if not api_key:
        return '{"error": "OPENAI_API_KEY 누락됨"}'
        
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=api_base if api_base else "https://api.openai.com/v1"
        )
        
        system_prompt = """
당신은 시험 출제를 전담하는 강사이자 소프트웨어 데이터 변환기입니다.
제공된 학생의 '노션 강의 노트(마크다운)'를 완벽히 분석하여, 핵심 개념을 묻는 **딱 10개의 4지선다 객관식 문제**를 출제해야 합니다.

[🚨 절대 엄수 규칙 🚨]
1. 오직 10개의 객관식(MULTIPLE_CHOICE)만 만들 것! (주관식 금지)
2. 당신의 응답은 서버 DB 모델과 직결되므로, 절대로 인사말이나 마크다운 코드블록 기호(```json 등)를 붙이지 마세요!
3. 무조건 아래 예시의 **JSON 배열 텍스트 형태**로만 출력하세요!

[예시 구조]
[
  {
    "question": "다음 중 파이썬의 리스트에 대한 설명으로 옳은 것은?",
    "options": ["크기 고정", "수정 불가능", "다양한 자료형 저장 가능", "인덱싱 불가"],
    "answer_index": 2,
    "explanation": "파이썬의 리스트는 서로 다른 자료형 요소를 자유롭게 추가/삭제할 수 있는 가변 컨테이너이기 때문입니다."
  },
  ... (총 10문제)
]
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"다음 문서를 바탕으로 JSON 형태로 10문제를 출제해 줘:\n\n{markdown_content}"}
            ],
            temperature=0.2, # 기계적이고 일관된 JSON을 얻어내기 위해 창의성(온도)을 확 낮춥니다.
            max_tokens=3500
        )
        
        # 앞뒤에 붙은 불필요한 공백이나 마크다운 기호를 떼어냅니다(안전장치).
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json", "", 1).strip()
        if result_text.endswith("```"):
            result_text = result_text[:-3].strip()
            
        return result_text
        
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
