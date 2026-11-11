"""
explain.py
----------
점검 결과마다 '쉬운 설명 카드'를 찾아 줍니다.
설명 내용은 data/explanations.csv에 있습니다. 코드를 몰라도 엑셀·메모장으로 CSV만 고치면
설명을 추가·수정할 수 있습니다. (저장할 때 'CSV UTF-8' 형식 유지)

CSV의 '키' 열 쓰는 법
    병용금기      : 성분A+성분B           예) clarithromycin+simvastatin  (순서 상관없음)
    효능군 중복   : 효능군 이름            예) 당뇨병용제
    노인주의      : 성분;성분;성분 ...      예) celecoxib;ibuprofen
    동일성분 중복 : *                     (모든 동일성분 중복에 같은 설명)
성분 이름은 DUR 성분명(영문)의 일부만 적어도 됩니다. (예: 'ibuprofen'은 'ibuprofen arginine'에도 맞음)
"""

from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data"


def load_explanations(path=DATA / "explanations.csv"):
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    return df.to_dict("records")


def _contains(full_ingredient, key):
    """key(예: 'simvastatin')가 성분명 안에 들어 있는지. 대소문자 무시."""
    return key.strip().lower() in str(full_ingredient).lower()


def find_explanation(explanations, result):
    """점검 결과 하나에 맞는 설명을 찾아 돌려줍니다. 없으면 None."""
    kind = result["종류"]
    for e in explanations:
        if e["종류"] != kind:
            continue
        key = e["키"]

        if kind == "병용금기":
            a, b = key.split("+")
            i1, i2 = result["성분"]
            if (_contains(i1, a) and _contains(i2, b)) or (_contains(i1, b) and _contains(i2, a)):
                return e

        elif kind == "효능군 중복":
            if key.strip() == result.get("효능군", "").strip():
                return e

        elif kind == "노인주의":
            if any(_contains(result["성분"][0], k) for k in key.split(";") if k.strip()):
                return e

        elif kind == "동일성분 중복":
            return e
    return None


def symptoms_list(explanation):
    """'A / B / C' 형태의 증상 문자열을 리스트로 나눕니다. '-'나 빈 칸이면 빈 리스트."""
    text = explanation.get("바로연락할증상", "").strip()
    if text in ("", "-"):
        return []
    return [s.strip() for s in text.split("/") if s.strip()]
