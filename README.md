# 영화 리뷰 감성 분석 서비스

- `backend/`: FastAPI 백엔드 (Render, Docker 배포) · API 문서는 `/docs`
- `frontend/`: Streamlit 프론트엔드 (Streamlit Community Cloud 배포, 실행 파일 `frontend/app.py`)
- `seed/`: 영화 3개와 리뷰 30개를 백엔드에 한 번에 등록하는 스크립트

## 배포 주소

- 프론트엔드: https://movie-review-sentiment-xqy62ufkrprsiwl7j6y63o.streamlit.app
- 백엔드: https://movie-review-api-86vt.onrender.com (API 문서 `/docs`)

## 테스트 데이터 등록

Render 무료 서버는 디스크가 유지되지 않아 재배포되거나 잠들었다 깨면 DB가 초기화됩니다.
배포 사이트에 영화가 없으면 아래 명령으로 영화 3개와 리뷰 30개를 다시 등록하세요 (`requests` 패키지 필요).

```bash
python seed/load_seed.py --url https://movie-review-api-86vt.onrender.com
```

이미 데이터가 있는 상태에서 다시 실행하면 리뷰가 중복으로 들어갑니다.
기존 리뷰를 지우고 다시 넣으려면 `--replace-reviews` 를 붙입니다.
