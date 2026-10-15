import streamlit as st
import pdfplumber
import json
import io
import time
import pandas as pd
from datetime import datetime
from streamlit_drawable_canvas import st_canvas
from google import genai

# ---------------------------------------------------------
# 1. 화면 기본 설정 & 외부 CSS 파일 불러오기
# ---------------------------------------------------------
st.set_page_config(page_title="AI 에듀테크 수퍼 앱", layout="wide", initial_sidebar_state="collapsed")

# 🌟 [디자인 업그레이드] 탭 글씨 크기 확대 및 스타일링
custom_css = """
<style>
    /* 탭(Tab) 제목 글씨 크기 및 굵기 키우기 */
    div[data-baseweb="tab-list"] button p {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }
    /* 메뉴 타이틀 꾸미기 */
    .menu-title { font-size: 1.1rem; font-weight: 800; color: #1f4b8e; margin-top: 15px; margin-bottom: 5px; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

def load_css(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        pass
load_css("style.css")

# 세션 상태 초기화
if "current_page" not in st.session_state: st.session_state.current_page = "과정안 생성"
if "extracted_text" not in st.session_state: st.session_state.extracted_text = ""
if "proposed_sessions" not in st.session_state: st.session_state.proposed_sessions = None
if "selected_session_detail" not in st.session_state: st.session_state.selected_session_detail = None
if "worksheet_detail" not in st.session_state: st.session_state.worksheet_detail = None
if "quiz_detail" not in st.session_state: st.session_state.quiz_detail = None
if "final_subject" not in st.session_state: st.session_state.final_subject = "공통국어"

if "training_list" not in st.session_state: 
    st.session_state.training_list = ["2026학년도 새학년 집중준비기간 연수", "전남글빛국어교육연구회 공개수업"]
if "registry_df" not in st.session_state: 
    st.session_state.registry_df = pd.DataFrame(columns=["연번", "연수명", "소속", "직위", "이름", "서명 상태", "등록 일시"])

# 상단 헤더 (센스 있는 네이밍)
st.title("🚀 AI 에듀테크 수퍼 앱 (feat. 개념기반 교육과정)")
st.write("---")

# ==========================================
# 🌟 [AI 호출 함수] (트래픽 방어 로직 포함)
# ==========================================
def call_gemini_robust(api_key, prompt, max_retries=3):
    client = genai.Client(api_key=api_key)
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
            return response.text
        except Exception as e:
            err_msg = str(e)
            if "503" in err_msg or "UNAVAILABLE" in err_msg:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
            raise Exception(f"AI 통신 오류: {err_msg}")

# ---------------------------------------------------------
# 3. 화면 3분할 (2:6:2 비율)
# ---------------------------------------------------------
col_menu, col_main, col_info = st.columns([2, 6, 2], gap="large")

with col_menu:
    st.subheader("📌 업무 메뉴")
    def nav_button(label, page_name):
        if st.button(label, type="primary" if st.session_state.current_page == page_name else "secondary", use_container_width=True):
            st.session_state.current_page = page_name
            st.rerun()
            
    st.markdown("<div class='menu-title'>📚 수업 지원</div>", unsafe_allow_html=True)
    nav_button("📝 과정안/학습지 출제", "과정안 생성")
    
    st.markdown("<div class='menu-title'>📝 평가/기록 지원</div>", unsafe_allow_html=True)
    nav_button("💡 학생 세특 초안", "세특 초안")
    
    st.markdown("<div class='menu-title'>🏫 행정/학급 운영</div>", unsafe_allow_html=True)
    nav_button("📋 온라인 등록부", "등록부")
    nav_button("💌 학급 알림장/문자", "알림장")

with col_main:
    if st.session_state.current_page == "과정안 생성":
        st.subheader("📝 개념기반 공개수업 마스터플랜 생성기")
        st.caption("교과서 PDF 하나로 단원 분석부터 과정안, 활동지, 형성평가까지 완벽하게 추출합니다.")
        
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "⚙️ 1. 기본 설정", "📊 2. 단원 분석", "🎯 3. 지도안 생성", "📝 4. 활동지 생성", "❓ 5. 평가 출제", "🖨️ 6. 인쇄 출력"
        ])
        
        # [탭 1] 기본 설정 및 파일 업로드
        with tab1:
            st.markdown("#### ⚙️ 수업 기본 정보 세팅")
            st.caption("여기서 입력하신 학교명, 과목, 일시 등의 정보는 6단계의 모든 출력물에 자동으로 깔끔하게 인쇄됩니다.")
            
            c1, c2 = st.columns(2)
            with c1:
                # 과목 신규 생성 로직 적용
                subj_list = ["공통국어", "윤리와 사상", "생활과 윤리", "➕ 직접 입력 (새 과목 추가)"]
                sel_subj = st.selectbox("📚 담당 과목", subj_list)
                if sel_subj == "➕ 직접 입력 (새 과목 추가)":
                    st.session_state.final_subject = st.text_input("✨ 새 과목명 입력", placeholder="예) 통합사회, 심리학 등")
                else:
                    st.session_state.final_subject = sel_subj
                
                st.text_input("🏫 소속 학교명", placeholder="예) 광영고등학교", key="school_name")
                st.text_input("📅 수업 일시", placeholder="예) 2026. 10. 14. (수) 14:00", key="class_date")
                
            with c2:
                st.text_input("👨‍🏫 지도 교사", placeholder="예) 유일한", key="teacher_name")
                st.text_input("👥 수업 대상", placeholder="예) 1학년 6반 학생", key="target_students")
                st.text_input("🏫 수업 장소", placeholder="예) 1학년 6반 교실", key="class_location")
                
            st.write("---")
            st.text_input("🔑 Gemini API 키", type="password", placeholder="발급받은 API 키를 입력하세요", key="api_key")
                
            st.write("---")
            st.markdown("#### 📄 교과서 PDF 업로드")
            st.info("💡 **효율 200% 활용 꿀팁:** 교과서 전체 파일(대용량)보다는 **수업하실 단원(1~3차시 분량)의 PDF만 잘라서 업로드**해 주세요! AI가 훨씬 빠르고 정밀하게 개념을 추출합니다.")
            uploaded_file = st.file_uploader("단원 분석을 위한 PDF 파일을 업로드해 주세요.", type=["pdf"])
                
        # [탭 2] 단원 분석
        with tab2:
            st.markdown("#### 📊 단원 구조 분석")
            st.caption("업로드된 텍스트를 읽고 개념기반 탐구 흐름에 맞는 최적의 수업 차시를 제안합니다.")
            if uploaded_file and st.session_state.api_key:
                if st.button("🚀 AI 단원 분석 시작", type="primary"):
                    with st.spinner(f"AI가 {st.session_state.final_subject} 교과서를 분석하여 개념기반 흐름을 추출하고 있습니다..."):
                        text_data = ""
                        with pdfplumber.open(uploaded_file) as pdf:
                            for page in pdf.pages:
                                ext = page.extract_text()
                                if ext: text_data += ext + "\n"
                        st.session_state.extracted_text = text_data
                        
                        prompt1 = f"당신은 개념기반 교육과정(CBI)에 정통한 고등학교 {st.session_state.final_subject} 수석 교사입니다. 텍스트를 분석해 개념 탐구에 적합한 최적 총 차시를 설계하세요. JSON 배열로 답변 (키: session, type, title, desc). [내용] {text_data}"
                        try:
                            res1 = call_gemini_robust(st.session_state.api_key, prompt1)
                            st.session_state.proposed_sessions = json.loads(res1.replace("```json", "").replace("```", "").strip())
                            st.success("단원 분석 완료! 3단계 탭으로 이동하세요.")
                        except Exception as e:
                            st.error(str(e))
            else:
                st.warning("1단계 탭에서 API 키를 입력하고 교과서 PDF를 업로드해 주세요.")
                
        # [탭 3] 공개수업 지도안 생성
        with tab3:
            st.markdown("#### 🎯 개념기반 공개수업 지도안 생성")
            st.caption("학생들이 다양한 자료를 통합하여 '핵심 아이디어'에 스스로 도달할 수 있도록 교사-학생 상호작용이 강조된 지도안을 설계합니다.")
            if st.session_state.proposed_sessions:
                options = {f"{s['session']}차시 - {s['title']}": s for s in st.session_state.proposed_sessions}
                sel_opt = st.radio("과정안을 생성할 차시를 선택하세요:", list(options.keys()))
                if st.button("📝 개념기반 공개수업 지도안 생성", type="primary"):
                    chosen = options[sel_opt]
                    with st.spinner("사실적 지식을 넘어 핵심 아이디어로 나아가는 지도안을 설계 중입니다..."):
                        prompt2 = f"""당신은 개념기반 교육과정(CBI)에 정통한 고등학교 {st.session_state.final_subject} 수석 교사입니다. 
