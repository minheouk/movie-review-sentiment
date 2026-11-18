"""요청과 응답 데이터 형식

- Pydantic 모델로 입력값을 검사하고 응답 형식을 정함
- description 과 examples 는 FastAPI Docs 에 그대로 표시됨
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# 영화 등록 요청
class MovieCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="영화 제목",
                       examples=["기생충"])
    release_date: date = Field(..., description="개봉일 (YYYY-MM-DD)", examples=["2019-05-30"])
    director: str = Field(..., min_length=1, max_length=100, description="감독",
                          examples=["봉준호"])
    genre: str = Field(..., min_length=1, max_length=100, description="장르",
                       examples=["드라마, 스릴러"])
    poster_url: str = Field(..., min_length=1, max_length=1000,
                            description="포스터 이미지 URL (나무위키 등)",
                            examples=["https://example.com/poster.jpg"])


# 영화 응답
# - from_attributes=True: DB 모델 객체를 그대로 응답 형식으로 바꿀 수 있게 함
# - review_count, average_score 는 DB 컬럼이 아니라 조회할 때 계산해서 채움
class MovieOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="영화 ID")
    title: str = Field(..., description="영화 제목")
    release_date: date = Field(..., description="개봉일")
    director: str = Field(..., description="감독")
    genre: str = Field(..., description="장르")
    poster_url: str = Field(..., description="포스터 이미지 URL")
    created_at: datetime = Field(..., description="등록 시각 (KST)")
    review_count: int = Field(0, description="등록된 리뷰 수")
    average_score: float | None = Field(
        None, description="리뷰 감성 점수(긍정 확률)의 평균, 0~1. 리뷰가 없으면 null")


# 리뷰 등록 요청
class ReviewCreate(BaseModel):
    movie_id: int = Field(..., description="리뷰를 남길 영화 ID", examples=[1])
    author: str = Field(..., min_length=1, max_length=50, description="작성자 이름",
                        examples=["김민혁"])
    content: str = Field(..., min_length=1, max_length=2000, description="리뷰 내용",
                         examples=["배우들 연기가 정말 좋았고 끝까지 긴장감이 넘쳤어요."])


# 리뷰 응답
# - movie_title 은 화면 표시용으로 영화 테이블에서 가져와 채움
class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="리뷰 ID")
    movie_id: int = Field(..., description="영화 ID")
    movie_title: str | None = Field(None, description="영화 제목")
    author: str = Field(..., description="작성자 이름")
    content: str = Field(..., description="리뷰 내용")
    sentiment_label: str = Field(..., description="감성 분석 결과 (긍정 / 부정)")
    sentiment_score: float = Field(..., description="긍정일 확률 (0~1)")
    created_at: datetime = Field(..., description="등록 시각 (KST)")


# 평점 응답
class RatingOut(BaseModel):
    movie_id: int = Field(..., description="영화 ID")
    review_count: int = Field(..., description="평점 계산에 쓴 리뷰 수")
    average_score: float | None = Field(
        None, description="리뷰 감성 점수의 평균 (0~1). 리뷰가 없으면 null")
    rating: float | None = Field(
        None, description="5점 만점으로 환산한 평점 (average_score × 5)")


# 감성 분석 요청과 응답
class SentimentRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="분석할 문장",
                      examples=["시간 가는 줄 모르고 봤어요"])


class SentimentOut(BaseModel):
    label: str = Field(..., description="감성 분석 결과 (긍정 / 부정)")
    score: float = Field(..., description="긍정일 확률 (0~1)")
    confidence: float = Field(..., description="예측한 레이블의 확률 (0.5~1)")


# 삭제 완료, 오류 등 결과 메시지 응답
class Message(BaseModel):
    detail: str = Field(..., description="결과 메시지")
