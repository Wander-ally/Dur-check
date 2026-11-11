"""
prepare_data.py
----------------
한국의약품안전관리원 DUR 원본 CSV 3개를 앱에서 쓰기 좋은 작은 CSV 4개로 정리합니다.

[입력]  raw/ 폴더에 아래 이름으로 파일을 넣어 두세요. (다운로드한 파일 이름을 바꾸면 됩니다)
    raw/병용금기.csv     ← 한국의약품안전관리원_병용금기약물_YYYYMMDD.csv
    raw/효능군중복.csv   ← 한국의약품안전관리원_효능군중복주의_YYYYMMDD.csv
    raw/노인주의.csv     ← 한국의약품안전관리원_노인주의_YYYYMMDD.csv

[출력]  data/ 폴더에 생성됩니다.
    data/products.csv       검색용 제품 목록 (제품명 → 성분)
    data/contra_pairs.csv   병용금기 성분 쌍 + 금기 사유
    data/duplication.csv    제품별 효능군·그룹 (효능군중복 점검용)
    data/elderly.csv        노인주의 제품 목록

[실행]  python prepare_data.py
"""

from pathlib import Path
import pandas as pd

RAW = Path("raw")
OUT = Path("data")
OUT.mkdir(exist_ok=True)

# 원본 파일은 한글 인코딩이 cp949입니다. (그냥 읽으면 한글이 깨짐)
ENC = "cp949"


def read_raw(name, **kwargs):
    """raw 폴더의 CSV를 모든 열을 문자열(str)로 읽습니다.
    제품코드를 숫자로 읽으면 앞자리 0이 사라지는 문제가 있어서 str로 고정합니다."""
    return pd.read_csv(RAW / name, encoding=ENC, dtype=str, **kwargs)


def clean_text(s):
    """앞뒤 공백 제거. (원본에 'amlodipine ' 처럼 뒤에 공백이 붙은 경우가 있음)"""
    return s.astype(str).str.strip()


# ---------------------------------------------------------------
# 1. 병용금기
# 원본은 '제품 × 제품' 조합으로 51만 줄, 160MB나 됩니다. (GitHub 업로드 한도 100MB 초과)
# 분석해 보니 "성분코드 A + 성분코드 B" 쌍이 같으면 그 성분의 모든 제품끼리 금기였습니다.
# 그래서 성분 쌍만 남기면 약 2만 줄로 줄어들고, 정보 손실은 없습니다.
# ---------------------------------------------------------------
print("1/3 병용금기 처리 중... (파일이 커서 30초 정도 걸릴 수 있어요)")

combo_cols = ["성분코드A", "성분명A", "제품코드A", "제품명A",
              "성분코드B", "성분명B", "제품코드B", "제품명B", "금기사유"]

pieces = []
products_from_combo = []
# 파일이 커서 20만 줄씩 나눠서 읽습니다(chunksize). 메모리 부족 오류 방지용.
for chunk in read_raw("병용금기.csv", usecols=combo_cols, chunksize=200_000):
    pieces.append(chunk[["성분코드A", "성분명A", "성분코드B", "성분명B", "금기사유"]].drop_duplicates())
    # A쪽, B쪽 제품을 각각 모아서 제품 목록에도 넣습니다.
    for side in ["A", "B"]:
        p = chunk[[f"제품코드{side}", f"제품명{side}", f"성분코드{side}", f"성분명{side}"]]
        p.columns = ["제품코드", "제품명", "성분코드", "성분명"]
        products_from_combo.append(p.drop_duplicates())

contra = pd.concat(pieces).drop_duplicates(["성분코드A", "성분코드B"])
for col in contra.columns:
    contra[col] = clean_text(contra[col])
# 주의: 원본은 (A,B) 한 방향으로만 들어 있습니다. 점검할 때 (B,A)도 확인해야 합니다.
contra.to_csv(OUT / "contra_pairs.csv", index=False, encoding="utf-8-sig")
print(f"   병용금기 성분 쌍: {len(contra):,}개")


