"""
app.py
------
Streamlit 화면입니다. 점검 로직은 check.py, 확인표는 report.py에 있고, 여기서는 화면만 다룹니다.

실행:  streamlit run app.py

화면 구성
    머리 배너 → 1. 예시로 체험하기 → 2. 나이 → 3. 약 고르기
    → 4. 결과 (탭 4개: 결과 목록+쉬운 설명 / 약 관계도 / 복약 시간표 / 약사 확인표)
"""

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st
from check import load_data, check_medications, calc_age, ELDERLY_AGE
from explain import load_explanations, find_explanation, symptoms_list
from report import make_report_html, KST, short_name, SLOTS

DATA_DATE = "병용금기 2026-07-31 / 효능군중복·노인주의 2026-07-21"

st.set_page_config(page_title="우리집 약 점검", page_icon="💊", layout="centered")


# ===============================================================
# 디자인 (CSS)
# 색 규칙: 청록(기본) / 빨강(금기) / 주황(주의) / 초록(문제 없음)
# 글꼴: Pretendard (불러오기 실패 시 기본 한글 글꼴로 자동 대체)
# ===============================================================
CSS = """
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
html, body, [class*="css"], .stMarkdown, button, input, textarea {
    font-family: "Pretendard", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif !important;
}
html, body { font-size: 18px; }
.block-container { padding-top: 2rem; max-width: 820px; }

/* 머리 배너 */
.hero {
    background: linear-gradient(135deg, #0f766e 0%, #0891b2 60%, #6366f1 100%);
    color: white; border-radius: 22px; padding: 30px 30px 24px; margin-bottom: 18px;
    box-shadow: 0 12px 30px rgba(8, 145, 178, .25);
}
.hero h1 { color: white; font-size: 2.1rem; font-weight: 800; margin: 0 0 6px; padding: 0; }
.hero p  { color: rgba(255,255,255,.92); font-size: 1.05rem; margin: 0; }
.hero .chips { margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
.hero .chip  { background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.35);
               border-radius: 999px; padding: 4px 12px; font-size: .85rem; }

/* 단계 제목 */
.step { display: flex; align-items: center; gap: 10px; margin: 26px 0 8px; }
.step .num { background: #0f766e; color: white; width: 32px; height: 32px; border-radius: 50%;
             display: flex; align-items: center; justify-content: center; font-weight: 700; flex: none; }
.step .title { font-size: 1.25rem; font-weight: 700; color: #134e4a; }

/* 안전 안내 */
.safety { background: #f0fdfa; border: 1px solid #99f6e4; border-radius: 14px;
          padding: 12px 16px; font-size: .92rem; color: #134e4a; }

/* 요약 숫자 카드 */
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 6px 0 14px; }
.stat  { border-radius: 16px; padding: 14px 10px; text-align: center; border: 1px solid; }
.stat .n { font-size: 2rem; font-weight: 800; line-height: 1.1; }
.stat .l { font-size: .85rem; margin-top: 2px; }
.stat.meds    { background: #f0f9ff; border-color: #bae6fd; color: #075985; }
.stat.contra  { background: #fef2f2; border-color: #fecaca; color: #b91c1c; }
.stat.caution { background: #fffbeb; border-color: #fde68a; color: #b45309; }

/* 결과 카드 */
.card { border-radius: 16px; padding: 14px 18px; margin-bottom: 12px; background: white;
        border: 1px solid #e5e7eb; border-left: 7px solid; box-shadow: 0 2px 8px rgba(0,0,0,.05); }
.card.contra  { border-left-color: #dc2626; }
.card.caution { border-left-color: #f59e0b; }
.badge { display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: .8rem;
         font-weight: 700; margin-right: 6px; }
.badge.contra  { background: #fee2e2; color: #b91c1c; }
.badge.caution { background: #fef3c7; color: #b45309; }
.badge.kind    { background: #f3f4f6; color: #374151; }
.card .drugs  { font-weight: 700; margin: 8px 0 4px; font-size: 1.02rem; }
.card .detail { color: #4b5563; font-size: .95rem; }

.ok { background: linear-gradient(135deg, #ecfdf5, #f0fdfa); border: 1px solid #a7f3d0;
      border-radius: 16px; padding: 18px; color: #065f46; }
.ok b { font-size: 1.1rem; }

/* 약 이름표 */
.pill { display: inline-block; background: #f0fdfa; border: 1px solid #99f6e4; color: #115e59;
        border-radius: 999px; padding: 4px 12px; margin: 3px 4px 3px 0; font-size: .9rem; }

/* 버튼 */
.stButton > button, .stDownloadButton > button {
    border-radius: 12px; font-weight: 600; padding: .55rem 1rem;
}
.stDownloadButton > button { background: #0f766e; color: white; border: none; }
.stDownloadButton > button:hover { background: #115e59; color: white; }

/* 쉬운 설명 카드 */
.easy  { background: #f8fafc; border-radius: 12px; padding: 12px 14px; margin-bottom: 8px; line-height: 1.6; }
.alert { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; border-radius: 12px;
         padding: 10px 14px; margin-bottom: 6px; }
.alert ul { margin: 4px 0 0; padding-left: 20px; }

/* 복약 시간표 */
.timeline { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin-top: 14px; }
.slot { border-radius: 16px; padding: 12px; border: 1px solid #e5e7eb; min-height: 120px; }
.slot.s0 { background: #fff7ed; } .slot.s1 { background: #fefce8; }
.slot.s2 { background: #eef2ff; } .slot.s3 { background: #f5f3ff; }
.slot-h { font-weight: 800; margin-bottom: 8px; font-size: 1.05rem; }
.slot-item { background: white; border-radius: 10px; padding: 6px 10px; margin-bottom: 6px;
             font-size: .9rem; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.slot-item .meal { color: #0f766e; font-size: .78rem; margin-left: 4px; }
.slot-empty { color: #9ca3af; font-size: .85rem; }

/* 고른 약 카드 (사진) */
.med-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; margin: 6px 0 10px; }
.med-card { background: white; border: 1px solid #e5e7eb; border-radius: 16px; padding: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,.05); }
.med-photo { height: 110px; border-radius: 10px; background: #f8fafc; display: flex;
             align-items: center; justify-content: center; overflow: hidden; margin-bottom: 8px; }
.med-photo img { max-width: 100%; max-height: 110px; object-fit: contain; font-size: .75rem; color: #9ca3af; }
.no-photo { color: #9ca3af; font-size: .85rem; }
.med-name { font-weight: 700; font-size: .92rem; line-height: 1.35; }
.med-sub  { color: #6b7280; font-size: .8rem; margin-top: 3px; line-height: 1.4; }

.footer { font-size: .8rem; color: #6b7280; text-align: center; margin-top: 30px; line-height: 1.6; }
"""
# st.markdown 대신 st.html을 씁니다. st.markdown은 CSS 중간의 빈 줄에서 스타일이 잘리는 문제가 있었습니다.
st.html(f"<style>{CSS}</style>")


