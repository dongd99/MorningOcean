import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 💡 [PostgreSQL / Supabase 연동 라인]
# 로컬 PostgreSQL (예: postgresql://user:password@localhost:5432/dbname) 이나
# Supabase 클라우드 주소를 DATABASE_URL 환경 변수에 넣기만 하시면 코드가 알아서 연결됩니다.
# 만약 .env에 아무것도 안 넣으시면, 일단 로컬 테스트용(SQLite)으로 자동 동작하게 만들었습니다!

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notion_quiz_app.db") 

# Vercel 같은 서버리스 환경은 서버가 자꾸 죽고 살고를 반복하므로 `pool_pre_ping=True`로
# 살아있는 DB 선인지 한 번 찔러보고 연결하도록 강제하여 오류를 막습니다.
if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
