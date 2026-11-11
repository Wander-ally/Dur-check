"""
check.py
--------
DUR 점검의 핵심 로직입니다. 화면(Streamlit) 코드와 분리해 두어서
화면 없이도 테스트할 수 있게 만들었습니다.

사용 예:
    from check import load_data, search_products, check_medications
    db = load_data()
    search_products(db, "노바스크")              # 제품 검색
    check_medications(db, ["73400360", "662503400"], age=70)   # 점검

점검 항목 (심각도 순)
    1. 병용금기       : 함께 쓰면 안 되는 성분 조합       → '금기'
    2. 동일성분 중복  : 같은 성분을 두 제품으로 먹는 경우  → '주의'
    3. 효능군 중복    : 같은 계열의 다른 약을 겹쳐 먹는 경우 → '주의'
    4. 노인주의       : 65세 이상에게 주의가 필요한 성분  → '주의'
"""

import re
from itertools import combinations
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data"
ELDERLY_AGE = 65


# ---------------------------------------------------------------
# 성분명 정리
# 같은 성분이라도 'amlodipine', 'amlodipine besylate', 'Amlodipine ' 처럼
# 염(salt)·대소문자·공백이 달라서, 이름의 첫 단어만 뽑아 비교합니다.
#   'metformin hydrochloride'                  → {'metformin'}
#   'atorvastatin calcium (as atorvastatin)+metformin hydrochloride'
#                                              → {'atorvastatin', 'metformin'}  (복합제는 '+'로 나눔)
# 한계: 첫 단어가 같지만 다른 성분이거나, 첫 단어가 다르지만 같은 성분인 드문 경우는 못 잡습니다.
# ---------------------------------------------------------------
def ingredient_names(full_name):
    result = set()
    for part in str(full_name).lower().split("+"):
        m = re.search(r"[a-z][a-z\-]*", part)   # 첫 번째 영단어 (하이픈 포함: s-amlodipine)
        if m:
            result.add(m.group())
    return result


# ---------------------------------------------------------------
# 데이터 불러오기: 앱 시작할 때 한 번만 실행합니다.
# 점검을 빠르게 하려고 표(DataFrame)를 사전(dict) 형태로 바꿔 둡니다.
# ---------------------------------------------------------------
def load_data(data_dir=DATA):
    data_dir = Path(data_dir)
    read = lambda name: pd.read_csv(data_dir / name, dtype=str, encoding="utf-8-sig")

    products = read("products.csv")
    contra = read("contra_pairs.csv")
    dup = read("duplication.csv")
    eld = read("elderly.csv")

    db = {"products": products}

    # 제품코드 → 제품 정보
    db["product_info"] = products.set_index("제품코드").to_dict("index")

    # 병용금기: (성분코드A, 성분코드B) → 금기사유
    db["contra"] = {(a, b): r for a, b, r in zip(contra["성분코드A"], contra["성분코드B"], contra["금기사유"])}

    # 효능군중복: 제품코드 → [(효능군, 그룹, 성분명), ...]   (복합제는 여러 개)
    db["dup"] = {}
    for code, eff, grp, name in zip(dup["제품코드"], dup["효능군"], dup["그룹"], dup["성분명"]):
        db["dup"].setdefault(code, []).append((eff, grp, name))

    # 노인주의: 제품코드 → 성분명
    db["elderly"] = dict(zip(eld["제품코드"], eld["성분명"]))

    # 알약 사진·모양 정보: 제품코드 → {"사진", "성상", "모양", "색상", "각인"}
    # (prepare_pill_images.py로 만든 파일. 없으면 사진 없이 동작)
    pill_path = data_dir / "pill_images.csv"
    db["pill"] = (pd.read_csv(pill_path, dtype=str, encoding="utf-8-sig").fillna("")
                  .set_index("제품코드").to_dict("index") if pill_path.exists() else {})
    return db


# ---------------------------------------------------------------
# 제품 검색: 입력한 글자가 제품명에 들어 있는 제품을 찾습니다.
# ---------------------------------------------------------------
def search_products(db, query, limit=30):
    query = query.strip()
    if not query:
        return db["products"].head(0)
    p = db["products"]
    hit = p[p["제품명"].str.contains(query, case=False, regex=False, na=False)]
    return hit.head(limit)