def html(s):
    """꾸민 HTML 조각을 화면에 그립니다. (st.html 사용)"""
    st.html(s)


def step(num, title):
    """동그라미 숫자가 붙은 단계 제목을 그립니다."""
    html(f'<div class="step"><div class="num">{num}</div>'
                f'<div class="title">{title}</div></div>')


# 데이터는 앱이 처음 켜질 때 한 번만 불러옵니다. (매번 불러오면 느려짐)
@st.cache_resource
def get_db():
    return load_data()


@st.cache_resource
def get_explanations():
    return load_explanations()


db = get_db()
info = db["product_info"]
explanations = get_explanations()


# ===============================================================
# 예시 시나리오: 버튼 한 번에 약 목록과 나이를 채워 줍니다.
# 심사위원이 약 이름을 몰라도 바로 체험할 수 있게 하려는 목적입니다.
# ===============================================================
SCENARIOS = {
    "👵 여러 병원에 다니는 74세": {
        "birth": "19520315",   # 만 74세 (2026년 기준)
        "codes": ["644200550", "662503750", "73400360", "662503400", "73400290"],
        "desc": "항생제 + 고지혈증약 + 혈압약 2종 + 관절염약",
        # 시연용 예시 시간표 (실제 처방이 아니라 보여주기 위한 예시)
        "schedule": {
            "644200550": {"아침": True, "식사": "식후"},
            "662503750": {"저녁": True, "식사": "식후"},
            "73400360": {"아침": True, "식사": "식사와 상관없이"},
            "662503400": {"아침": True, "식사": "식사와 상관없이"},
            "73400290": {"아침": True, "저녁": True, "식사": "식후"},
        },
    },
    "👨 같은 성분이 겹친 58세": {
        "birth": "19680720",   # 만 58세
        "codes": ["641600360", "652103560", "643900470", "643300110"],
        "desc": "당뇨약 2종 + 진통소염제 2종",
    },
    "🙂 문제없는 45세": {
        "birth": "19810101",   # 만 45세
        "codes": ["73400360", "641600360"],
        "desc": "혈압약 + 당뇨약",
    },
}


