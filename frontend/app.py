"""영화 리뷰 감성 분석 Streamlit 웹 서비스

실행: streamlit run app.py

화면 구성
- 영화 목록: 포스터, 제목, 영화 정보, 평점(리뷰 감성 점수 평균)을 보여줌
- 영화 추가: 제목, 개봉일, 감독, 장르, 포스터 URL 을 입력해 영화를 등록함
- 리뷰 등록: 영화를 골라 리뷰를 등록하면 감성 분석 결과를 보여줌
- 최근 리뷰: 최근 등록된 리뷰 10개와 감성 분석 결과를 보여줌

- 모든 데이터는 FastAPI 백엔드에 저장하고 이 앱은 화면 표시와 입력만 맡음
- 백엔드 주소는 BACKEND_URL (Streamlit secrets 또는 환경 변수)로 정함
"""

import os
from datetime import date

import pandas as pd
import requests
import streamlit as st

DEFAULT_BACKEND_URL = "http://localhost:8000"
TIMEOUT = 90            # 무료 서버(Render)가 잠들어 있으면 첫 요청이 1분 정도 걸려서 넉넉히 잡음
PLACEHOLDER_POSTER = "https://placehold.co/300x430?text=No+Image"
COLS_PER_ROW = 4        # 영화 목록 한 줄에 놓을 영화 수


def get_backend_url() -> str:
    """secrets.toml → 환경 변수 → 기본값 순서로 백엔드 주소를 찾음"""
    try:
        url = st.secrets["BACKEND_URL"]
    except Exception:
        url = os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL)
    return url.rstrip("/")


API = get_backend_url()


def api(method: str, path: str, **kwargs):
    """백엔드를 호출하고 (성공 여부, 응답 JSON 또는 오류 메시지)를 반환함"""
    try:
        resp = requests.request(method, f"{API}{path}", timeout=TIMEOUT, **kwargs)
    except requests.RequestException:
        return False, f"백엔드 서버({API})에 연결할 수 없습니다."
    if resp.ok:
        return True, resp.json()

    # 오류 메시지 정리
    # - 입력값 검증 오류(422)는 detail 이 목록이라 "항목: 내용" 형태로 이어 붙임
    try:
        detail = resp.json().get("detail", resp.text)
    except ValueError:
        detail = resp.text
    if isinstance(detail, list):
        detail = ", ".join(f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}" for e in detail)
    return False, f"요청 실패 ({resp.status_code}): {detail}"


def fetch_movies() -> list[dict]:
    """전체 영화 목록을 불러옴 (실패하면 오류를 표시하고 빈 목록 반환)"""
    ok, data = api("GET", "/movies")
    if not ok:
        st.error(data)
        return []
    return data


def poster_html(url: str) -> str:
    """포스터 이미지 HTML 을 만듦

    - referrerpolicy="no-referrer": 외부 사이트에서 이미지를 막는 경우를 피하려고 출처를 보내지 않음
    - 이미지를 불러오지 못하면 대체 이미지를 보여줌
    """
    return (
        f'<img src="{url}" referrerpolicy="no-referrer" '
        f"onerror=\"this.onerror=null;this.src='{PLACEHOLDER_POSTER}';\" "
        'style="width:100%;aspect-ratio:7/10;object-fit:cover;border-radius:8px;">'
    )


def rating_text(movie: dict) -> str:
    """영화 카드의 평점 문구를 만듦 (감성 점수 평균을 5점 만점으로 환산)"""
    if movie["average_score"] is None:
        return "평점 없음 (리뷰 0개)"
    stars = movie["average_score"] * 5
    return f"평점 {stars:.1f} / 5  ·  리뷰 {movie['review_count']}개"


def sentiment_badge(label: str, score: float) -> str:
    """감성 분석 결과를 "긍정 (98%)" 형태로 만듦"""
    confidence = score if label == "긍정" else 1 - score
    return f"{label} ({confidence:.0%})"


def render_movie_list():
    """영화 목록 탭"""
    movies = fetch_movies()
    if not movies:
        st.info("등록된 영화가 없습니다. '영화 추가' 탭에서 영화를 등록해 주세요.")
        return

    # 영화를 격자 형태로 표시함
    for start in range(0, len(movies), COLS_PER_ROW):
        cols = st.columns(COLS_PER_ROW, gap="medium")
        for col, movie in zip(cols, movies[start:start + COLS_PER_ROW]):
            with col:
                st.markdown(poster_html(movie["poster_url"]), unsafe_allow_html=True)
                st.markdown(f"**{movie['title']}**")
                st.caption(f"{movie['release_date']} 개봉 · {movie['director']} · {movie['genre']}")
                st.markdown(rating_text(movie))

                # 이 영화의 리뷰는 접어서 표시함
                with st.expander("리뷰 보기"):
                    render_movie_reviews(movie["id"])

                if st.button("영화 삭제", key=f"del_movie_{movie['id']}"):
                    ok, data = api("DELETE", f"/movies/{movie['id']}")
                    if ok:
                        st.toast(f"'{movie['title']}' 영화를 삭제했습니다.")
                        st.rerun()
                    else:
                        st.error(data)


def render_movie_reviews(movie_id: int):
    """영화 한 편의 리뷰 목록을 표시함"""
    ok, reviews = api("GET", f"/movies/{movie_id}/reviews")
    if not ok:
        st.error(reviews)
        return
    if not reviews:
        st.caption("아직 리뷰가 없습니다.")
        return
    for r in reviews:
        st.markdown(f"**{r['author']}** · {sentiment_badge(r['sentiment_label'], r['sentiment_score'])}")
        st.caption(r["content"])


