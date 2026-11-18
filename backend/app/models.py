"""DB 테이블 정의

- movies: 영화 정보
- reviews: 리뷰와 감성 분석 결과
- 영화 1개에 리뷰 여러 개가 달리는 1:N 관계
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    """한국 시간 기준 현재 시각을 반환함 (서버가 UTC 여도 KST 로 저장)"""
    return datetime.now(KST).replace(tzinfo=None, microsecond=0)


# 영화 테이블
class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    release_date: Mapped[date] = mapped_column(Date, nullable=False)
    director: Mapped[str] = mapped_column(String(100), nullable=False)
    genre: Mapped[str] = mapped_column(String(100), nullable=False)
    poster_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst, nullable=False)

    # 리뷰 목록
    # - 영화를 삭제하면 그 영화의 리뷰도 함께 삭제함
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="movie", cascade="all, delete-orphan", passive_deletes=True
    )


# 리뷰 테이블
class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 감성 분석 결과
    # - sentiment_label: "긍정" 또는 "부정"
    # - sentiment_score: 긍정일 확률 (0~1), 영화 평점은 이 값의 평균으로 계산함
    sentiment_label: Mapped[str] = mapped_column(String(10), nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_kst, nullable=False, index=True
    )

    movie: Mapped[Movie] = relationship(back_populates="reviews")