def reset_schedule_editor():
    """시간표 표(data_editor)에 남아 있는 이전 편집 기록을 지웁니다."""
    for k in [k for k in st.session_state if str(k).startswith("sched_editor_")]:
        del st.session_state[k]


def load_scenario(name):
    """버튼을 누르면 실행됩니다. 입력 칸의 값을 시나리오 값으로 바꿉니다."""
    st.session_state["birth"] = SCENARIOS[name]["birth"]
    st.session_state["meds"] = SCENARIOS[name]["codes"]
    st.session_state["schedule"] = {c: dict(v) for c, v in SCENARIOS[name].get("schedule", {}).items()}
    reset_schedule_editor()


def clear_all():
    st.session_state["birth"] = ""
    st.session_state["meds"] = []
    st.session_state["schedule"] = {}
    reset_schedule_editor()


# ===============================================================
# 머리 배너
# ===============================================================
html("""
<div class="hero">
  <h1>💊 우리집 약 점검</h1>
  <p>여러 병원·약국에서 받은 약, 함께 먹어도 괜찮을까요?<br>약을 골라 넣으면 식약처 DUR 기준으로 한 번에 점검해 드려요.</p>
  <div class="chips">
    <span class="chip">🚫 병용금기</span><span class="chip">🔁 성분·효능 중복</span>
    <span class="chip">👴 노인주의</span><span class="chip">📖 쉬운 설명</span>
    <span class="chip">⏰ 복약 시간표</span><span class="chip">📄 약사 확인표</span>
  </div>
</div>
<div class="safety">ℹ️ 이 도구는 <b>교육용 시제품</b>으로 진단·처방을 대신하지 않습니다.
결과와 상관없이 <b>약을 임의로 끊거나 바꾸지 말고</b> 약사·의사와 상담하세요.</div>
""")

# 사이드바: 사용법과 데이터 정보
with st.sidebar:
    st.markdown("### 📖 사용 방법")
    st.markdown("1. 생년월일을 입력해요\n2. 드시는 약을 모두 골라요\n3. 결과와 쉬운 설명을 확인해요\n"
                "4. 복약 시간표를 정리해요\n5. 확인표를 약사님께 보여드려요")
    st.markdown("### 🗂️ 사용한 자료")
    st.caption(f"한국의약품안전관리원 DUR 정보\n\n기준일: {DATA_DATE}")
    st.markdown("### 🔒 개인정보")
    st.caption("입력한 생년월일과 약은 저장되지 않습니다. 확인표에는 만 나이만 표시돼요.")


# ===============================================================
# 1. 예시로 체험하기
# ===============================================================
step(1, "예시로 체험해 보기 <span style='font-weight:400;font-size:.9rem;color:#6b7280'>(선택)</span>")
cols = st.columns(len(SCENARIOS))
for col, name in zip(cols, SCENARIOS):
    with col:
        st.button(name, on_click=load_scenario, args=(name,), width="stretch",
                  help=SCENARIOS[name]["desc"])

# ===============================================================
# 2. 나이
# ===============================================================
step(2, "복용하시는 분의 생년월일")
# 처음 켰을 때 기본값. (value= 대신 session_state로 정해야 예시 버튼과 충돌하지 않음)
st.session_state.setdefault("birth", "")
st.session_state.setdefault("meds", [])
st.session_state.setdefault("schedule", {})
birth = st.text_input("생년월일 8자리 (- 없이, 모르면 비워 두세요)", max_chars=10,
                      placeholder="예: 19520315", key="birth")
