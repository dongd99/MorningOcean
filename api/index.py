import os
import requests
from flask import Flask, redirect, request, session, render_template, jsonify
from dotenv import load_dotenv
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from extractor import fetch_page_markdown

load_dotenv()

template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)
# Flask Session(사용자 쿠키)을 암호화하기 위한 시크릿 키
app.secret_key = os.urandom(24) 

NOTION_CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
NOTION_CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")
# 개발자 대시보드에서 등록한 그 주소 복붙
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5000/callback") 

# 노션 공식 OAuth 엔드포인트 주소들
AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
TOKEN_URL = "https://api.notion.com/v1/oauth/token"

@app.route("/")
def index():
    """ 
    일반 브라우저 유저용 첫 관문 페이지.
    [💡 Flutter 연동 시 참고 포인트]
    모바일 앱(Flutter) 환경에서는 웹뷰(Webview) 플러그인이나 url_launcher 등을 통해 아래의 `auth_link` URL 창을 직접 띄워주게 됩니다.
    """
    auth_link = f"{AUTHORIZE_URL}?owner=user&client_id={NOTION_CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code"
    
    # 지금은 웹 테스트용이니까 HTML을 반환합니다.
    return render_template("index.html", auth_link=auth_link)

@app.route("/callback")
def callback():
    """
    사용자가 노션 권한을 수락하고 리디렉션 되어 돌아오는 진입점 (auth code 처리).
    [💡 Flutter 연동 시 참고 포인트]
    Flutter는 App Link/Deep Link(예: myapp://callback)를 통해 이 code 값을 가로채어 백엔드(아래 API)로 POST 전송해주는 형태(API 분리)로 구성합니다.
    """
    code = request.args.get("code")
    if not code:
        return "Notion OAuth 인증 코드를 받지 못했습니다. 앱 내에서 취소 버튼을 누른 것 같습니다.", 400

    # 2. 임시 권한표(code)를 주고 사용자 고유 접근 토큰(access_token) 받아오기
    auth_credentials = (NOTION_CLIENT_ID, NOTION_CLIENT_SECRET)
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
    
    response = requests.post(TOKEN_URL, auth=auth_credentials, json=data)
    if response.status_code != 200:
        return f"토큰 교환에 실패했습니다: {response.text}", 400
        
    token_data = response.json()
    access_token = token_data.get("access_token")
    workspace_name = token_data.get("workspace_name")
    
    # 3. 토큰 보관
    # (Flutter API용이라면 여기서 DB나 토큰 저장소에 유저식별값과 매핑해 넣은 뒤 JSON으로 리턴합니다)
    session["notion_token"] = access_token
    session["workspace_name"] = workspace_name
    
    return redirect("/pages")

@app.route("/pages")
def pages():
    """연동된 (공유된) 사용자의 모든 논션 페이지 목록을 불러옵니다."""
    access_token = session.get("notion_token")
    if not access_token:
        return redirect("/")
        
    # Search API를 사용하여 권한이 허용된 문서를 찾습니다
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    search_data = {
        "filter": {"value": "page", "property": "object"}
    }
    
    res = requests.post("https://api.notion.com/v1/search", headers=headers, json=search_data)
    if res.status_code != 200:
        return f"리스트를 불러오는 도중 오류 발생: {res.text}", 400
        
    results = res.json().get("results", [])
    
    pages_list = []
    for p in results:
        page_id = p["id"]
        title = "제목 없음"
        # 복잡한 프로퍼티 구조에서 타이틀 객체 하나만 빼옵니다
        props = p.get("properties", {})
        for k, v in props.items():
            if v.get("type") == "title" and v.get("title"):
                title = v["title"][0]["plain_text"]
                break
        pages_list.append({"id": page_id, "title": title})
        
    workspace_name = session.get("workspace_name", "Notion 룸")
    return render_template("pages.html", pages=pages_list, workspace_name=workspace_name)

@app.route("/extract/<page_id>")
def extract_page(page_id):
    """
    클릭한 특정 노션 페이지를 변환 처리합니다.
    [💡 Flutter 연동 시 변경 포인트]
    이곳을 JSON Response 처리용 라우트로 바꿉니다:
    `return jsonify({"status": "success", "title": title, "content": md_content})`
    """
    access_token = session.get("notion_token")
    if not access_token:
        return redirect("/")
        
    title, md_content = fetch_page_markdown(access_token, page_id)
    return render_template("extract.html", title=title, content=md_content)

if __name__ == "__main__":
    print("\n==================================")
    print("🚀 플라스크 웹 서버를 기동합니다. ")
    print("👉 브라우저 주소: http://127.0.0.1:5000")
    print("==================================\n")
    app.run(port=5000, debug=True)
