"""감성 분석 모델 ONNX 변환과 INT8 경량화

실행: python scripts/export_onnx.py  (backend 폴더에서)
필요 패키지: requirements-export.txt (torch, transformers, onnx 등)

처리 순서
- Hugging Face 에서 원본 모델(daekeun-ml/koelectra-small-v3-nsmc)을 받음
- PyTorch 모델을 FP32 ONNX 파일로 변환함
- 가중치를 INT8 로 바꾸는 동적 양자화로 모델을 경량화함
- NSMC 테스트셋으로 FP32 와 INT8 의 크기, 정확도, 추론 시간을 비교함

- 개발 PC 에서 한 번만 실행함
- 서버에는 결과물인 sentiment_int8.onnx 와 tokenizer.json 만 올라가서 torch, transformers 가 필요 없음
"""

import json
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic
from tokenizers import Tokenizer
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# 원본 모델과 결과 파일 위치
MODEL_ID = "daekeun-ml/koelectra-small-v3-nsmc"
BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "models"
FP32_PATH = OUT_DIR / "sentiment_fp32.onnx"
INT8_PATH = OUT_DIR / "sentiment_int8.onnx"
TOKENIZER_PATH = OUT_DIR / "tokenizer.json"
REPORT_PATH = OUT_DIR / "export_report.json"
MAX_LEN = 128

# 성능 비교용 데이터
# - NSMC 테스트셋 (네이버 영화 리뷰, 0 = 부정 / 1 = 긍정)
NSMC_TEST_URL = "https://raw.githubusercontent.com/e9t/nsmc/master/ratings_test.txt"
EVAL_SAMPLES = 1000


def export_fp32(model, tokenizer):
    """PyTorch 모델을 FP32 ONNX 파일로 변환함

    - dynamic_axes: 문장 길이와 배치 크기가 달라도 같은 모델을 쓸 수 있게 함
    """
    sample = tokenizer("정말 재미있는 영화였어요", return_tensors="pt")
    torch.onnx.export(
        model,
        (sample["input_ids"], sample["attention_mask"], sample["token_type_ids"]),
        str(FP32_PATH),
        input_names=["input_ids", "attention_mask", "token_type_ids"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "token_type_ids": {0: "batch", 1: "seq"},
            "logits": {0: "batch"},
        },
        opset_version=17,
        dynamo=False,
    )


def quantize_int8():
    """FP32 모델의 가중치를 INT8 로 바꿈 (동적 양자화)

    - Windows 에서는 경로에 한글이 있으면 양자화 중 형태 추론 단계가 파일을 못 찾음
    - 그래서 영문 경로인 임시 폴더에서 양자화한 뒤 결과만 복사해 옴
    """
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "fp32.onnx"
        dst = Path(tmp) / "int8.onnx"
        shutil.copy(FP32_PATH, src)
        quantize_dynamic(str(src), str(dst), weight_type=QuantType.QInt8)
        shutil.copy(dst, INT8_PATH)


def load_nsmc_samples(n):
    """NSMC 테스트셋 앞부분 n개를 (문장, 레이블) 목록으로 불러옴 (빈 문장은 제외)"""
    with urllib.request.urlopen(NSMC_TEST_URL) as resp:
        lines = resp.read().decode("utf-8").splitlines()[1:]
    samples = []
    for line in lines:
        _, text, label = line.split("\t")
        if text.strip():
            samples.append((text, int(label)))
        if len(samples) >= n:
            break
    return samples


def evaluate(onnx_path, tokenizer, samples):
    """ONNX 모델의 정확도와 문장 1개당 평균 추론 시간(ms)을 측정함"""
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    correct = 0
    elapsed = 0.0
    for text, label in samples:
        enc = tokenizer.encode(text)
        feeds = {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
            "token_type_ids": np.array([enc.type_ids], dtype=np.int64),
        }
        # 토큰화 시간은 빼고 모델 추론 시간만 잼
        start = time.perf_counter()
        logits = session.run(None, feeds)[0]
        elapsed += time.perf_counter() - start
        correct += int(np.argmax(logits[0]) == label)
    return correct / len(samples), elapsed / len(samples) * 1000


def main():
    OUT_DIR.mkdir(exist_ok=True)

    # 원본 모델 다운로드
    print(f"[1/4] 모델 다운로드: {MODEL_ID}")
    hf_tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID).eval()

    # ONNX 변환과 양자화
    print("[2/4] FP32 ONNX 변환")
    export_fp32(model, hf_tokenizer)

    print("[3/4] INT8 동적 양자화")
    quantize_int8()

    # 토크나이저 저장
    # - 서버에서는 transformers 대신 가벼운 tokenizers 라이브러리만 사용함
    hf_tokenizer.backend_tokenizer.save(str(TOKENIZER_PATH))
    tokenizer = Tokenizer.from_file(str(TOKENIZER_PATH))
    tokenizer.enable_truncation(max_length=MAX_LEN)

    # FP32 와 INT8 비교
    # - 결과는 export_report.json 에 저장함 (보고서 작성용)
    print(f"[4/4] NSMC 테스트셋 {EVAL_SAMPLES}개로 FP32와 INT8 비교")
    samples = load_nsmc_samples(EVAL_SAMPLES)
    torch_size = sum(p.numel() * p.element_size() for p in model.parameters())
    report = {"model_id": MODEL_ID, "eval_samples": len(samples),
              "pytorch_param_mb": round(torch_size / 1024**2, 2)}
    for name, path in [("fp32", FP32_PATH), ("int8", INT8_PATH)]:
        acc, ms = evaluate(path, tokenizer, samples)
        report[name] = {
            "size_mb": round(path.stat().st_size / 1024**2, 2),
            "accuracy": round(acc, 4),
            "latency_ms": round(ms, 2),
        }
        print(f"  {name}: {report[name]}")

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"결과 저장: {REPORT_PATH}")


if __name__ == "__main__":
    main()