# ---------------------------------------------------------------
# 2. 효능군중복
# 같은 효능군 안에서 같은 그룹(같은 계열 약)을 2개 이상 먹으면 '중복'입니다.
# 예) 혈압약 Group 7(칼슘채널차단제)의 amlodipine + s-amlodipine
#
# 원본 데이터의 문제 두 가지를 고칩니다. (보고서 '데이터 정제' 파트에 쓸 내용)
#   (1) 그룹 표기가 'Group 1', 'Group 1,', 'Group 1.' 처럼 섞여 있음 → 'Group 1'로 통일
#   (2) '효능군중복점검코드'의 약 6%가 엑셀에서 숫자로 바뀌어 깨져 있음
#       (예: '396E0003' → '3.96E+03', 엑셀이 지수 표기로 인식)
#       → 이 열은 쓰지 않고, 대신 '효능군 + 그룹'과 '일반명코드'로 점검합니다.
# ---------------------------------------------------------------
print("2/3 효능군중복 처리 중...")

dup_raw = read_raw("효능군중복.csv")
dup = pd.DataFrame({
    "제품코드": clean_text(dup_raw["약품코드"]),
    "제품명": clean_text(dup_raw["품목명"]),
    "성분코드": clean_text(dup_raw["일반명코드"]),
    "성분명": clean_text(dup_raw["일반명"]),
    "효능군": clean_text(dup_raw["효능군"]),
    # 'Group 1,' → 'Group 1' : 끝에 붙은 쉼표·마침표 제거
    "그룹": clean_text(dup_raw["그룹구분"]).str.rstrip(",."),
})
# 복합제는 한 제품이 여러 줄로 들어 있습니다. (성분마다 한 줄, 예: ebastine 줄 + pseudoephedrine 줄)
# 같은 성분인지 비교하는 작업은 check.py에서 '성분명'으로 합니다.
dup = dup.drop_duplicates(["제품코드", "효능군", "그룹", "성분명"])
dup[["제품코드", "효능군", "그룹", "성분명"]].to_csv(
    OUT / "duplication.csv", index=False, encoding="utf-8-sig")
print(f"   효능군중복 대상 제품: {dup['제품코드'].nunique():,}개, "
      f"효능군·그룹 조합: {dup[['효능군', '그룹']].drop_duplicates().shape[0]}개")


# ---------------------------------------------------------------
# 3. 노인주의
# 65세 이상에게 주의가 필요한 성분의 제품 목록입니다.
# 원본에 '주의 사유' 열이 없어서, 사유 설명은 팀에서 성분별로 직접 작성해야 합니다.
# ---------------------------------------------------------------
print("3/3 노인주의 처리 중...")

eld_raw = read_raw("노인주의.csv")
eld = pd.DataFrame({
    "제품코드": clean_text(eld_raw["제품코드"]),
    "제품명": clean_text(eld_raw["제품명"]),
    "성분코드": clean_text(eld_raw["성분코드"]),
    "성분명": clean_text(eld_raw["성분명"]),
}).drop_duplicates("제품코드")
eld[["제품코드", "성분코드", "성분명"]].to_csv(OUT / "elderly.csv", index=False, encoding="utf-8-sig")
print(f"   노인주의 제품: {len(eld):,}개, 성분: {eld['성분명'].nunique()}개")


# ---------------------------------------------------------------
# 4. 검색용 제품 목록 (세 파일에 나온 제품을 모두 합침)
# 한계: DUR 경고가 하나도 없는 약(예: 일반 소화제)은 이 목록에 없습니다.
# ---------------------------------------------------------------
products = pd.concat(
    products_from_combo
    + [dup[["제품코드", "제품명", "성분코드", "성분명"]],
       eld[["제품코드", "제품명", "성분코드", "성분명"]]]
)
for col in products.columns:
    products[col] = clean_text(products[col])
products = products.drop_duplicates("제품코드").sort_values("제품명")
products.to_csv(OUT / "products.csv", index=False, encoding="utf-8-sig")
print(f"\n검색 가능한 제품: {len(products):,}개")

print("\n완료! data/ 폴더 파일 크기:")
for f in sorted(OUT.glob("*.csv")):
    print(f"   {f.name:20s} {f.stat().st_size / 1024 / 1024:6.2f} MB")