주제: {chosen['title']}. 
단순한 지식 전달이 아닌, 학생들이 다양한 자료를 분석·통합하여 '핵심 아이디어(일반화)'에 스스로 도달할 수 있는 학생 주도형 탐구 수업을 설계해 주세요.
반드시 아래 키를 포함한 JSON 형식으로 답변하세요:
{{
  "overview": "수업 개요 및 개념기반 설계 의도 (2~3문장)",
  "macro": "거시 개념 (예: #관점 #통합 #체계 등)",
  "micro": "미시 개념 (단원에 특화된 핵심 개념)",
  "objective": "본시 학습 목표 (DO와 UNDERSTAND가 결합된 형태)",
  "big_idea": "핵심 아이디어 / 일반화 (학생이 도달해야 할 깊은 이해)",
  "intro_act": "도입 (개념적 사고를 자극하는 생각열기 질문 및 동기유발)", "intro_time": "10분", "intro_note": "학생의 삶과 연결",
  "dev_act": "전개 (사실적 지식 탐구 -> 개념적 이해로 나아가는 활동. 교사의 탐구 질문과 학생의 상호작용 상세화)", "dev_time": "30분", "dev_note": "모둠 활동 및 스마트기기 활용",
  "conc_act": "정리 (핵심 아이디어 도출 공유 및 일반화 성찰, 형성평가)", "conc_time": "10분", "conc_note": "개념 전이 점검"
}}
[내용] {st.session_state.extracted_text}"""
                        try:
                            res2 = call_gemini_robust(st.session_state.api_key, prompt2)
                            st.session_state.selected_session_detail = json.loads(res2.replace("```json", "").replace("```", "").strip())
                            st.session_state.selected_session_detail.update({'session': chosen['session'], 'title': chosen['title']})
                            st.success("개념기반 지도안 완성! 4단계 탭으로 이동하세요.")
                        except Exception as e:
                            st.error(str(e))
            else:
                st.warning("2단계 단원 분석을 먼저 완료해 주세요.")

        # [탭 4] A4 학생 활동지 생성
        with tab4:
            st.markdown("#### 📝 A4 맞춤형 학생 활동지 생성")
            st.caption("단순 빈칸 채우기가 아닌, 3단 논리 구조와 열린 탐구 질문이 포함된 고품질 활동지를 만듭니다.")
            if st.session_state.selected_session_detail:
                if st.button("📝 개념기반 학생 활동지 설계", type="primary"):
                    with st.spinner("탐구 질문과 논리 구조가 포함된 학생 활동지를 디자인 중입니다..."):
                        prompt3 = f"""당신은 개념기반 교육과정(CBI) 전문가이자 {st.session_state.final_subject} 수석 교사입니다. 
