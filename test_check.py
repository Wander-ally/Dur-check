"""
test_check.py
-------------
check.py가 제대로 동작하는지 확인하는 테스트입니다.  실행:  python test_check.py

각 테스트는 "이 약들을 넣으면 이런 결과가 나와야 한다"를 적어 둔 것입니다.
코드를 고친 뒤에는 꼭 다시 실행해서 전부 통과(PASS)하는지 확인하세요.
이 결과는 보고서 '검증' 파트의 근거로 씁니다.
"""

import random
from check import load_data, check_medications

db = load_data()

# 테스트에 쓰는 실제 제품코드 (products.csv에서 찾은 것)
클래리시드 = "644200532"   # clarithromycin
조코나20 = "662503750"     # simvastatin
노바스크5 = "73400360"     # amlodipine 5mg
노바스크10 = "73400390"    # amlodipine 10mg
넥스디핀 = "662503400"     # s-amlodipine
쎄레브렉스100 = "73400290"  # celecoxib (노인주의 성분)
쎄레브렉스200 = "73400280"  # celecoxib
다이아벡스 = "641600360"    # metformin


def kinds(codes, age=None):
    """점검 결과에서 '종류'만 뽑아 리스트로 돌려줍니다."""
    return [r["종류"] for r in check_medications(db, codes, age)]


def test_병용금기_검출():
    assert kinds([클래리시드, 조코나20]) == ["병용금기"]


def test_병용금기_순서_바꿔도_검출():
    # 원본 데이터는 한 방향으로만 저장돼 있으므로, 순서를 바꿔도 잡히는지 확인
    assert kinds([조코나20, 클래리시드]) == ["병용금기"]


def test_효능군중복_검출():
    assert kinds([노바스크5, 넥스디핀]) == ["효능군 중복"]


def test_동일성분_중복은_한번만():
    # 같은 성분 다른 용량 → '동일성분 중복' 하나만 나와야 함 (효능군 중복으로 또 나오면 안 됨)
    assert kinds([노바스크5, 노바스크10]) == ["동일성분 중복"]


def test_노인주의_65세이상만():
    assert kinds([쎄레브렉스100], age=70) == ["노인주의"]
    assert kinds([쎄레브렉스100], age=65) == ["노인주의"]   # 경계값: 65세는 포함
    assert kinds([쎄레브렉스100], age=64) == []
    assert kinds([쎄레브렉스100], age=None) == []          # 나이 모름 → 점검 안 함


def test_문제없는_조합():
    assert kinds([노바스크5, 다이아벡스], age=50) == []


def test_같은제품_두번입력():
    assert kinds([노바스크5, 노바스크5]) == []


def test_금기가_맨앞():
    res = kinds([쎄레브렉스100, 클래리시드, 조코나20], age=70)
    assert res[0] == "병용금기"


def test_전체_병용금기쌍_구현검증():
    """병용금기 성분 쌍 23,619개 전부에 대해, 각 성분의 제품 하나씩을 골라 점검했을 때
    빠짐없이 잡히는지 확인합니다. (구현이 데이터대로 동작하는지 검증. 임상적 타당성 검증은 아님)"""
    p = db["products"]
    code_to_product = dict(zip(p["성분코드"], p["제품코드"]))   # 성분코드 → 대표 제품 하나
    pairs = list(db["contra"].keys())
    missed = [(a, b) for a, b in pairs
              if "병용금기" not in kinds([code_to_product[a], code_to_product[b]])]
    print(f"      병용금기 {len(pairs):,}쌍 중 검출 {len(pairs) - len(missed):,}쌍, 누락 {len(missed)}쌍")
    assert not missed


def test_금기아닌_무작위쌍_오탐검증():
    """병용금기가 아닌 무작위 제품 쌍 2,000개를 넣었을 때 병용금기로 잘못 잡지 않는지 확인합니다."""
    random.seed(0)                      # 매번 같은 무작위 결과가 나오게 고정 (재현성)
    p = db["products"]
    codes, ing = list(p["제품코드"]), dict(zip(p["제품코드"], p["성분코드"]))
    false_alarm = 0
    tested = 0
    while tested < 2000:
        a, b = random.sample(codes, 2)
        if (ing[a], ing[b]) in db["contra"] or (ing[b], ing[a]) in db["contra"]:
            continue                    # 실제 금기 쌍이면 건너뜀
        tested += 1
        if "병용금기" in kinds([a, b]):
            false_alarm += 1
    print(f"      금기 아닌 쌍 {tested:,}개 중 오탐 {false_alarm}개")
    assert false_alarm == 0


