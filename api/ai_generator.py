import os
from openai import OpenAI

def generate_quiz(markdown_content):
    """
    추출된 마크다운 전문을 기반으로 AI에게 퀴즈 및 쪽지시험 생성을 요청합니다.
    [💡 향후 Local LLM 연동 팁]
    Ollama, vLLM 등의 로컬 LLM을 사용하실 경우, 발급키를 무시하고 
    api_base에 해당하는 OPENAI_API_BASE 환경 변수만 "http://localhost:11434/v1" 등으로 변경하시면
    코드 수정 없이 똑같은 OpenAI 규격으로 문제없이 작동합니다!
    """
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE")
    
    if not api_key:
        return "⚠️ 오류: 서버 환경에 'OPENAI_API_KEY' 값이 누락되어 인공지능이 동작할 수 없습니다. Vercel 환경 변수나 .env 파일에 OpenAI 키를 반드시 넣어주세요."
        
    try:
        # 클라이언트 생성 시 Base URL을 옵셔널로 받아들임
        client = OpenAI(
            api_key=api_key,
            base_url=api_base if api_base else "https://api.openai.com/v1"
        )
        
        system_prompt = """
당신은 시험 출제를 전담하는 친절하고 전문적인 1타 강사 선생님입니다. 
제공돤 학생의 '노션 강의 노트 요약본(마크다운)'을 읽고 분석하여, 문서를 완벽히 이해했는지 점검할 수 있는 핵심 예상 문제를 출제해주세요.

[작성 규칙 지침]
1. 가장 중요한 개념을 묻는 객관식 3문제 (보기 4개 포함, 헷갈리기 쉬운 오답 배치)
2. 확실히 암기했는지 체크하는 주관식 (단답형 또는 서술형) 2문제 출제
3. 문제들이 끝난 뒤 빈 줄을 많이 띄워 스포일러를 방지하고, 맨 밑부분에 [💯 정답 및 해설] 블럭을 따로 모아서 상세히 기재할 것.
4. 결과물 전체는 가독성이 아주 좋은 깔끔한 마크다운(.md) 서식으로 응답해 줄 것.
5. 시험에 응하는 학생을 격려하는 부드러운 말투로 시작과 끝을 장식할 것.
"""
        
        response = client.chat.completions.create(
            # 로컬 LLM을 연동하실 경우 이 모델명을 로컬 모델명(예: "llama3")으로 바꾸셔야 합니다.
            model="gpt-4o-mini", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"다음 분석 문서를 바탕으로 쪽지 시험 문제를 5개 만들어 주세요:\n\n{markdown_content}"}
            ],
            temperature=0.6,
            max_tokens=2500
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"> ❌ AI 문제를 점검하던 중 오류가 발생했습니다: {str(e)}\n\nAPI 키가 만료되었거나 한도를 초과했을 수 있습니다."