# 만 나이는 앱이 오늘 날짜(한국 시간) 기준으로 계산합니다. 생년월일 자체는 저장하지 않습니다.
age, age_error = calc_age(birth, datetime.now(KST).date())
if age_error:
    st.error("⚠️ " + age_error)
elif age is not None:
    note = f" · {ELDERLY_AGE}세 이상 주의 약도 함께 확인해요" if age >= ELDERLY_AGE else ""
    st.success(f"🎂 만 **{age}세**로 계산했어요{note}")

# ===============================================================
# 3. 약 고르기
# ===============================================================
step(3, "드시는 약 고르기")
selected = st.multiselect(
    "칸을 누르고 약 이름을 일부만 입력하면 목록이 나와요. 여러 개를 고를 수 있어요.",
    options=list(info.keys()),                              # 실제 값은 제품코드
    format_func=lambda c: short_name(info[c]["제품명"]),    # 화면에는 제품명으로 보여줌
    placeholder="예: 노바스크",
    key="meds",
)
if selected:
    # 고른 약 카드: 사진과 모양을 보여 주어, 약봉투 속 실제 약과 같은지 사용자가 직접 확인하게 합니다.
    # (앱이 사진으로 약을 알아맞히는 것이 아니라, 사람이 고른 약을 사진으로 '확인'만 하는 기능)
    st.caption("📸 약봉투 속 실제 약과 **모양·색·새겨진 글자**가 같은지 확인해 보세요. "
               "같은 약이라도 제조 시기에 따라 모양이 다를 수 있으니, 최종 확인은 약봉투 이름과 약사님께.")
    cards = ""
    for c in selected:
        pinfo = db["pill"].get(c)
        name = escape(short_name(info[c]["제품명"]))
        if pinfo:
            imprint = f"<div class='med-sub'>새겨진 글자: {escape(pinfo['각인'])}</div>" if pinfo["각인"] else ""
            photo = (f"<img src='{escape(pinfo['사진'])}' alt='사진을 불러오지 못했어요 (인터넷 연결 확인)' "
                     f"referrerpolicy='no-referrer' loading='lazy'>")
            desc = f"<div class='med-sub'>{escape(pinfo['성상'])}</div>{imprint}"
        else:
            photo = "<div class='no-photo'>사진 정보 없음</div>"
            desc = ""
        cards += (f"<div class='med-card'><div class='med-photo'>{photo}</div>"
                  f"<div class='med-name'>{name}</div>"
                  f"<div class='med-sub'>성분: {escape(info[c]['성분명'])}</div>{desc}</div>")
    html(f"<div class='med-grid'>{cards}</div>")
    st.caption("사진 출처: 식품의약품안전처 의약품 낱알식별 정보")
    st.button("🔄 처음부터 다시", on_click=clear_all)

# ===============================================================
# 4. 결과
# ===============================================================
step(4, "점검 결과")

if not selected:
    st.info("👆 약을 고르거나, 위의 예시 버튼을 눌러 보세요.")
