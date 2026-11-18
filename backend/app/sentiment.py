"""리뷰 감성 분석

- 원본 모델: daekeun-ml/koelectra-small-v3-nsmc (네이버 영화 리뷰 NSMC 로 학습)
- scripts/export_onnx.py 로 ONNX 변환 후 INT8 동적 양자화한 모델을 사용함
- 서버에서는 torch 없이 onnxruntime 과 tokenizers 만으로 추론함
- 환경 변수 MODEL_PATH, TOKENIZER_PATH 로 파일 위치를 바꿀 수 있음
"""

import os
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

# 모델과 토크나이저 위치
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = Path(os.getenv("MODEL_PATH", BASE_DIR / "models" / "sentiment_int8.onnx"))
TOKENIZER_PATH = Path(os.getenv("TOKENIZER_PATH", BASE_DIR / "models" / "tokenizer.json"))
MAX_LEN = 128           # 리뷰가 길면 앞 128 토큰만 사용함


class SentimentAnalyzer:
    """ONNX 모델과 토크나이저를 불러와 문장의 감성을 예측함"""

    def __init__(self, model_path: Path = MODEL_PATH, tokenizer_path: Path = TOKENIZER_PATH):
        # 추론 세션
        # - 무료 서버 CPU 에 맞춰 스레드 수를 2개로 제한함
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        self.session = ort.InferenceSession(
            str(model_path), options, providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.tokenizer.enable_truncation(max_length=MAX_LEN)

    def predict(self, text: str) -> dict:
        """문장 하나를 분석해 레이블, 긍정 확률, 신뢰도를 반환함"""
        # 토큰화
        enc = self.tokenizer.encode(text)
        feeds = {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
            "token_type_ids": np.array([enc.type_ids], dtype=np.int64),
        }
        logits = self.session.run(None, feeds)[0][0]

        # 확률 계산
        # - softmax 로 확률로 바꿈 (0번 = 부정, 1번 = 긍정)
        # - 긍정 확률이 0.5 이상이면 긍정으로 판단함
        exp = np.exp(logits - logits.max())
        probs = exp / exp.sum()
        positive = float(probs[1])
        label = "긍정" if positive >= 0.5 else "부정"
        return {
            "label": label,
            "score": round(positive, 4),
            "confidence": round(max(positive, 1 - positive), 4),
        }


_analyzer: SentimentAnalyzer | None = None


def get_analyzer() -> SentimentAnalyzer:
    """모델을 처음 한 번만 불러오고 이후에는 같은 객체를 재사용함"""
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentAnalyzer()
    return _analyzer
