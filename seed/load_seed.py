"""영화와 리뷰 일괄 등록

실행: python seed/load_seed.py --url http://localhost:8000
      python seed/load_seed.py --url https://<서비스 이름>.onrender.com

- seed_data.json 의 영화와 리뷰를 백엔드 API 로 등록함
- 같은 제목의 영화가 이미 있으면 새로 만들지 않고 그 영화에 리뷰만 추가함
- --replace-reviews: 등록하기 전에 대상 영화의 기존 리뷰를 모두 삭제함 (등록할 리뷰가 있는 영화만)
- 리뷰는 등록할 때 백엔드에서 감성 분석이 자동으로 실행됨
"""

import argparse
import json
from pathlib import Path

import requests

SEED_PATH = Path(__file__).resolve().parent / "seed_data.json"
TIMEOUT = 120           # 무료 서버가 잠들어 있으면 첫 요청이 1분 정도 걸릴 수 있음


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000", help="백엔드 주소")
    parser.add_argument("--replace-reviews", action="store_true",
                        help="등록 전에 대상 영화의 기존 리뷰를 삭제함")
    args = parser.parse_args()
    api = args.url.rstrip("/")

    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    existing = {m["title"]: m["id"] for m in requests.get(f"{api}/movies", timeout=TIMEOUT).json()}

    for movie in seed["movies"]:
        reviews = movie.pop("reviews")

        # 영화 등록 (이미 있으면 기존 영화 사용)
        if movie["title"] in existing:
            movie_id = existing[movie["title"]]
        else:
            resp = requests.post(f"{api}/movies", json=movie, timeout=TIMEOUT)
            resp.raise_for_status()
            movie_id = resp.json()["id"]

        # 기존 리뷰 삭제
        # - 등록할 리뷰가 없는 영화는 건드리지 않음
        if args.replace_reviews and reviews:
            old = requests.get(f"{api}/movies/{movie_id}/reviews", timeout=TIMEOUT).json()
            for r in old:
                requests.delete(f"{api}/reviews/{r['id']}", timeout=TIMEOUT).raise_for_status()

        # 리뷰 등록
        for r in reviews:
            resp = requests.post(f"{api}/reviews", timeout=TIMEOUT,
                                 json={"movie_id": movie_id, **r})
            resp.raise_for_status()

        rating = requests.get(f"{api}/movies/{movie_id}/rating", timeout=TIMEOUT).json()
        print(f"{movie['title']}: 리뷰 {rating['review_count']}개, 평점 {rating['rating']}")


if __name__ == "__main__":
    main()
