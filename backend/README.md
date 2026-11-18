# 영화 리뷰 감성 분석 API (FastAPI)

영화 정보와 리뷰를 관리하고, 리뷰의 감성(긍정/부정)을 분석하는 백엔드입니다.
API 문서는 `/docs` 에서 볼 수 있습니다.

- 감성 분석 모델: `daekeun-ml/koelectra-small-v3-nsmc` (NSMC 영화 리뷰로 학습)
- 경량화: ONNX 변환 + INT8 동적 양자화 (`scripts/export_onnx.py`)
- DB: SQLite (`data/movies.db`)
- 배포: Render (Docker, 이 폴더의 `Dockerfile` 사용)

## 로컬 실행

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
