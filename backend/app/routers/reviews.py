"""리뷰 API

- 등록: 리뷰를 저장할 때 감성 분석을 자동으로 실행함
- 조회: 전체 리뷰(최근 순), 특정 리뷰
- 삭제: 특정 리뷰
- 특정 영화의 리뷰 조회는 /movies/{movie_id}/reviews (movies.py) 에 있음
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Movie, Review
from ..schemas import Message, ReviewCreate, ReviewOut
from ..sentiment import get_analyzer

router = APIRouter(prefix="/reviews", tags=["리뷰"])

# Docs 에 표시할 404 응답 설명
NOT_FOUND = {404: {"model": Message, "description": "해당 ID의 리뷰 또는 영화가 없음"}}


def to_review_out(review: Review, movie_title: str | None = None) -> ReviewOut:
    """리뷰 DB 객체를 응답 형식으로 바꾸고 영화 제목을 채움"""
    out = ReviewOut.model_validate(review)
    out.movie_title = movie_title if movie_title is not None else review.movie.title
    return out


def _get_review_or_404(db: Session, review_id: int) -> Review:
    """리뷰를 찾아 반환함 (없으면 404 오류)"""
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"리뷰(ID: {review_id})를 찾을 수 없습니다.")
    return review


# 리뷰 등록
# - 리뷰 내용을 감성 분석한 뒤 결과와 함께 저장함
@router.post(
    "",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="리뷰 등록",
    description="영화 ID, 작성자, 리뷰 내용을 받아 리뷰를 등록합니다. "
                "등록할 때 감성 분석이 자동으로 실행되어 결과(긍정/부정, 긍정 확률)가 함께 저장됩니다.",
    responses=NOT_FOUND,
)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    movie = db.get(Movie, payload.movie_id)
    if movie is None:
        raise HTTPException(status_code=404,
                            detail=f"영화(ID: {payload.movie_id})를 찾을 수 없습니다.")
    result = get_analyzer().predict(payload.content)
    review = Review(
        movie_id=payload.movie_id,
        author=payload.author,
        content=payload.content,
        sentiment_label=result["label"],
        sentiment_score=result["score"],
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return to_review_out(review, movie.title)


# 전체 리뷰 조회
# - 최근 등록 순으로 정렬함
# - joinedload: 영화 제목을 리뷰와 함께 한 번에 불러옴
@router.get(
    "",
    response_model=list[ReviewOut],
    summary="전체 리뷰 조회",
    description="모든 영화의 리뷰를 최근 등록 순으로 돌려줍니다. "
                "limit으로 개수를 정할 수 있습니다 (화면의 '최근 리뷰 10개'는 limit=10).",
)
def list_reviews(
    limit: int | None = Query(None, ge=1, le=1000, description="가져올 최대 개수 (생략하면 전체)"),
    db: Session = Depends(get_db),
):
    query = (select(Review).options(joinedload(Review.movie))
             .order_by(Review.created_at.desc(), Review.id.desc()))
    if limit is not None:
        query = query.limit(limit)
    return [to_review_out(r) for r in db.scalars(query).all()]


# 특정 리뷰 조회
@router.get(
    "/{review_id}",
    response_model=ReviewOut,
    summary="특정 리뷰 조회",
    description="리뷰 ID로 리뷰 하나를 조회합니다.",
    responses=NOT_FOUND,
)
def get_review(review_id: int, db: Session = Depends(get_db)):
    return to_review_out(_get_review_or_404(db, review_id))


# 리뷰 삭제
@router.delete(
    "/{review_id}",
    response_model=Message,
    summary="리뷰 삭제",
    description="리뷰 ID로 리뷰를 삭제합니다.",
    responses=NOT_FOUND,
)
def delete_review(review_id: int, db: Session = Depends(get_db)):
    review = _get_review_or_404(db, review_id)
    db.delete(review)
    db.commit()
    return Message(detail=f"리뷰(ID: {review_id})를 삭제했습니다.")