앞서 설계한 '{st.session_state.selected_session_detail['title']}' 수업의 학생용 활동지를 만듭니다. 
반드시 아래 JSON 구조로 답변하세요:
{{
  "title": "활동지 제목",
  "act1_title": "[활동 1] 지식 탐구 및 분석 (자료를 분석하여 표로 정리할 내용 안내)",
  "act2_title": "[활동 2] 생각을 여는 탐구 질문 만들기 (피해야 할 닫힌 질문 vs 추천하는 열린 탐구 질문 예시)",
  "act3_title": "[활동 3] 나만의 관점 세우기 (비판적 재구성 - 3단 마법의 문장 틀 포함)",
  "wrap_up": "[마무리] 상호작용 및 성찰 체크리스트"
}}"""
                        try:
                            res3 = call_gemini_robust(st.session_state.api_key, prompt3)
                            st.session_state.worksheet_detail = json.loads(res3.replace("```json", "").replace("```", "").strip())
                            st.success("활동지 완성! 5단계 탭으로 이동하세요.")
                        except Exception as e:
                            st.error(str(e))
            else:
                st.warning("3단계 지도안 생성을 완료해 주세요.")

        # [탭 5] 형성평가 문제 출제
        with tab5:
            st.markdown("#### ❓ 다유형 형성평가지 출제")
            st.caption("수업 목표 달성 여부를 확인하기 위해 O/X, 초성, 어휘, 4지선다 등 4가지 유형의 퀴즈를 출제합니다.")
            if st.session_state.selected_session_detail:
                if st.button("❓ 형성평가 문제 출제 시작", type="primary"):
                    with st.spinner(f"핵심 아이디어를 점검할 수 있는 {st.session_state.final_subject} 퀴즈를 출제하고 있습니다..."):
                        prompt4 = f"""당신은 {st.session_state.final_subject} 수석 교사이자 평가 전문가입니다.