# ---------------------------------------------------------------
# 핵심: 약 목록 점검
# codes : 사용자가 고른 제품코드 리스트
# age   : 나이 (모르면 None → 노인주의 점검 생략)
# 반환  : 점검 결과 리스트. 결과 하나는 아래 형태의 사전입니다.
#   {"종류": "병용금기", "심각도": "금기", "약": ["제품명1", "제품명2"], "내용": "..."}
# ---------------------------------------------------------------
def check_medications(db, codes, age=None):
    codes = list(dict.fromkeys(codes))          # 같은 제품을 두 번 고른 경우 하나만 남김 (순서 유지)
    info = db["product_info"]
    name = lambda c: info[c]["제품명"]
    results = []

    # 약 2개씩 짝지어 모든 조합을 확인합니다. (약 n개 → n×(n-1)/2 쌍)
    for c1, c2 in combinations(codes, 2):
        p1, p2 = info[c1], info[c2]

        # 1) 병용금기: 원본이 한 방향으로만 저장돼 있어서 (A,B)와 (B,A)를 둘 다 찾습니다.
        reason = db["contra"].get((p1["성분코드"], p2["성분코드"])) \
            or db["contra"].get((p2["성분코드"], p1["성분코드"]))
        if reason:
            results.append({"종류": "병용금기", "심각도": "금기",
                            "약": [name(c1), name(c2)], "내용": reason,
                            "성분": [p1["성분명"], p2["성분명"]]})   # 쉬운 설명 찾기용

        # 2) 동일성분 중복: 두 제품에 공통 성분이 있는지
        same = ingredient_names(p1["성분명"]) & ingredient_names(p2["성분명"])
        if same:
            results.append({"종류": "동일성분 중복", "심각도": "주의",
                            "약": [name(c1), name(c2)],
                            "내용": f"같은 성분({', '.join(sorted(same))})이 두 제품에 모두 들어 있어 "
                                    f"과량 복용이 될 수 있습니다."})

        # 3) 효능군 중복: 같은 (효능군, 그룹)인데 성분이 다른 경우
        #    (성분이 같으면 이미 2)번에서 잡았으므로 제외)
        reported = set()
        for eff1, grp1, n1 in db["dup"].get(c1, []):
            for eff2, grp2, n2 in db["dup"].get(c2, []):
                if (eff1, grp1) == (eff2, grp2) and not (ingredient_names(n1) & ingredient_names(n2)) \
                        and (eff1, grp1) not in reported:
                    reported.add((eff1, grp1))
                    results.append({"종류": "효능군 중복", "심각도": "주의",
                                    "약": [name(c1), name(c2)],
                                    "내용": f"두 약이 같은 계열의 {eff1}입니다({n1.strip()} / {n2.strip()}). "
                                            f"효과가 겹쳐 부작용 위험이 커질 수 있습니다.",
                                    "효능군": eff1})   # 쉬운 설명 찾기용

    # 4) 노인주의: 약 하나씩 확인
    if age is not None and age >= ELDERLY_AGE:
        for c in codes:
            if c in db["elderly"]:
                results.append({"종류": "노인주의", "심각도": "주의", "약": [name(c)],
                                "내용": f"{db['elderly'][c].strip()} 성분은 {ELDERLY_AGE}세 이상에서 "
                                        f"주의가 필요한 성분입니다.",
                                "성분": [db['elderly'][c]]})   # 쉬운 설명 찾기용

    # 금기가 먼저 보이도록 정렬
    order = {"금기": 0, "주의": 1}
    results.sort(key=lambda r: order[r["심각도"]])
    return results


# ---------------------------------------------------------------
# 생년월일 8자리 → 만 나이
# 예) calc_age("19520315", date(2026, 11, 10)) → 74
# 잘못된 입력이면 (None, "이유")를 돌려줍니다.
# 만 나이 = 올해 - 태어난 해, 단 올해 생일이 아직 안 지났으면 1을 뺌
# (2월 29일생은 평년에는 3월 1일에 나이가 올라가는 것으로 계산)
# ---------------------------------------------------------------
def calc_age(birth_text, today):
    from datetime import date
    text = str(birth_text).strip().replace("-", "").replace(".", "").replace(" ", "")
    if not text:
        return None, ""
    if not (text.isdigit() and len(text) == 8):
        return None, "생년월일은 숫자 8자리로 입력해 주세요. (예: 19520315)"
    try:
        birth = date(int(text[:4]), int(text[4:6]), int(text[6:]))
    except ValueError:
        return None, "없는 날짜예요. 월·일을 다시 확인해 주세요."
    if birth > today:
        return None, "오늘보다 미래의 날짜예요."
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    if age > 120:
        return None, "태어난 해를 다시 확인해 주세요."
    return age, ""


# 이 파일을 직접 실행하면 간단한 예시를 보여줍니다:  python check.py
if __name__ == "__main__":
    db = load_data()
    example = ["644200532", "662503750", "73400360", "662503400", "73400290"]
    print("예시 약 목록:")
    for c in example:
        print("  -", db["product_info"][c]["제품명"])
    print("\n점검 결과 (70세):")
    for r in check_medications(db, example, age=70):
        print(f"  [{r['심각도']}] {r['종류']}: {' + '.join(r['약'])}\n        → {r['내용']}")
