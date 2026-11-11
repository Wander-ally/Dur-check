"""
prepare_pill_images.py
----------------------
식약처 '의약품 낱알식별 정보'(raw/낱알식별.csv)에서 우리 앱의 약(data/products.csv)에 해당하는
사진 주소와 모양·색·각인 정보만 골라 data/pill_images.csv로 저장합니다.

[먼저]  python download_pill_info.py   → raw/낱알식별.csv 생성 (API 키 필요, 한 번만)
[실행]  python prepare_pill_images.py  → data/pill_images.csv 생성

연결 방법 (보고서 '데이터' 파트에 쓸 내용)
  1순위: 보험코드(EDI_CODE)가 DUR 제품코드와 같으면 연결
         - DUR 파일은 제품코드 앞자리 0이 빠진 경우가 있어(8자리) 9자리로 맞춰 비교합니다.
         - 낱알식별의 EDI_CODE는 '코드1,코드2'처럼 여러 개일 수 있어 하나씩 나눠 비교합니다.
  2순위: 보험코드로 못 찾으면 제품명이 정확히 같은 경우 연결 (띄어쓰기·포장단위 무시)
사진 파일은 저장하지 않고 식약처 서버의 사진 주소(URL)만 저장합니다.
"""

import re
from pathlib import Path

import pandas as pd

RAW = Path("raw") / "낱알식별.csv"
DATA = Path("data")

pill = pd.read_csv(RAW, dtype=str, encoding="utf-8-sig").fillna("")
products = pd.read_csv(DATA / "products.csv", dtype=str, encoding="utf-8-sig")


def norm_name(name):
    """'노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)' → '노바스크정5밀리그람(암로디핀베실산염)'
    포장 단위를 떼고, 공백·밑줄을 지우고, 소문자로 바꿔 비교하기 쉽게 만듭니다."""
    return re.sub(r"[\s_]", "", str(name).split("_(")[0]).lower()


def info_row(r):
    """낱알식별 한 줄에서 앱에 필요한 정보만 뽑습니다."""
    imprint = " / ".join(x for x in [r["PRINT_FRONT"], r["PRINT_BACK"]] if x)
    color = "·".join(x for x in [r["COLOR_CLASS1"], r["COLOR_CLASS2"]] if x)
    return {"사진": r["ITEM_IMAGE"], "성상": r["CHART"], "모양": r["DRUG_SHAPE"],
            "색상": color, "각인": imprint}


# 1) 보험코드 → 낱알 정보 사전
by_edi = {}
for _, r in pill.iterrows():
    for code in r["EDI_CODE"].split(","):
        code = code.strip()
        if code:
            by_edi.setdefault(code.zfill(9), info_row(r))   # 같은 코드가 여러 번 나오면 처음 것 사용

# 2) 제품명 → 낱알 정보 사전 (보험코드로 못 찾을 때만 사용)
by_name = {}
for _, r in pill.iterrows():
    by_name.setdefault(norm_name(r["ITEM_NAME"]), info_row(r))

rows = []
for _, p in products.iterrows():
    hit = by_edi.get(p["제품코드"].zfill(9))
    how = "보험코드"
    if hit is None:
        hit, how = by_name.get(norm_name(p["제품명"])), "제품명"
    if hit and hit["사진"]:
        rows.append({"제품코드": p["제품코드"], **hit, "연결방법": how})

out = pd.DataFrame(rows)
out.to_csv(DATA / "pill_images.csv", index=False, encoding="utf-8-sig")

n = len(products)
print(f"전체 제품 {n:,}개 중 사진 연결 {len(out):,}개 ({len(out) / n:.1%})")
print(out["연결방법"].value_counts().to_string())
print("(시럽·주사·연고 등 먹는 알약이 아닌 제품은 낱알 사진이 없습니다)")