앞서 설계한 '{st.session_state.selected_session_detail['title']}' 수업의 내용과 핵심 아이디어를 점검할 수 있는 형성평가 문제를 출제해 주세요.
단순 암기 확인부터 개념 적용까지 다양하게 구성하세요.
반드시 아래 JSON 구조로 답변하세요:
{{
  "title": "형성평가지 제목",
  "ox_quiz": [
    {{"q": "질문 내용", "a": "O 또는 X", "exp": "해설"}}
  ],
  "initial_quiz": [
    {{"q": "질문 내용 (초성 제시)", "a": "정답단어", "exp": "해설"}}
  ],
  "vocab_quiz": [
    {{"q": "질문 내용", "a": "정답단어", "exp": "해설"}}
  ],
  "mcq": [
    {{"q": "질문 내용", "options": ["보기1", "보기2", "보기3", "보기4"], "a": "정답번호(예: 1)", "exp": "해설"}}
  ]
}}
[수업 목표 및 핵심 아이디어 참고]
목표: {st.session_state.selected_session_detail['objective']}
아이디어: {st.session_state.selected_session_detail['big_idea']}
"""
                        try:
                            res4 = call_gemini_robust(st.session_state.api_key, prompt4)
                            st.session_state.quiz_detail = json.loads(res4.replace("```json", "").replace("```", "").strip())
                            st.success("형성평가 출제 완료! 마지막 6단계(인쇄) 탭으로 이동하세요.")
                        except Exception as e:
                            st.error(str(e))
            else:
                st.warning("3단계 지도안 생성을 완료해 주세요.")

        # [탭 6] 인쇄 출력 (3가지 통합 출력)
        with tab6:
            st.markdown("#### 🖨️ 생성 파일 원클릭 인쇄")
            st.caption("아래 버튼을 눌러 생성된 HTML 문서를 다운로드한 뒤 브라우저에서 열어 상단의 [인쇄하기] 버튼을 누르세요. 1단계에서 입력한 정보가 모두 반영되어 있습니다.")
            
            col_a, col_b, col_c = st.columns(3)
            
            # 정보 불러오기
            sub = st.session_state.final_subject
            s_name = st.session_state.get('school_name', '')
            c_date = st.session_state.get('class_date', '')
            c_loc = st.session_state.get('class_location', '')
            t_stud = st.session_state.get('target_students', '')
            t_name = st.session_state.get('teacher_name', '')
            
            # 학교명 조합 로직
            teacher_display = f"{s_name} {t_name}".strip() if s_name else t_name
            school_prefix = f"[{s_name}] " if s_name else ""
            
            # 1. 지도안 HTML
            if st.session_state.selected_session_detail:
                d = st.session_state.selected_session_detail
                html_plan = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>공개수업 지도안</title>
<style>
    @page {{ size: A4; margin: 20mm; }}
    body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.5; color: #000; }}
    h1 {{ text-align: center; font-size: 24px; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }}
    .header-table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; font-size: 14px; }}
    .header-table th {{ background-color: #f2f2f2; border: 1px solid #000; padding: 8px; width: 15%; text-align: center; }}
    .header-table td {{ border: 1px solid #000; padding: 8px; width: 35%; text-align: center; }}
    h2 {{ font-size: 16px; margin-top: 20px; color: #003366; }}
    .content-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; table-layout: fixed; }}
    .content-table th, .content-table td {{ border: 1px solid #000; padding: 10px; vertical-align: top; word-break: keep-all; }}
    .content-table th {{ background-color: #f2f2f2; text-align: center; font-weight: bold; }}
    .col-step {{ width: 10%; text-align: center; font-weight: bold; background-color: #f2f2f2; }}
    .col-time {{ width: 10%; text-align: center; }}
    .col-act {{ width: 60%; }}
    .col-note {{ width: 20%; font-size: 12px; color: #333; }}
    .print-btn {{ display: block; width: 200px; margin: 0 auto 20px auto; padding: 10px; background-color: #1a73e8; color: white; border: none; font-size: 16px; font-weight: bold; cursor: pointer; border-radius: 5px; text-align: center; }}
    @media print {{ .print-btn {{ display: none; }} }}
</style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">🖨️ 지도안 인쇄하기</button>
    <h1>{sub}과 교수·학습 과정안</h1>
    <table class="header-table">
        <tr><th>일 시</th><td>{c_date}</td><th>장 소</th><td>{c_loc}</td></tr>
        <tr><th>대 상</th><td>{t_stud}</td><th>지도 교사</th><td>{teacher_display}</td></tr>
    </table>
    <h2>| 1. 수업의 개요 및 개념기반 설계 의도</h2><p>{d.get('overview', '')}</p>
    <h2>| 2. 개념기반 교육과정(CBI) 목표 설정</h2>
    <ul>
        <li><b>거시 개념:</b> {d.get('macro', '')} &nbsp;&nbsp; <b>미시 개념:</b> {d.get('micro', '')}</li>
        <li><b>본시 학습 목표:</b> {d.get('objective', '')}</li>
        <li><b>핵심 아이디어(일반화):</b> {d.get('big_idea', '')}</li>
    </ul>
    <h2>| 3. 본시 교수·학습 과정안</h2>
    <table class="content-table">
        <tr><th class="col-step">단계</th><th class="col-time">시량</th><th class="col-act">교수·학습 활동</th><th class="col-note">자료(◆) 및 유의점(※)</th></tr>
        <tr><td class="col-step">도 입</td><td class="col-time">{d.get('intro_time', '10분')}</td><td class="col-act">{d.get('intro_act', '').replace(chr(10), '<br>')}</td><td class="col-note">{d.get('intro_note', '').replace(chr(10), '<br>')}</td></tr>
        <tr><td class="col-step">전 개</td><td class="col-time">{d.get('dev_time', '30분')}</td><td class="col-act">{d.get('dev_act', '').replace(chr(10), '<br>')}</td><td class="col-note">{d.get('dev_note', '').replace(chr(10), '<br>')}</td></tr>
        <tr><td class="col-step">정 리</td><td class="col-time">{d.get('conc_time', '10분')}</td><td class="col-act">{d.get('conc_act', '').replace(chr(10), '<br>')}</td><td class="col-note">{d.get('conc_note', '').replace(chr(10), '<br>')}</td></tr>
    </table>
</body>
</html>"""
                with col_a:
                    st.download_button("📥 1. 과정안 HTML", data=html_plan.encode('utf-8'), file_name=f"과정안_{d.get('session')}차시.html", mime="text/html", type="primary", use_container_width=True)

            # 2. 활동지 HTML
            if st.session_state.worksheet_detail:
                w = st.session_state.worksheet_detail
                d = st.session_state.selected_session_detail
                html_work = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>학생 활동지</title>
