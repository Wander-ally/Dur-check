"""
download_pill_info.py
---------------------
식약처 '의약품 낱알식별 정보' API에서 전체 데이터를 내려받아 CSV 한 파일로 저장합니다.
딱 한 번만 실행하면 됩니다. 앱은 이 CSV를 쓰기 때문에, 앱을 실행할 때는 API 키가 필요 없습니다.

[실행]   python download_pill_info.py
         → API 키를 물어보면 붙여넣고 엔터
[결과]   raw/낱알식별.csv

주의: API 키를 이 코드 안에 적지 마세요. (GitHub에 올라가면 키가 공개됩니다)
      그래서 실행할 때마다 직접 입력하도록 만들었습니다.
추가 설치가 필요 없도록 파이썬 기본 기능(urllib, csv, json)만 사용했습니다.
"""

import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService03/getMdcinGrnIdntfcInfoList03"
ROWS = 100                       # 한 번에 받을 개수 (API 최대값)
OUT = Path("raw") / "낱알식별.csv"


def fetch_page(key, page):
    """한 페이지(100개)를 받아 (전체 개수, 항목 리스트)를 돌려줍니다."""
    query = urllib.parse.urlencode({"serviceKey": key, "type": "json",
                                    "numOfRows": ROWS, "pageNo": page})
    with urllib.request.urlopen(f"{URL}?{query}", timeout=30) as resp:
        text = resp.read().decode("utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 키가 틀리거나 아직 활성화되지 않으면 JSON 대신 XML 오류 메시지가 옵니다.
        raise RuntimeError("서버가 오류를 보냈어요:\n" + text[:400])
    body = data["body"]
    items = body.get("items") or []
    if isinstance(items, dict):              # {"item": [...]} 형태로 오는 경우 대비
        items = items.get("item", [])
    if isinstance(items, dict):              # 항목이 1개면 리스트가 아닐 수 있음
        items = [items]
    return int(body["totalCount"]), items


def fetch_with_retry(key, page, tries=3):
    """일시적인 접속 오류가 나면 3번까지 다시 시도합니다."""
    for i in range(tries):
        try:
            return fetch_page(key, page)
        except RuntimeError:
            raise                            # 키 오류는 다시 시도해도 소용없음
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"   {page}쪽 접속 실패({e}), 3초 뒤 다시 시도...")
            time.sleep(3)


def main():
    key = input("공공데이터포털 API 키(일반 인증키)를 붙여넣고 엔터: ").strip()
    total, rows = fetch_with_retry(key, 1)
    pages = (total + ROWS - 1) // ROWS
    print(f"전체 {total:,}개, {pages}쪽을 받습니다. (몇 분 걸려요)")

    for page in range(2, pages + 1):
        _, items = fetch_with_retry(key, page)
        rows.extend(items)
        if page % 20 == 0 or page == pages:
            print(f"   {page}/{pages}쪽 완료 ({len(rows):,}개)")
        time.sleep(0.1)                      # 서버에 부담을 주지 않도록 잠깐 쉼

    # 항목마다 열 이름이 조금씩 다를 수 있어서, 나온 열 이름을 모두 모아 표를 만듭니다.
    columns = list(dict.fromkeys(k for r in rows for k in r))
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n완료! {OUT} 에 {len(rows):,}개 저장했어요. 이 파일을 Claude에게 올려 주세요.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print("\n❌", e)
        print("\n· 키를 발급받은 지 1~2시간이 안 됐다면 아직 활성화 전일 수 있어요. 조금 뒤 다시 실행해 보세요.")
        print("· 키를 정확히 복사했는지(앞뒤 공백 포함) 확인해 주세요.")