def render_add_movie():
    """영화 추가 탭"""
    # 입력 폼
    # - clear_on_submit=True: 등록 후 입력칸을 비움
    with st.form("add_movie", clear_on_submit=True):
        title = st.text_input("제목")
        release_date = st.date_input("개봉일", value=date.today(),
                                     min_value=date(1900, 1, 1), max_value=date(2100, 12, 31))
        director = st.text_input("감독")
        genre = st.text_input("장르", placeholder="예: 드라마, 스릴러")
        poster_url = st.text_input("포스터 URL", placeholder="나무위키 등에서 포스터 이미지 주소를 복사해 넣어 주세요")
        submitted = st.form_submit_button("영화 등록", type="primary")

    if submitted:
        # 빈 항목이 있으면 등록하지 않고 안내함
        fields = {"제목": title, "감독": director, "장르": genre, "포스터 URL": poster_url}
        missing = [name for name, value in fields.items() if not value.strip()]
        if missing:
            st.warning(f"다음 항목을 입력해 주세요: {', '.join(missing)}")
            return
        ok, data = api("POST", "/movies", json={
            "title": title.strip(),
            "release_date": release_date.isoformat(),
            "director": director.strip(),
            "genre": genre.strip(),
            "poster_url": poster_url.strip(),
        })
        # 등록 성공 시 결과를 세션에 담고 다시 그림 (영화 목록 탭에도 바로 반영됨)
        if ok:
            st.session_state["added_movie"] = data
            st.rerun()
        st.error(data)

    added = st.session_state.pop("added_movie", None)
    if added:
        st.success(f"'{added['title']}' 영화를 등록했습니다. (영화 ID: {added['id']})")


def render_add_review():
    """리뷰 등록 탭"""
    movies = fetch_movies()
    if not movies:
        st.info("리뷰를 남길 영화가 없습니다. 먼저 영화를 등록해 주세요.")
        return

    # 입력 폼
    # - 영화 선택 목록은 "제목 (개봉 연도)" 형태로 보여줌
    options = {m["id"]: f"{m['title']} ({m['release_date'][:4]})" for m in movies}
    with st.form("add_review", clear_on_submit=True):
        movie_id = st.selectbox("영화 선택", options=list(options), format_func=options.get)
        author = st.text_input("작성자 이름")
        content = st.text_area("리뷰 내용", height=120)
        submitted = st.form_submit_button("리뷰 등록", type="primary")

    if submitted:
        if not author.strip() or not content.strip():
            st.warning("작성자 이름과 리뷰 내용을 모두 입력해 주세요.")
            return
        # 리뷰 등록
        # - 백엔드가 리뷰를 저장하면서 감성 분석을 자동으로 실행함
        with st.spinner("리뷰를 등록하고 감성을 분석하는 중입니다..."):
            ok, data = api("POST", "/reviews", json={
                "movie_id": movie_id, "author": author.strip(), "content": content.strip(),
            })
        if not ok:
            st.error(data)
            return
        # 등록 성공 시 결과를 세션에 담고 다시 그림 (평점과 최근 리뷰에도 바로 반영됨)
        st.session_state["added_review"] = data
        st.rerun()

    # 감성 분석 결과 표시
    added = st.session_state.pop("added_review", None)
    if added:
        st.success(f"'{added['movie_title']}'에 리뷰를 등록했습니다.")
        c1, c2 = st.columns(2)
        c1.metric("감성 분석 결과", sentiment_badge(added["sentiment_label"], added["sentiment_score"]))
        c2.metric("긍정 확률", f"{added['sentiment_score']:.1%}")


def render_recent_reviews():
    """최근 리뷰 탭"""
    ok, reviews = api("GET", "/reviews", params={"limit": 10})
    if not ok:
        st.error(reviews)
        return
    if not reviews:
        st.info("등록된 리뷰가 없습니다.")
        return

    # 최근 리뷰 10개 표
    # - 영화 ID, 등록일, 리뷰 내용, 감성 분석 결과를 표시함
    df = pd.DataFrame([{
        "영화 ID": r["movie_id"],
        "영화 제목": r["movie_title"],
        "등록일": r["created_at"].replace("T", " "),
        "작성자": r["author"],
        "리뷰 내용": r["content"],
        "감성 분석 결과": sentiment_badge(r["sentiment_label"], r["sentiment_score"]),
        "리뷰 ID": r["id"],
    } for r in reviews])
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={"리뷰 내용": st.column_config.TextColumn(width="large")})

    # 리뷰 삭제
    with st.expander("리뷰 삭제"):
        labels = {r["id"]: f"[{r['id']}] {r['movie_title']} - {r['author']}: {r['content'][:30]}"
                  for r in reviews}
        review_id = st.selectbox("삭제할 리뷰", options=list(labels), format_func=labels.get)
        if st.button("선택한 리뷰 삭제"):
            ok, data = api("DELETE", f"/reviews/{review_id}")
            if ok:
                st.toast(data["detail"])
                st.rerun()
            else:
                st.error(data)


# 페이지 설정
st.set_page_config(page_title="영화 리뷰 감성 분석", page_icon="🎬", layout="wide")

# 제목과 안내 문구
# - anchor=False: 제목에 마우스를 올렸을 때 나오는 링크 아이콘을 표시하지 않음
st.title("영화 리뷰 감성 분석", anchor=False)
st.caption("영화를 등록하고 리뷰를 남기면, AI가 리뷰의 감성을 분석해 영화 평점을 계산합니다.")

# 탭 구성
tab_list, tab_add, tab_review, tab_recent = st.tabs(["영화 목록", "영화 추가", "리뷰 등록", "최근 리뷰"])
with tab_list:
    render_movie_list()
with tab_add:
    render_add_movie()
with tab_review:
    render_add_review()
with tab_recent:
    render_recent_reviews()
