"""
report.py
---------
"약사에게 보여줄 확인표"를 HTML 파일로 만듭니다.
내려받은 파일을 브라우저로 열고 인쇄(Ctrl+P)하면 A4 한 장짜리 종이가 됩니다.
PDF 대신 HTML을 쓴 이유: PDF는 한글 글꼴 파일을 따로 넣어야 해서 오류가 나기 쉽습니다.

사용 예:
    from report import make_report_html
    html = make_report_html(db, ["73400360", "662503400"], age=70, results=결과)
"""

from datetime import datetime, timedelta, timezone
from html import escape

# 한국 시간. (zoneinfo("Asia/Seoul")는 윈도우에서 추가 설치 없이는 오류가 나서 이 방식을 씁니다)
KST = timezone(timedelta(hours=9))

# 결과 종류별로 "약사에게 물어볼 질문"을 미리 정해 둡니다. (AI가 지어내지 않도록 고정 문구 사용)
QUESTIONS = {
    "병용금기": "이 두 약을 함께 먹어도 되나요? 처방하신 선생님께 알려야 하나요?",
    "동일성분 중복": "같은 성분이 두 번 들어 있는 것 같은데, 둘 중 하나만 먹어야 하나요?",
    "효능군 중복": "효과가 비슷한 약을 두 가지 먹고 있는데, 둘 다 필요한가요?",
    "노인주의": "제 나이에 이 약을 먹을 때 조심해야 할 점이나 부작용 신호가 있나요?",
}


def short_name(full):
    """제품명 뒤 포장 단위 '_(...)'를 떼어 냅니다. (app.py와 같은 규칙)"""
    return full.split("_(")[0]


# 복약 시간표의 시간대 (app.py와 같이 씁니다)
SLOTS = ["아침", "점심", "저녁", "자기 전"]


