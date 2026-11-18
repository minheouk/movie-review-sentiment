"""영화 API

- 영화: 등록, 전체 조회, 특정 영화 조회, 삭제
- 특정 영화의 리뷰 조회, 평점 조회도 /movies 주소 아래에 둠
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Movie, Review
from ..schemas import Message, MovieCreate, MovieOut, RatingOut, ReviewOut
from .reviews import to_review_out

# 라우터
# - 리뷰, 평점 API 도 /movies 아래에 있어서 Docs 분류(tags)는 API 마다 따로 붙임
router = APIRouter(prefix="/movies")
MOVIE_TAG = ["영화"]

# Docs 에 표시할 404 응답 설명
NOT_FOUND = {404: {"model": Message, "description": "해당 ID의 영화가 없음"}}

Stats = tuple[int, float | None]  # (리뷰 수, 감성 점수 평균)
EMPTY_STATS: Stats = (0, None)


def _review_stats(db: Session, movie_ids: list[int]) -> dict[int, Stats]:
    """영화별 리뷰 수와 감성 점수 평균을 한 번의 쿼리로 계산함"""
    if not movie_ids:
        return {}
    rows = db.execute(
        select(Review.movie_id, func.count(Review.id), func.avg(Review.sentiment_score))
        .where(Review.movie_id.in_(movie_ids))
        .group_by(Review.movie_id)
    ).all()
    return {movie_id: (count, avg) for movie_id, count, avg in rows}


def _round(value: float | None, digits: int) -> float | None:
    """값이 있을 때만 반올림함"""
    return round(value, digits) if value is not None else None


def _to_movie_out(movie: Movie, stats: Stats | None) -> MovieOut:
    """영화 DB 객체를 응답 형식으로 바꾸고 리뷰 수와 감성 점수 평균을 채움"""
    count, avg = stats or EMPTY_STATS
    out = MovieOut.model_validate(movie)
    out.review_count = count
    out.average_score = _round(avg, 4)
    return out


def _get_movie_or_404(db: Session, movie_id: int) -> Movie:
    """영화를 찾아 반환함 (없으면 404 오류)"""
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail=f"영화(ID: {movie_id})를 찾을 수 없습니다.")
    return movie


# 영화 등록
@router.post(
    "",
    response_model=MovieOut,
    status_code=status.HTTP_201_CREATED,
    summary="영화 등록",
    description="제목, 개봉일, 감독, 장르, 포스터 URL을 받아 새 영화를 등록합니다.",
    tags=MOVIE_TAG,
)
def create_movie(payload: MovieCreate, db: Session = Depends(get_db)):
    movie = Movie(**payload.model_dump())
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return _to_movie_out(movie, None)


# 전체 영화 조회
# - 개봉일이 빠른 순으로 정렬하고 (개봉일이 같으면 먼저 등록한 순) 영화마다 리뷰 수와 감성 점수 평균을 함께 보냄
@router.get(
    "",
    response_model=list[MovieOut],
    summary="전체 영화 조회",
    description="등록된 모든 영화를 개봉일 순으로 돌려줍니다. "
                "영화마다 리뷰 수와 감성 점수 평균이 함께 들어 있습니다.",
    tags=MOVIE_TAG,
)
def list_movies(db: Session = Depends(get_db)):
    movies = db.scalars(select(Movie).order_by(Movie.release_date, Movie.id)).all()
    stats = _review_stats(db, [m.id for m in movies])
    return [_to_movie_out(m, stats.get(m.id)) for m in movies]


# 특정 영화 조회
@router.get(
    "/{movie_id}",
    response_model=MovieOut,
    summary="특정 영화 조회",
    description="영화 ID로 영화 한 편의 정보를 조회합니다.",
    responses=NOT_FOUND,
    tags=MOVIE_TAG,
)
def get_movie(movie_id: int, db: Session = Depends(get_db)):
    movie = _get_movie_or_404(db, movie_id)
    return _to_movie_out(movie, _review_stats(db, [movie_id]).get(movie_id))


# 특정 영화 삭제
# - 그 영화에 달린 리뷰도 함께 삭제됨 (models.py 의 cascade 설정)
@router.delete(
    "/{movie_id}",
    response_model=Message,
    summary="특정 영화 삭제",
    description="영화를 삭제합니다. 그 영화에 달린 리뷰도 함께 삭제됩니다.",
    responses=NOT_FOUND,
    tags=MOVIE_TAG,
)
def delete_movie(movie_id: int, db: Session = Depends(get_db)):
    movie = _get_movie_or_404(db, movie_id)
    db.delete(movie)
    db.commit()
    return Message(detail=f"영화(ID: {movie_id})를 삭제했습니다.")


# 특정 영화의 리뷰 조회
@router.get(
    "/{movie_id}/reviews",
    response_model=list[ReviewOut],
    summary="특정 영화의 리뷰 조회",
    description="한 영화에 달린 리뷰를 최근 등록 순으로 돌려줍니다.",
    responses=NOT_FOUND,
    tags=["리뷰"],
)
def list_movie_reviews(movie_id: int, db: Session = Depends(get_db)):
    movie = _get_movie_or_404(db, movie_id)
    reviews = db.scalars(
        select(Review).where(Review.movie_id == movie_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
    ).all()
    return [to_review_out(r, movie.title) for r in reviews]


# 평점 조회
# - 평점 = 리뷰 감성 점수(긍정 확률)의 평균
# - 화면 표시용으로 5점 만점으로 환산한 값도 함께 보냄
@router.get(
    "/{movie_id}/rating",
    response_model=RatingOut,
    summary="평점 조회",
    description="리뷰 감성 점수(긍정 확률, 0~1)의 평균을 영화 평점으로 돌려줍니다. "
                "5점 만점으로 환산한 값(rating)도 함께 들어 있습니다.",
    responses=NOT_FOUND,
    tags=["평점"],
)
def get_rating(movie_id: int, db: Session = Depends(get_db)):
    _get_movie_or_404(db, movie_id)
    count, avg = _review_stats(db, [movie_id]).get(movie_id, EMPTY_STATS)
    return RatingOut(
        movie_id=movie_id,
        review_count=count,
        average_score=_round(avg, 4),
        rating=_round(avg * 5, 2) if avg is not None else None,
    )