<style>
    @page {{ size: A4; margin: 20mm; }}
    body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #000; }}
    .header-box {{ border: 2px solid #000; padding: 15px; margin-bottom: 20px; border-radius: 8px; }}
    h1 {{ text-align: center; font-size: 22px; margin: 0 0 10px 0; }}
    .info-line {{ text-align: right; font-size: 15px; margin-bottom: 10px; font-weight: bold; color: #333; }}
    .concept-line {{ font-size: 13px; margin-bottom: 5px; }}
    h3 {{ font-size: 16px; background-color: #e9ecef; padding: 8px; border-radius: 5px; margin-top: 25px; }}
    p {{ font-size: 14px; margin: 10px 0; }}
    .print-btn {{ display: block; width: 200px; margin: 0 auto 20px auto; padding: 10px; background-color: #2b8a3e; color: white; border: none; font-size: 16px; font-weight: bold; cursor: pointer; border-radius: 5px; text-align: center; }}
    .box {{ border: 1px dashed #333; padding: 15px; min-height: 100px; margin-bottom: 10px; }}
    @media print {{ .print-btn {{ display: none; }} }}
</style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">🖨️ 활동지 인쇄하기</button>
    <div class="header-box">
        <h1>[탐구 활동지] {w.get('title', '')}</h1>
        <div class="info-line">{school_prefix}[{t_stud}] ___번 이름: _____________</div>
        <div class="concept-line"><b>[거시 개념]</b> {d.get('macro', '')} &nbsp;&nbsp; <b>[미시 개념]</b> {d.get('micro', '')}</div>
        <div class="concept-line"><b>[학습 목표]</b> {d.get('objective', '')}</div>
        <div class="concept-line"><b>★ [핵심 아이디어]</b> {d.get('big_idea', '')}</div>
    </div>
    <h3>{w.get('act1_title', '[활동 1]')}</h3><div class="box">{w.get('act1_desc', '수업 중 다룬 내용을 분석하여 정리해 봅시다.').replace(chr(10), '<br>')}</div>
    <h3>{w.get('act2_title', '[활동 2] 생각을 여는 질문 만들기')}</h3><p>※ 친구들과 토론할 수 있는 깊이 있는 질문을 만들어 보세요.</p><div class="box"><b>▶ 나의 탐구 질문: </b></div>
    <h3>{w.get('act3_title', '[활동 3] 나만의 관점 세우기')}</h3><p>[도움말] 1. 나는 ___라고 생각한다.<br>2. 왜냐하면 ___하기 때문이다.<br>3. 따라서 우리는 ___ 해야 한다.</p><div class="box" style="min-height: 150px;"></div>
    <h3>{w.get('wrap_up', '[마무리] 자기 점검 및 상호작용')}</h3><div class="box">{w.get('wrap_up', '나의 배움을 성찰하고 친구들과 공유해 봅시다.').replace(chr(10), '<br>')}</div>
</body>
</html>"""
                with col_b:
                    st.download_button("📥 2. 활동지 HTML", data=html_work.encode('utf-8'), file_name=f"활동지_{d.get('session')}차시.html", mime="text/html", type="primary", use_container_width=True)

            # 3. 형성평가지 HTML
            if st.session_state.quiz_detail:
                q = st.session_state.quiz_detail
                d = st.session_state.selected_session_detail
                
                ox_html = "".join([f"<li>{item['q']} ( O , X )</li>" for item in q.get('ox_quiz', [])])
                init_html = "".join([f"<li>{item['q']} ( 정답: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; )</li>" for item in q.get('initial_quiz', [])])
                vocab_html = "".join([f"<li>{item['q']}<br>( 정답: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; )</li>" for item in q.get('vocab_quiz', [])])
                
                mcq_html = ""
                for idx, item in enumerate(q.get('mcq', [])):
                    opts = item.get('options', [])
                    opt_str = "<ol>" + "".join([f"<li>{opt}</li>" for opt in opts]) + "</ol>"
                    mcq_html += f"<li>{item['q']}{opt_str}</li>"
                
                ans_html = "<ul>"
                for item in q.get('ox_quiz', []): ans_html += f"<li><b>[O/X]</b> 정답: {item['a']} - {item.get('exp','')}</li>"
                for item in q.get('initial_quiz', []): ans_html += f"<li><b>[초성]</b> 정답: {item['a']} - {item.get('exp','')}</li>"
                for item in q.get('vocab_quiz', []): ans_html += f"<li><b>[어휘]</b> 정답: {item['a']} - {item.get('exp','')}</li>"
                for item in q.get('mcq', []): ans_html += f"<li><b>[객관식]</b> 정답: {item['a']} - {item.get('exp','')}</li>"
                ans_html += "</ul>"

                html_quiz = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>형성평가지</title>
<style>
    @page {{ size: A4; margin: 20mm; }}
    body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #000; }}
    .header-box {{ border: 2px solid #000; padding: 15px; margin-bottom: 20px; border-radius: 8px; text-align: center; }}
    h1 {{ font-size: 24px; margin: 0 0 10px 0; }}
    .info-line {{ text-align: right; font-size: 15px; font-weight: bold; color: #333; }}
    h3 {{ font-size: 16px; margin-top: 25px; border-left: 5px solid #003366; padding-left: 10px; }}
    ol, ul {{ margin-top: 5px; }}
    li {{ margin-bottom: 15px; font-size: 15px; }}
    .print-btn {{ display: block; width: 200px; margin: 0 auto 20px auto; padding: 10px; background-color: #f59f00; color: white; border: none; font-size: 16px; font-weight: bold; cursor: pointer; border-radius: 5px; text-align: center; }}
    .answer-box {{ border: 1px dashed #777; padding: 15px; margin-top: 40px; background-color: #f9f9f9; }}
    .answer-box h4 {{ margin-top: 0; color: #e03131; }}
    @media print {{ .print-btn {{ display: none; }} }}
</style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">🖨️ 형성평가지 인쇄하기</button>
    <div class="header-box">
        <h1>[형성평가] {q.get('title', '단원 점검 퀴즈')}</h1>
        <div class="info-line">{school_prefix}[{t_stud}] ___번 이름: _____________</div>
    </div>
    
    <h3>🎯 O/X 퀴즈</h3><ul>{ox_html}</ul>
    <h3>🎯 초성 퀴즈</h3><ul>{init_html}</ul>
    <h3>🎯 어휘 퀴즈</h3><ul>{vocab_html}</ul>
    <h3>🎯 객관식 퀴즈 (4지선다)</h3><ol>{mcq_html}</ol>
    
    <div class="answer-box">
        <h4>[교사용] 정답 및 해설 (인쇄 전 절취선)</h4>
        {ans_html}
    </div>
</body>
</html>"""
                with col_c:
                    st.download_button("📥 3. 형성평가 HTML", data=html_quiz.encode('utf-8'), file_name=f"형성평가_{d.get('session')}차시.html", mime="text/html", type="primary", use_container_width=True)

    # --- 3. 학생 세특 초안 ---
    elif st.session_state.current_page == "세특 초안":
        st.subheader("💡 학생 세특(관찰) 초안 생성기")
        st.info("NEIS 학교생활기록부 양식에 맞춰 교과 세특 문장을 자동 완성합니다.")
        col1, col2 = st.columns(2)
        with col1: stu_name = st.text_input("학생 이름")
        with col2: stu_level = st.selectbox("성취 수준", ["상 (우수함, 주도적)", "중 (성실함, 무난함)", "하 (노력 요함)"])
        stu_activity = st.text_area("주요 관찰 내용 및 활동 키워드", placeholder="예) 인공지능 윤리를 주제로 한 찬반 토론에서 사회자 역할을 맡아 갈등을 조율함.")
        
        if st.button("✨ 세특 초안 생성하기", type="primary"):
            api_key_check = st.session_state.get("api_key", "")
            if not api_key_check:
                st.error("과정안 생성 메뉴의 1단계 탭에서 API 키를 먼저 입력해 주세요.")
            elif stu_name and stu_activity:
                with st.spinner("NEIS 양식에 맞게 문장을 작성 중입니다..."):
                    prompt = f"당신은 고등학교 {st.session_state.final_subject} 교사입니다. 학생 '{stu_name}'의 세특을 작성합니다. 수준: {stu_level} / 관찰: {stu_activity}. 명사형 종결어미(~함, ~임)를 사용하고, 500자 내외로 전문적이고 긍정적으로 작성하세요."
                    try:
                        res_text = call_gemini_robust(api_key_check, prompt)
                        st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
                        st.markdown(res_text)
                        st.markdown("</div>", unsafe_allow_html=True)
                    except Exception as e:
                        st.error(str(e))
            else:
                st.warning("학생 이름과 활동 내용을 입력해 주세요.")

    # --- 4. 학급 알림장/문자 ---
    elif st.session_state.current_page == "알림장":
        st.subheader("💌 학급 알림장/가정통신문 자동 생성기")
        st.info("거친 메모를 학부모님께 보내기 좋은 정중하고 친절한 문자로 다듬어 드립니다.")
        msg_context = st.text_area("전달할 핵심 내용 입력", placeholder="예) 내일 체험학습 감. 도시락 꼭 싸오고 8시 반까지 운동장 집합.")
        
        if st.button("💌 알림장 문구 생성", type="primary"):
            api_key_check = st.session_state.get("api_key", "")
            if not api_key_check:
                st.error("과정안 생성 메뉴의 1단계 탭에서 API 키를 먼저 입력해 주세요.")
            elif msg_context:
                with st.spinner("정중한 문구로 변환 중입니다..."):
                    prompt = f"당신은 다정하고 꼼꼼한 고등학교 담임교사입니다. 내용을 학부모님과 학생 단체 문자로 보낼 수 있게 알림장 형태로 다듬어주세요. 전달 내용: {msg_context}. 인사말로 시작해 끝맺음 인사를 포함하고 줄바꿈과 이모지를 적절히 사용하세요."
                    try:
                        res_text = call_gemini_robust(api_key_check, prompt)
                        st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
                        st.markdown(res_text)
                        st.markdown("</div>", unsafe_allow_html=True)
                    except Exception as e:
                        st.error(str(e))
            else:
                st.warning("전달할 내용을 입력해 주세요.")

    # --- 5. 온라인 등록부 ---
    elif st.session_state.current_page == "등록부":
        st.subheader("📋 온라인 등록부 및 전자 서명")
        with st.expander("⚙️ 연수명 관리 (비밀번호: 1234)"):
            pwd_input = st.text_input("비밀번호", type="password")
            if pwd_input == "1234":
                new_training = st.text_input("새로운 연수명 입력")
                if st.button("➕ 연수명 추가"):
                    st.session_state.training_list.append(new_training)
                    st.success("추가 완료!")
                    st.rerun()
        
        st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
        selected_training = st.selectbox("📌 연수명 선택", st.session_state.training_list)
        c1, c2, c3 = st.columns(3)
        with c1: in_dept = st.text_input("소속")
        with c2: in_pos = st.text_input("직위")
        with c3: in_name = st.text_input("이름")
        
        st.write("✍️ **서명** (아래 캔버스에 서명하세요)")
        st_canvas(stroke_width=2, stroke_color="#000", background_color="#f0f0f0", height=100, width=400, drawing_mode="freedraw", key="sig")
        
        if st.button("✅ 서명 완료 및 제출", type="primary", use_container_width=True):
            if in_name:
                new_row = pd.DataFrame([{"연번": len(st.session_state.registry_df)+1, "연수명": selected_training, "소속": in_dept, "직위": in_pos, "이름": in_name, "서명 상태": "✅ 완료", "등록 일시": datetime.now().strftime("%m-%d %H:%M")}])
                st.session_state.registry_df = pd.concat([st.session_state.registry_df, new_row], ignore_index=True)
                st.success(f"{in_name}님 등록 완료!")
            else:
                st.warning("이름을 입력하세요.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.write("---")
        st.dataframe(st.session_state.registry_df, hide_index=True, use_container_width=True)
        if not st.session_state.registry_df.empty:
            st.download_button("📥 엑셀(CSV) 다운로드", data=st.session_state.registry_df.to_csv(index=False, encoding='utf-8-sig'), file_name="등록부.csv", mime="text/csv")

# ==========================================
# [오른쪽 20%] 유용한 교육/생활 정보
# ==========================================
with col_info:
    st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
    st.markdown("#### 🌤️ 오늘의 날씨")
    st.markdown("**전남 광양시 중마동**")
    st.markdown("<h2 style='margin:0; color:#ffb3c6;'>18°C / 맑음</h2>", unsafe_allow_html=True)
    st.caption("미세먼지: 좋음 🟢 | 강수확률: 0%")
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
    st.markdown("#### 💡 에듀테크 꿀팁")
    st.markdown("**Canva(캔바) 업데이트**")
    st.write("새로운 '매직스튜디오' 기능으로 텍스트만 입력하면 수업용 슬라이드 배경이 자동 생성됩니다.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
    st.markdown("#### 📅 주요 일정")
    st.write("• **10/14:** 국어교육연구회 공개수업")
    st.write("• **10월 3주차:** 학생 세특 초안 작성")
    st.write("• **1월:** 나고야 가족 겨울 여행 준비")
    st.markdown("</div>", unsafe_allow_html=True)