def make_report_html(db, codes, age, results, data_date="", schedule=None):
    """schedule: {제품코드: {"아침": True, ..., "식사": "식후", "메모": ""}}  (없으면 None)
    results 안에 '설명'(explain.py가 찾은 쉬운 설명)이 있으면 증상 안내도 함께 넣습니다."""
    info = db["product_info"]
    codes = list(dict.fromkeys(codes))
    schedule = schedule or {}
    today = datetime.now(KST).strftime("%Y년 %m월 %d일")
    age_text = f"만 {age}세" if age is not None else "입력 안 함"
    sections = []   # (제목, 내용 HTML) 순서대로 모아서 번호를 자동으로 붙입니다.

    # 1) 약 목록 표   (escape: 제품명에 <, & 같은 기호가 있어도 화면이 깨지지 않게 처리)
    pills = db.get("pill", {})

    def photo(c):
        """사진이 있으면 작은 사진, 없으면 빈 칸"""
        p = pills.get(c)
        return (f"<img src='{escape(p['사진'])}' alt='' referrerpolicy='no-referrer' class='thumb'>"
                if p and p.get("사진") else "")

    med_rows = "".join(
        f"<tr><td>{i}</td><td>{photo(c)}</td><td>{escape(short_name(info[c]['제품명']))}</td>"
        f"<td>{escape(info[c]['성분명'])}</td></tr>"
        for i, c in enumerate(codes, start=1)
    )
    sections.append((f"먹고 있는 약 ({len(codes)}개)",
                     f"<table><tr><th>#</th><th>사진</th><th>제품명</th><th>성분</th></tr>{med_rows}</table>"))

    # 2) 복약 시간표: 시간대를 하나라도 체크한 약이 있을 때만 넣습니다.
    if any(schedule.get(c, {}).get(s) for c in codes for s in SLOTS):
        head = "".join(f"<th class='slot'>{s}</th>" for s in SLOTS)
        rows = ""
        for c in codes:
            sc = schedule.get(c, {})
            marks = "".join(f"<td class='mark'>{'●' if sc.get(s) else ''}</td>" for s in SLOTS)
            rows += (f"<tr><td>{escape(short_name(info[c]['제품명']))}</td>{marks}"
                     f"<td>{escape(str(sc.get('식사') or ''))}</td><td>{escape(str(sc.get('메모') or ''))}</td></tr>")
        sections.append(("복약 시간표 (직접 입력한 내용)",
                         f"<table><tr><th>약</th>{head}<th>식사</th><th>메모</th></tr>{rows}</table>"))

    # 3) 점검 결과 (+ 쉬운 설명과 바로 연락할 증상)
    if results:
        items = ""
        for r in results:
            e = r.get("설명")
            extra = ""
            if e:
                extra += f"<div class='easy'>💡 {escape(e['쉬운설명'])}</div>"
                symptoms = [x.strip() for x in e.get("바로연락할증상", "").split("/") if x.strip() not in ("", "-")]
                if symptoms:
                    extra += f"<div class='alert'>🚨 이런 증상이 있으면 바로 병원·약국에 연락: {escape(', '.join(symptoms))}</div>"
            items += (f"<li class='{'contra' if r['심각도'] == '금기' else 'caution'}'>"
                      f"<b>[{escape(r['심각도'])} · {escape(r['종류'])}]</b> "
                      f"{escape(' + '.join(short_name(d) for d in r['약']))}<br>"
                      f"<span class='detail'>DUR 사유: {escape(r['내용'])}</span>{extra}</li>")
        sections.append(("점검 결과", f"<ul>{items}</ul>"))
    else:
        sections.append(("점검 결과", "<ul><li>DUR 목록에서 확인된 문제가 없습니다. "
                                      "(DUR 목록에 없는 상호작용은 확인하지 못합니다)</li></ul>"))

    # 4) 질문 목록: 나온 결과 종류에 맞는 질문만, 중복 없이
    kinds = list(dict.fromkeys(r["종류"] for r in results))
    questions = ["제가 먹고 있는 약 목록이 맞는지 확인해 주세요."] + [QUESTIONS[k] for k in kinds]
    if any(schedule.get(c, {}).get(s) for c in codes for s in SLOTS):
        questions.append("제가 적은 복약 시간표가 처방대로 맞는지 봐 주세요.")
    sections.append(("약사님께 여쭤볼 것", "<ol>" + "".join(f"<li>{escape(q)}</li>" for q in questions) + "</ol>"))

    # 5) 메모 칸
    sections.append(("약사님 메모", "<div class='memo'></div>"))

    body = "".join(f"<h2>{i}. {title}</h2>{content}" for i, (title, content) in enumerate(sections, start=1))

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>약 점검 확인표 ({today})</title>
<style>
  body {{ font-family: "Malgun Gothic", "Apple SD Gothic Neo", sans-serif; font-size: 16pt;
         max-width: 800px; margin: 24px auto; padding: 0 16px; color: #111; line-height: 1.5; }}
  h1 {{ font-size: 22pt; margin-bottom: 4px; }}
  h2 {{ font-size: 17pt; border-bottom: 2px solid #333; padding-bottom: 4px; margin-top: 28px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13pt; }}
  th, td {{ border: 1px solid #999; padding: 6px 8px; text-align: left; vertical-align: top; }}
  th {{ background: #eee; }}
  li {{ margin-bottom: 10px; }}
  .contra {{ color: #b00020; }}
  .caution {{ color: #8a5a00; }}
  .detail {{ color: #333; font-size: 13pt; }}
  .memo {{ border: 1px solid #999; height: 120px; }}
  .easy {{ color: #333; font-size: 12.5pt; margin-top: 4px; }}
  .alert {{ color: #b00020; font-size: 12.5pt; margin-top: 4px; font-weight: bold; }}
  td.mark {{ text-align: center; color: #0f766e; }}
  th.slot {{ white-space: nowrap; width: 1%; }}
  img.thumb {{ height: 44px; max-width: 90px; object-fit: contain; }}
  .notice {{ font-size: 11pt; color: #444; border-top: 1px solid #999; margin-top: 28px; padding-top: 8px; }}
  @media print {{ body {{ margin: 0; }} .noprint {{ display: none; }} }}
</style></head>
<body>
  <p class="noprint">🖨️ 인쇄하려면 <b>Ctrl + P</b>(맥은 ⌘ + P)를 누르세요.</p>
  <h1>💊 약 점검 확인표</h1>
  <div>작성일: {today} · 나이: {escape(age_text)}</div>

  {body}

  <p class="notice">이 확인표는 의대생 교육용 시제품이 한국의약품안전관리원 DUR 정보{escape(' (' + data_date + ')') if data_date else ''}를
  바탕으로 만든 것으로, 진단이나 처방을 대신하지 않습니다. 결과와 상관없이 약을 임의로 끊거나 바꾸지 마세요.
  건강기능식품·한약은 점검하지 않았습니다.</p>
</body></html>"""
