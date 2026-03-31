from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import uuid
import datetime
from .database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=generate_uuid)
    notion_user_id = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    pages = relationship("NotionPage", back_populates="owner")
    alarms = relationship("Alarm", back_populates="user")
    answers = relationship("UserAnswer", back_populates="user")

class NotionPage(Base):
    __tablename__ = "notion_pages"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    notion_page_id = Column(String, unique=True, index=True)
    title = Column(String)
    markdown_content = Column(Text)
    
    # 스케줄러(Vercel Cron)가 페이지 내용을 다시 긁어야 할지 판단하는 척도입니다.
    notion_last_edited_time = Column(DateTime)
    last_synced_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    owner = relationship("User", back_populates="pages")
    questions = relationship("QuizQuestion", back_populates="page")

class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    id = Column(String, primary_key=True, default=generate_uuid)
    page_id = Column(String, ForeignKey("notion_pages.id"))
    
    question_text = Column(Text)
    options = Column(Text) # JSON 문자열 형태로 저장 ['보기1', '보기2', ...]
    answer_index = Column(Integer) # 문제 정답이 몇 번째인지 (0, 1, 2, 3)
    explanation = Column(Text) # 해설
    
    # 사용자의 멋진 아이디어 (오답노트 보존용 플래그)
    # 지문이 주 1회 업데이트 될 경우 이 값만 False로 바꿔 새 알람이 안 가도록 하고 기록은 영구 보존!
    is_active = Column(Boolean, default=True) 
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    page = relationship("NotionPage", back_populates="questions")
    answers = relationship("UserAnswer", back_populates="question")
    alarms = relationship("Alarm", back_populates="question")

class UserAnswer(Base):
    """사용자가 맞힌/틀린 오답노트 대시보드를 위한 통계 테이블"""
    __tablename__ = "user_answers"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    question_id = Column(String, ForeignKey("quiz_questions.id"))
    
    selected_option_index = Column(Integer)
    is_correct = Column(Boolean)
    solved_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="answers")
    question = relationship("QuizQuestion", back_populates="answers")

class Alarm(Base):
    """사용자의 폰으로 랜덤 문제를 보낼 예약 알람 테이블"""
    __tablename__ = "alarms"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    question_id = Column(String, ForeignKey("quiz_questions.id"))
    
    alarm_time = Column(DateTime)
    status = Column(String, default="pending") # 대기중(pending), 보냄(sent)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="alarms")
    question = relationship("QuizQuestion", back_populates="alarms")