def test_확인표_내용():
    from report import make_report_html
    codes = [클래리시드, 조코나20, 쎄레브렉스100]
    res = check_medications(db, codes, age=70)
    html = make_report_html(db, codes, 70, res)
    assert "조코나정20밀리그램" in html            # 약 이름이 들어 있는지
    assert "함께 먹어도 되나요" in html            # 병용금기 질문
    assert "제 나이에 이 약을" in html             # 노인주의 질문
    assert "진단이나 처방을 대신하지 않습니다" in html   # 안전 문구


def test_확인표_문제없을때():
    from report import make_report_html
    html = make_report_html(db, [노바스크5], None, [])
    assert "확인된 문제가 없습니다" in html
    assert "입력 안 함" in html


def test_쉬운설명_찾기():
    from explain import load_explanations, find_explanation
    ex = load_explanations()
    res = check_medications(db, [조코나20, 클래리시드, 노바스크5, 넥스디핀, 쎄레브렉스100], age=70)
    titles = {r["종류"]: find_explanation(ex, r) for r in res}
    assert "콜레스테롤약" in titles["병용금기"]["제목"]   # 순서를 바꿔 넣어도 찾아야 함
    assert "혈압약" in titles["효능군 중복"]["제목"]
    assert "진통소염제" in titles["노인주의"]["제목"]


def test_쉬운설명_빠짐없음():
    """효능군 중복의 모든 효능군, 노인주의의 모든 성분에 설명이 있는지 확인합니다."""
    import pandas as pd
    from explain import load_explanations, find_explanation
    ex = load_explanations()
    for eff in pd.read_csv("data/duplication.csv", dtype=str)["효능군"].str.strip().unique():
        assert find_explanation(ex, {"종류": "효능군 중복", "효능군": eff}), eff
    for ing in pd.read_csv("data/elderly.csv", dtype=str)["성분명"].unique():
        assert find_explanation(ex, {"종류": "노인주의", "성분": [ing]}), ing


def test_확인표_시간표포함():
    from report import make_report_html
    html = make_report_html(db, [노바스크5, 다이아벡스], 50, [],
                            schedule={노바스크5: {"아침": True, "식사": "식후"}})
    assert "복약 시간표" in html and "식후" in html
    html2 = make_report_html(db, [노바스크5], 50, [], schedule={})
    assert "복약 시간표" not in html2                     # 체크한 게 없으면 넣지 않음


def test_만나이_계산():
    from datetime import date
    from check import calc_age
    today = date(2026, 11, 10)
    assert calc_age("19521110", today) == (74, "")      # 오늘이 생일 → 나이 올라감
    assert calc_age("19521111", today) == (73, "")      # 내일이 생일 → 아직 안 올라감
    assert calc_age("19611110", today) == (65, "")      # 노인주의 경계값
    assert calc_age("1952-11-10", today) == (74, "")    # - 를 넣어도 처리
    assert calc_age("", today) == (None, "")            # 비워 두면 나이 모름
    for bad in ["1952111", "19521310", "19520230", "20270101", "abcdefgh", "18000101"]:
        age, err = calc_age(bad, today)
        assert age is None and err, bad                 # 잘못된 입력은 오류 문구
    # 2월 29일생: 평년에는 3월 1일에 나이가 올라감
    assert calc_age("19600229", date(2027, 2, 28))[0] == 66
    assert calc_age("19600229", date(2027, 3, 1))[0] == 67


def test_알약사진_연결():
    # 예시 시나리오에 쓰는 약 9개는 모두 사진이 연결되어야 함 (시연용)
    assert 클래리시드 not in db["pill"]       # 건조시럽은 알약이 아니라 사진 없음이 정상
    for c in [조코나20, 노바스크5, 넥스디핀, 쎄레브렉스100, 다이아벡스,
              "644200550", "652103560", "643900470"]:
        assert db["pill"].get(c, {}).get("사진", "").startswith("https://"), c


# ------ 테스트 실행기: test_로 시작하는 함수를 전부 실행합니다 ------
if __name__ == "__main__":
    tests = [(n, f) for n, f in list(globals().items()) if n.startswith("test_")]
    failed = 0
    for n, f in tests:
        try:
            f()
            print(f"PASS  {n}")
        except AssertionError:
            failed += 1
            print(f"FAIL  {n}")
    print(f"\n{len(tests) - failed}/{len(tests)}개 통과")
