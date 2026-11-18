"""영화 리뷰 감성 분석 FastAPI 백엔드

실행: uvicorn app.main:app --reload  (backend 폴더에서)
문서: http://localhost:8000/docs

API 구성
- 영화: 등록, 전체 조회, 특정 영화 조회, 삭제
- 리뷰: 등록(감성 분석 자동 실행), 전체 조회, 특정 영화 리뷰 조회, 삭제
- 평점: 리뷰 감성 점수의 평균
- 감성 분석: 문장 하나를 분석함 (저장하지 않음)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .database import Base, engine
from .routers import movies, reviews
from .schemas import SentimentOut, SentimentRequest
from .sentiment import get_analyzer


# 서버 시작 시 준비 작업
# - DB 테이블이 없으면 만듦
# - 첫 요청이 느리지 않도록 감성 분석 모델을 미리 불러옴
@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    get_analyzer()
    yield


# FastAPI 앱
# - title, description, openapi_tags 는 FastAPI Docs 화면에 표시됨
app = FastAPI(
    title="영화 리뷰 감성 분석 API",
    version="1.0.0",
    description=(
        "영화 정보와 사용자 리뷰를 관리하고, 리뷰의 감성(긍정/부정)을 분석하는 API입니다.\n\n"
        "- **영화**: 등록, 전체 조회, 특정 영화 조회, 삭제\n"
        "- **리뷰**: 등록(감성 분석 자동 실행), 전체 조회, 특정 영화 리뷰 조회, 삭제\n"
        "- **평점**: 리뷰 감성 점수의 평균\n"
        "- **감성 분석**: KoELECTRA-small (NSMC 학습) 모델을 ONNX INT8로 경량화해 사용"
    ),
    openapi_tags=[
        {"name": "영화", "description": "영화 정보 관리"},
        {"name": "리뷰", "description": "리뷰 관리 (등록 시 감성 분석 자동 실행)"},
        {"name": "평점", "description": "리뷰 감성 점수 평균으로 계산한 영화 평점"},
        {"name": "감성 분석", "description": "문장 하나의 감성 분석 (저장하지 않음)"},
        {"name": "상태", "description": "서버 상태 확인"},
    ],
    lifespan=lifespan,
)

# 영화, 리뷰 API 연결
app.include_router(movies.router)
app.include_router(reviews.router)


# 문장 감성 분석
@app.post(
    "/sentiment",
    response_model=SentimentOut,
    tags=["감성 분석"],
    summary="문장 감성 분석",
    description="문장을 받아 긍정/부정과 긍정 확률을 돌려줍니다. 결과는 저장하지 않습니다.",
)
def analyze_sentiment(payload: SentimentRequest):
    return get_analyzer().predict(payload.text)


# 서버 상태 확인
@app.get("/health", tags=["상태"], summary="서버 상태 확인",
         description="서버가 정상 동작하면 status: ok 를 돌려줍니다.")
def health():
    return {"status": "ok"}


# 기본 주소로 접속하면 API 문서로 이동함
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")
