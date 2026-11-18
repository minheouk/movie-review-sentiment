# 영화 리뷰 감성 분석 FastAPI 백엔드 이미지 (Render 배포용)
#   빌드: docker build -t movie-review-api .
#   실행: docker run -d -p 10000:10000 movie-review-api
#   접속: http://localhost:10000/docs
FROM python:3.11-slim

# 실행 사용자
# - root 대신 일반 사용자(UID 1000)로 서버를 실행함
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/home/user/app/data/movies.db \
    PORT=10000

WORKDIR /home/user/app

# 의존성 설치
# - 코드만 바뀌면 이 레이어는 캐시를 재사용함
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 앱 코드와 모델 복사
# - 경량화한 INT8 모델과 토크나이저만 넣음 (FP32 모델과 변환 스크립트는 제외)
COPY --chown=user app ./app
COPY --chown=user models/sentiment_int8.onnx models/tokenizer.json ./models/

# 포트
# - Render 는 실행할 때 PORT 환경 변수로 포트를 알려줌 (기본값 10000)
EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
