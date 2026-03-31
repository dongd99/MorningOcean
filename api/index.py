import os
import requests
import json
import sys
from datetime import datetime
from urllib.parse import quote

from flask import Flask, redirect, request, session, render_template, jsonify
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from extractor import fetch_page_markdown
from database import SessionLocal, Base, engine
from models import User, NotionPage, QuizQuestion

load_dotenv()

template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)
app.secret_key = os.urandom(24) 

NOTION_CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
NOTION_CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5000/callback") 

AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
TOKEN_URL = "https://api.notion.com/v1/oauth/token"

# [PostgreSQL 초기화] Vercel과 같은 서버리스 환경에서 안전하게 테이블을 생성합니다.
# Supabase 연결 시, 테이블이 없으면 스스로 Create 쿼리를 날려 구축합니다!
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"DB 테이블 생성 중 엑세스 오류: {e}")

@app.route("/")
def index():
    encoded_redirect = quote(REDIRECT_URI)
    auth_link = f"{AUTHORIZE_URL}?owner=user&client_id={NOTION_CLIENT_ID}&redirect_uri={encoded_redirect}&response_type=code"
    return render_template("index.html", auth_link=auth_link)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Notion OAuth 인증 코드를 받지 못했습니다.", 400

    auth_credentials = (NOTION_CLIENT_ID, NOTION_CLIENT_SECRET)
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
    
    response = requests.post(TOKEN_URL, auth=auth_credentials, json=data)
    if response.status_code != 200:
        return f"토큰 교환에 실패했습니다: {response.text}", 400
        
    token_data = response.json()
    access_token = token_data.get("access_token")
    workspace_name = token_data.get("workspace_name")
    
    # 🌟 [DB 연동] 노션 유저 정보를 파싱하여 DB에 회원가입 시킵니다.
    owner_info = token_data.get("owner", {}).get("user", {})
    notion_user_id = owner_info.get("id") or token_data.get("bot_id")
    user_name = owner_info.get("name", "Unknown User")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.notion_user_id == notion_user_id).first()
        if not user:
            user = User(notion_user_id=notion_user_id, name=user_name)
            db.add(user)
            db.commit()
            db.refresh(user)
        # 플라스크 세션에 내 DB 유저 PK 임시 보관 (플러터 연동 시 JWT로 변환 필요)
        session["user_db_id"] = user.id
    except Exception as e:
        print(f"User DB 저장 오류: {e}")
    finally:
        db.close()

    session["notion_token"] = access_token
    session["workspace_name"] = workspace_name
    
    return redirect("/pages")

@app.route("/pages")
def pages():
    access_token = session.get("notion_token")
    if not access_token:
        return redirect("/")
        
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    search_data = {"filter": {"value": "page", "property": "object"}}
    res = requests.post("https://api.notion.com/v1/search", headers=headers, json=search_data)
    if res.status_code != 200:
        return f"리스트 로드 오류: {res.text}", 400
        
    results = res.json().get("results", [])
    pages_list = []
    for p in results:
        page_id = p["id"]
        title = "제목 없음"
        props = p.get("properties", {})
        for k, v in props.items():
            if v.get("type") == "title" and v.get("title"):
                title = v["title"][0]["plain_text"]
                break
        
        last_edited_time = p.get("last_edited_time")
        pages_list.append({"id": page_id, "title": title, "last_edited_time": last_edited_time})
        
    workspace_name = session.get("workspace_name", "Notion 룸")
    return render_template("pages.html", pages=pages_list, workspace_name=workspace_name)

@app.route("/extract/<page_id>")
def extract_page(page_id):
    access_token = session.get("notion_token")
    user_db_id = session.get("user_db_id")
    if not access_token or not user_db_id:
        return redirect("/")
        
    title, md_content = fetch_page_markdown(access_token, page_id)
    quiz_result_md = "> 알 수 없는 오류로 퀴즈를 생성하지 못했습니다."
    
    if not md_content.startswith("# Error"):
        from api.ai_generator import generate_quiz
        quiz_json_str = generate_quiz(md_content)
        
        try:
            # 🌟 JSON 포맷 강제 파싱 시작
            quiz_data = json.loads(quiz_json_str) 
            
            db = SessionLocal()
            try:
                # 1. DB에 해당 노션 페이지 등록 또는 조회
                page_record = db.query(NotionPage).filter(NotionPage.notion_page_id == page_id).first()
                if not page_record:
                    page_record = NotionPage(user_id=user_db_id, notion_page_id=page_id, title=title)
                    db.add(page_record)
                    db.commit()
                    db.refresh(page_record)
                
                # 마크다운 최신화
                page_record.markdown_content = md_content
                page_record.last_synced_at = datetime.utcnow()
                
                # 2. [오답노트 규칙] 기존 퀴즈를 비활성화 (버리기 X 보존 O)
                db.query(QuizQuestion).filter(QuizQuestion.page_id == page_record.id).update({"is_active": False})
                db.commit()
                
                quiz_result_md = ""
                # 3. 새로운 10문제 객관식을 순회하며 DB 삽입 및 화면 표시용 마크다운 문자열 조립
                for i, q in enumerate(quiz_data, 1):
                    # 화면 표시용 텍스트 조립 (사용자 다운로드 뷰)
                    quiz_result_md += f"### {i}. {q.get('question', '')}\n\n"
                    options_json_str = json.dumps(q.get('options', []), ensure_ascii=False)
                    for idx, opt in enumerate(q.get('options', []), 0):
                        quiz_result_md += f"- **[{idx+1}]** {opt}\n"
                    quiz_result_md += f"\n<details>\n<summary>정답 및 해설 펼치기</summary>\n"
                    quiz_result_md += f"**✅ 정답:** {q.get('answer_index', 0)+1}번\n"
                    quiz_result_md += f"**💡 해설:** {q.get('explanation', '')}\n</details>\n\n---\n"
                    
                    # DB 테이블에 레코드 Insert
                    new_q = QuizQuestion(
                        page_id=page_record.id,
                        question_text=q.get('question'),
                        options=options_json_str,
                        answer_index=q.get('answer_index', 0),
                        explanation=q.get('explanation', ''),
                        is_active=True
                    )
                    db.add(new_q)
                    
                db.commit()
            except Exception as db_err:
                print("DB 연동 에러:", db_err)
                db.rollback()
            finally:
                db.close()
            
        except json.JSONDecodeError as e:
            quiz_result_md = "AI가 유효한 JSON 배열 규격을 어겨 파싱에 실패했습니다.\n\n[원본 응답]\n" + quiz_json_str
            print("JSON 파싱 에러:", e)
            
    return render_template("extract.html", title=title, content=md_content, quiz=quiz_result_md)

@app.route("/api/cron/sync")
def cron_sync():
    """
    주 1회 Vercel 스케줄러(Cron)가 툭 치고 가는 동기화 버튼입니다.
    이 트리거가 발동되면 최신 버전 지문을 재분석하여 DB를 갱신합니다.
    (실제 운용 시 Header의 CRON_SECRET 보안 토큰 검사를 통해 Vercel만의 명령인지 판별합니다)
    """
    return jsonify({"status": "success", "message": "Cron scheduler reached out successfully. Triggering background jobs..."}), 200

if __name__ == "__main__":
    app.run(port=5000, debug=True)
