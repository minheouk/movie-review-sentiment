"""SQLite 데이터베이스 연결

- SQLAlchemy 엔진과 세션을 만들고 API 요청마다 세션을 나눠 줌
- 환경 변수 DB_PATH 로 DB 파일 위치를 바꿀 수 있음 (기본값: backend/data/movies.db)
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent

# DB 파일 위치
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "movies.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# DB 엔진
# - check_same_thread=False: FastAPI 는 요청마다 다른 스레드를 쓸 수 있어서 같은 스레드 검사를 끔
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, _):
    """SQLite 는 외래 키 기능이 기본으로 꺼져 있어서 연결할 때마다 켬"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """모든 테이블 모델의 부모 클래스"""


def get_db():
    """요청 하나 동안 쓸 DB 세션을 만들고 요청이 끝나면 닫음"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