else:
    results = check_medications(db, selected, age=age)
    for r in results:                       # 결과마다 쉬운 설명 카드를 찾아 붙여 둡니다 (없으면 None)
        r["설명"] = find_explanation(explanations, r)
    n_contra = sum(r["심각도"] == "금기" for r in results)
    n_caution = len(results) - n_contra

    # 요약 숫자 카드 3개
    html(f"""
    <div class="stats">
      <div class="stat meds"><div class="n">{len(selected)}</div><div class="l">💊 고른 약</div></div>
      <div class="stat contra"><div class="n">{n_contra}</div><div class="l">🚫 함께 쓰면 안 됨</div></div>
      <div class="stat caution"><div class="n">{n_caution}</div><div class="l">⚠️ 주의 필요</div></div>
    </div>""")

    tab_list, tab_graph, tab_sched, tab_report = st.tabs(
        ["📋 결과 목록", "🕸️ 약 관계도", "⏰ 복약 시간표", "📄 약사 확인표"])

    # ---------- 탭 1: 결과 목록 ----------
    with tab_list:
        for r in results:
            level = "contra" if r["심각도"] == "금기" else "caution"
            icon = "🚫" if level == "contra" else "⚠️"
            drugs = " + ".join(short_name(d) for d in r["약"])
            # escape: 약 이름에 <, & 같은 기호가 있어도 화면이 깨지지 않도록 처리
            html(f"""
            <div class="card {level}">
              <span class="badge {level}">{icon} {escape(r['심각도'])}</span>
              <span class="badge kind">{escape(r['종류'])}</span>
              <div class="drugs">{escape(drugs)}</div>
              <div class="detail">{escape(r['내용'])}</div>
            </div>""")

            # 쉬운 설명 카드: 눌러서 펼쳐 보는 방식
            e = r["설명"]
            if e:
                with st.expander(f"📖 쉽게 알아보기 · {e['제목']}"):
                    html(f"<div class='easy'>{escape(e['쉬운설명'])}</div>")
                    symptoms = symptoms_list(e)
                    if symptoms:
                        items = "".join(f"<li>{escape(x)}</li>" for x in symptoms)
                        html(f"<div class='alert'>🚨 <b>이런 증상이 있으면 바로 병원·약국에 연락하세요</b>"
                             f"<ul>{items}</ul></div>")
                    st.caption(f"근거: {e['근거']}")

        if not results:
            html("""
            <div class="ok"><b>✅ DUR 목록에서 확인된 문제가 없어요.</b><br>
            단, DUR 목록에 없는 상호작용도 있을 수 있고, 건강기능식품·한약은 점검하지 않습니다.</div>
            """)
        else:
            st.markdown("👉 이 내용을 **약사에게 보여주고** 계속 드셔도 되는지 확인하세요.")

        if age is None:
            st.caption(f"💡 생년월일을 입력하면 {ELDERLY_AGE}세 이상 주의 약도 함께 확인해요.")

    # ---------- 탭 2: 약 관계도 ----------
    # 약을 동그라미로, 문제가 있는 조합을 선으로 이어서 한눈에 보여줍니다.
    # Graphviz의 DOT 언어로 그림을 '글로' 설명하면 Streamlit이 그려 줍니다. (추가 설치 필요 없음)
    with tab_graph:
        elderly_drugs = {d for r in results if r["종류"] == "노인주의" for d in r["약"]}

        def node_id(code):
            return f"n{code}"

        lines = ['graph G {',
                 '  layout=neato; overlap=false; sep="+25"; bgcolor="transparent"; pad=0.3;',
                 '  node [shape=box, style="rounded,filled", fontname="Malgun Gothic", fontsize=12,'
                 ' fillcolor="#f0fdfa", color="#0f766e", penwidth=1.5, margin="0.2,0.12"];',
                 '  edge [fontname="Malgun Gothic", fontsize=11, penwidth=2.5, len=2.6];']
        for c in selected:
            full = info[c]["제품명"]
            label = short_name(full).split("(")[0].replace('"', "'")   # 괄호 앞 이름만 짧게
            if full in elderly_drugs:                         # 노인주의 약은 주황 테두리 + 표시
                lines.append(f'  {node_id(c)} [label="{label}\\n👴 노인주의", color="#f59e0b", fillcolor="#fffbeb"];')
            else:
                lines.append(f'  {node_id(c)} [label="{label}"];')

        name_to_code = {info[c]["제품명"]: c for c in selected}
        for r in results:
            if len(r["약"]) != 2:
                continue
            a, b = (node_id(name_to_code[d]) for d in r["약"])
            if r["심각도"] == "금기":
                lines.append(f'  {a} -- {b} [color="#dc2626", label=" 금기 ", fontcolor="#dc2626"];')
            else:
                lines.append(f'  {a} -- {b} [color="#f59e0b", style=dashed, label=" 중복 ", fontcolor="#b45309"];')
        lines.append("}")

        if len(selected) == 1 and not results:
            st.caption("약을 2개 이상 고르면 약끼리의 관계를 그려 드려요.")
        st.graphviz_chart("\n".join(lines), width="stretch")
        st.caption("🟥 빨간 실선: 함께 쓰면 안 됨 · 🟧 주황 점선: 중복 주의 · 선이 없으면 DUR에서 확인된 문제 없음")

    # ---------- 탭 3: 복약 시간표 ----------
    # 표에서 약마다 먹는 시간을 체크하면, 아래에 하루 시간표 카드로 정리됩니다.
    # 입력한 내용은 확인표에도 들어갑니다.
    with tab_sched:
        st.markdown("약봉투나 처방전에 적힌 대로 **언제 먹는지 체크**해 보세요. 하루 시간표로 정리해 드려요.")
        st.caption("⚠️ 이 앱은 복용 시간을 정해 주지 않아요. 처방받은 대로만 입력하고, 모르면 약사님께 물어보세요.")

        sched = st.session_state["schedule"]           # {제품코드: {"아침": True, ..., "식사": "식후", "메모": ""}}
        table = pd.DataFrame(
            [{"약": short_name(info[c]["제품명"]),
              **{s: bool(sched.get(c, {}).get(s, False)) for s in SLOTS},
              "식사": sched.get(c, {}).get("식사"),
              "메모": sched.get(c, {}).get("메모")} for c in selected],
            index=selected,
        )
        edited = st.data_editor(
            table,
            key="sched_editor_" + "_".join(selected),   # 약 목록이 바뀌면 새 표로 시작
            hide_index=True, width="stretch", disabled=["약"],
            column_config={
                "약": st.column_config.TextColumn("약", width="medium"),
                **{s: st.column_config.CheckboxColumn(s, width="small") for s in SLOTS},
                "식사": st.column_config.SelectboxColumn("식사", options=["식전", "식후", "식사와 상관없이", "모름"]),
                "메모": st.column_config.TextColumn("메모", help="예: 반 알, 통증 있을 때만"),
            },
        )

        def clean(v):
            """빈 칸(None, NaN)을 빈 글자로 바꿉니다."""
            return "" if v is None or pd.isna(v) else str(v)

        for c, row in edited.iterrows():               # 표에서 고친 내용을 저장
            sched[c] = {**{s: bool(row[s]) for s in SLOTS}, "식사": clean(row["식사"]), "메모": clean(row["메모"])}

        # 하루 시간표 카드 4칸
        icons = ["🌅", "☀️", "🌇", "🌙"]
        slots_html = ""
        for i, s in enumerate(SLOTS):
            items = ""
            for c in selected:
                if sched[c][s]:
                    meal = f"<span class='meal'>{escape(sched[c]['식사'])}</span>" if sched[c]["식사"] else ""
                    items += f"<div class='slot-item'>💊 {escape(short_name(info[c]['제품명']).split('(')[0])}{meal}</div>"
            slots_html += (f"<div class='slot s{i}'><div class='slot-h'>{icons[i]} {s}</div>"
                           f"{items or '<div class=slot-empty>없음</div>'}</div>")
        html(f"<div class='timeline'>{slots_html}</div>")

        n_times = sum(any(sched[c][s] for c in selected) for s in SLOTS)
        unset = [short_name(info[c]["제품명"]).split("(")[0] for c in selected if not any(sched[c][s] for s in SLOTS)]
        if n_times:
            st.markdown(f"🗓️ 하루에 **{n_times}번** 약을 챙겨 드세요.")
        if unset:
            st.caption("아직 시간을 정하지 않은 약: " + ", ".join(unset))

    # ---------- 탭 4: 약사 확인표 ----------
    with tab_report:
        st.markdown("내려받은 파일을 열면 **한 장짜리 확인표**가 나와요. 점검 결과, 쉬운 설명, "
                    "복약 시간표가 함께 들어가요. 인쇄하거나 휴대폰 화면으로 약사님께 보여 드리세요.")
        report_html = make_report_html(db, selected, age, results, data_date=DATA_DATE,
                                       schedule=st.session_state["schedule"])
        st.download_button(
            "📄 확인표 내려받기",
            data=report_html,
            file_name=f"약점검_확인표_{datetime.now(KST):%Y%m%d}.html",
            mime="text/html",
            width="stretch",
        )
        with st.expander("👀 확인표 미리 보기"):
            st.iframe(report_html, height=700)

# ===============================================================
# 꼬리말
# ===============================================================
html(f"""
<div class="footer">
자료: 한국의약품안전관리원 DUR 정보 (기준일 {DATA_DATE}) · 비상업적 교육 목적 사용<br>
DUR 경고가 없는 일부 약은 검색되지 않을 수 있습니다 · 입력한 정보는 저장되지 않습니다
</div>""")
