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
st.set_page_config(page_title="AI 교무·학습 수퍼 앱", layout="wide", initial_sidebar_state="collapsed")

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
if "api_key" not in st.session_state: st.session_state.api_key = ""

if "training_list" not in st.session_state: 
    st.session_state.training_list = ["2026학년도 새학년 집중준비기간 연수", "전남글빛국어교육연구회 공개수업"]
if "registry_df" not in st.session_state: 
    st.session_state.registry_df = pd.DataFrame(columns=["연번", "연수명", "소속", "직위", "이름", "서명 상태", "등록 일시"])

st.title("✨ AI 맞춤형 교무·학습 지원 시스템")
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
    nav_button("📝 과정안/활동지 생성", "과정안 생성")
    
    st.markdown("<div class='menu-title'>📝 평가/기록 지원</div>", unsafe_allow_html=True)
    nav_button("💡 학생 세특 초안", "세특 초안")
    
    st.markdown("<div class='menu-title'>🏫 행정/학급 운영</div>", unsafe_allow_html=True)
    nav_button("📋 온라인 등록부", "등록부")
    nav_button("💌 학급 알림장/문자", "알림장")
    
    st.write("---")
    st.markdown("##### ⚙️ 교과 설정")
    selected_subject = st.selectbox("📚 담당 과목", ["공통국어", "윤리와 사상", "생활과 윤리", "기타"], label_visibility="collapsed")
    
    # 🌟 새롭게 추가된 인쇄물 기본 정보 입력칸
    st.markdown("##### 🖨️ 출력물 정보 (수정 가능)")
    class_date = st.text_input("수업 일시", value="2026. 10. 14. (수) 14:00")
    class_location = st.text_input("수업 장소", value="1학년 6반 교실")
    target_students = st.text_input("수업 대상", value="1학년 6반 학생")
    teacher_name = st.text_input("지도 교사", value="유일한")
    
    st.write("---")
    st.session_state.api_key = st.text_input("🔑 Gemini API 키 입력", type="password")

with col_main:
    if st.session_state.current_page == "과정안 생성":
        st.subheader(f"📝 {selected_subject} 공개수업 과정안 & 활동지 생성기")
        uploaded_file = st.file_uploader("📄 교과서 PDF 업로드", type=["pdf"])
        tab1, tab2, tab3, tab4 = st.tabs(["📊 1. 분석", "🎯 2. 지도안 생성", "📝 3. 활동지 생성", "🖨️ 4. 인쇄 출력"])
        
        # [탭 1] 단원 분석
        with tab1:
            if uploaded_file and st.session_state.api_key:
                if st.button("🚀 AI 분석 시작", type="primary"):
                    with st.spinner("AI가 교과서를 분석 중입니다..."):
                        text_data = ""
                        with pdfplumber.open(uploaded_file) as pdf:
                            for page in pdf.pages:
                                ext = page.extract_text()
                                if ext: text_data += ext + "\n"
                        st.session_state.extracted_text = text_data
                        
                        prompt1 = f"당신은 고등학교 {selected_subject} 수석 교사입니다. 텍스트를 분석해 최적 총 차시를 설계하세요. JSON 배열로 답변 (키: session, type, title, desc). [내용] {text_data}"
                        try:
                            res1 = call_gemini_robust(st.session_state.api_key, prompt1)
                            st.session_state.proposed_sessions = json.loads(res1.replace("```json", "").replace("```", "").strip())
                            st.success("분석 완료! 2단계로 이동하세요.")
                        except Exception as e:
                            st.error(str(e))
            else:
                st.info("좌측에 API 키를 입력하고 교과서 PDF를 업로드해 주세요.")
                
        # [탭 2] 공개수업 지도안 생성
        with tab2:
            if st.session_state.proposed_sessions:
                options = {f"{s['session']}차시 - {s['title']}": s for s in st.session_state.proposed_sessions}
                sel_opt = st.radio("과정안 차시 선택:", list(options.keys()))
                if st.button("📝 공개수업 지도안 생성", type="primary"):
                    chosen = options[sel_opt]
                    with st.spinner("개념기반(CBI) 공개수업 지도안을 작성 중입니다..."):
                        prompt2 = f"""당신은 {selected_subject} 수석 교사입니다. 주제: {chosen['title']}. 전남글빛국어교육연구회 공개수업 스타일로 다음 구조의 JSON을 생성하세요:
{{
  "overview": "수업 개요 및 설계 의도 (2~3문장)",
  "macro": "거시 개념 (예: #관점 #통합)",
  "micro": "미시 개념 (예: #형식과 맥락)",
  "objective": "본시 학습 목표",
  "big_idea": "핵심 아이디어 (일반화)",
  "intro_act": "도입 활동 (동기유발, 퀴즈 등)", "intro_time": "10분", "intro_note": "지도상 유의점",
  "dev_act": "전개 활동 (구체적 교사-학생 발문, 관점 세우기 3단계 등)", "dev_time": "30분", "dev_note": "태블릿 활용 등",
  "conc_act": "정리 활동 (온라인 보드 공유, 하트/댓글 소통 등)", "conc_time": "10분", "conc_note": "상호작용 강조"
}}
[내용] {st.session_state.extracted_text}"""
                        try:
                            res2 = call_gemini_robust(st.session_state.api_key, prompt2)
                            st.session_state.selected_session_detail = json.loads(res2.replace("```json", "").replace("```", "").strip())
                            st.session_state.selected_session_detail.update({'session': chosen['session'], 'title': chosen['title']})
                            st.success("지도안 완성! 3단계로 이동하세요.")
                        except Exception as e:
                            st.error(str(e))
            else:
                st.warning("1단계 분석을 완료해 주세요.")

        # [탭 3] A4 학생 활동지 생성
        with tab3:
            if st.session_state.selected_session_detail:
                if st.button("📝 A4 학생 활동지 생성", type="primary"):
                    with st.spinner("A4 출력용 맞춤형 학생 활동지를 디자인 중입니다..."):
                        prompt3 = f"""당신은 {selected_subject} 수석 교사입니다. 앞서 만든 '{st.session_state.selected_session_detail['title']}' 수업의 학생 배부용 활동지를 만듭니다. 
반드시 아래 JSON 구조로 답변하세요:
{{
  "title": "활동지 제목",
  "act1_title": "[활동 1] 본문 비교·분석하기 (제목, 관점, 형식적 특징 표 형태로 구성할 내용)",
  "act2_title": "[활동 2] 생각을 여는 탐구 질문 만들기 (피해야 할 질문 vs 좋은 질문 예시 포함)",
  "act3_title": "[활동 3] 나만의 관점 세우기 (비판적 재구성 - 3단 마법의 문장 틀 포함)",
  "wrap_up": "[마무리 소통 활동] 퀴즈앤(QuizN) 보드 공유 및 상호작용 체크리스트"
}}"""
                        try:
                            res3 = call_gemini_robust(st.session_state.api_key, prompt3)
                            st.session_state.worksheet_detail = json.loads(res3.replace("```json", "").replace("```", "").strip())
                            st.success("활동지 완성! 4단계(인쇄)로 이동하세요.")
                        except Exception as e:
                            st.error(str(e))
            else:
                st.warning("2단계 지도안 생성을 완료해 주세요.")

        # [탭 4] 인쇄 출력 (입력된 정보 자동 적용)
        with tab4:
            col_a, col_b = st.columns(2)
            
            # 1. 지도안 HTML 다운로드
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
    <h1>{selected_subject}과 교수·학습 과정안</h1>
    
    <!-- 좌측에서 입력한 정보가 들어가는 표 -->
    <table class="header-table">
        <tr>
            <th>일 시</th><td>{class_date}</td>
            <th>장 소</th><td>{class_location}</td>
        </tr>
        <tr>
            <th>대 상</th><td>{target_students}</td>
            <th>지도 교사</th><td>{teacher_name}</td>
        </tr>
    </table>

    <h2>| 1. 수업의 개요 및 설계 의도</h2>
    <p>{d.get('overview', '')}</p>
    <h2>| 2. 개념기반 교육과정(CBI) 기반 목표 설정</h2>
    <ul>
        <li><b>거시 개념:</b> {d.get('macro', '')} &nbsp;&nbsp; <b>미시 개념:</b> {d.get('micro', '')}</li>
        <li><b>본시 학습 목표:</b> {d.get('objective', '')}</li>
        <li><b>핵심 아이디어:</b> {d.get('big_idea', '')}</li>
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
                    st.download_button("📥 [교사용] 지도안 다운로드 (HTML)", data=html_plan.encode('utf-8'), file_name=f"공개수업지도안_{d.get('session')}차시.html", mime="text/html", type="primary")

            # 2. 활동지 HTML 다운로드
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
    <button class="print-btn" onclick="window.print()">🖨️ A4 활동지 인쇄하기</button>
    <div class="header-box">
        <h1>[개념기반 탐구 활동지] {w.get('title', '')}</h1>
        <!-- 좌측에서 입력한 대상(target_students) 자동 삽입 -->
        <div class="info-line">[{target_students}] ___번 이름: _____________</div>
        <div class="concept-line"><b>[거시 개념]</b> {d.get('macro', '')} &nbsp;&nbsp; <b>[미시 개념]</b> {d.get('micro', '')}</div>
        <div class="concept-line"><b>[학습 목표]</b> {d.get('objective', '')}</div>
        <div class="concept-line"><b>★ [핵심 아이디어]</b> {d.get('big_idea', '')}</div>
    </div>
    
    <h3>{w.get('act1_title', '[활동 1]')}</h3>
    <div class="box">{w.get('act1_desc', '수업 중 다룬 텍스트의 관점과 형식을 표 형태로 정리해 봅시다.').replace(chr(10), '<br>')}</div>
    
    <h3>{w.get('act2_title', '[활동 2] 생각을 여는 질문 만들기')}</h3>
    <p>※ 정답이 정해진 질문 대신, 친구들과 토론할 수 있는 깊이 있는 질문을 만들어 보세요.</p>
    <div class="box"><b>▶ 나의 탐구 질문: </b></div>

    <h3>{w.get('act3_title', '[활동 3] 나만의 관점 세우기')}</h3>
    <p>[도움말] 3단 마법의 문장 틀을 활용해 보세요!<br>1. 나는 앞선 질문에 대해 _____라고 생각한다.<br>2. 왜냐하면 교과서의 _____ 부분에서 알 수 있듯이, _____하기 때문이다.<br>3. 따라서 우리는 _____ 해야 한다.</p>
    <div class="box" style="min-height: 150px;"></div>

    <h3>{w.get('wrap_up', '[마무리] 자기 점검 및 상호작용')}</h3>
    <p>□ 내 초안을 퀴즈앤 게시판에 올렸나요?<br>□ 친구의 글 3개 이상 읽고 하트(♥)를 눌렀나요?<br>□ 존중을 담은 댓글을 1개 이상 남겼나요?</p>
</body>
</html>"""
                with col_b:
                    st.download_button("📥 [학생용] A4 활동지 다운로드", data=html_work.encode('utf-8'), file_name=f"학생활동지_{d.get('session')}차시.html", mime="text/html", type="primary")

    # --- 3. 학생 세특 초안 ---
    elif st.session_state.current_page == "세특 초안":
        st.subheader("💡 학생 세특(관찰) 초안 생성기")
        st.info("NEIS 학교생활기록부 양식에 맞춰 교과 세특 문장을 자동 완성합니다.")
        col1, col2 = st.columns(2)
        with col1: stu_name = st.text_input("학생 이름")
        with col2: stu_level = st.selectbox("성취 수준", ["상 (우수함, 주도적)", "중 (성실함, 무난함)", "하 (노력 요함)"])
        stu_activity = st.text_area("주요 관찰 내용 및 활동 키워드", placeholder="예) 인공지능 윤리를 주제로 한 찬반 토론에서 사회자 역할을 맡아 갈등을 조율함.")
        
        if st.button("✨ 세특 초안 생성하기", type="primary"):
            if not st.session_state.api_key:
                st.error("좌측에 API 키를 입력해 주세요.")
            elif stu_name and stu_activity:
                with st.spinner("NEIS 양식에 맞게 문장을 작성 중입니다..."):
                    prompt = f"당신은 고등학교 {selected_subject} 교사입니다. 학생 '{stu_name}'의 세특을 작성합니다. 수준: {stu_level} / 관찰: {stu_activity}. 명사형 종결어미(~함, ~임)를 사용하고, 500자 내외로 전문적이고 긍정적으로 작성하세요."
                    try:
                        res_text = call_gemini_robust(st.session_state.api_key, prompt)
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
            if not st.session_state.api_key:
                st.error("좌측에 API 키를 입력해 주세요.")
            elif msg_context:
                with st.spinner("정중한 문구로 변환 중입니다..."):
                    prompt = f"당신은 다정하고 꼼꼼한 고등학교 담임교사입니다. 내용을 학부모님과 학생 단체 문자로 보낼 수 있게 알림장 형태로 다듬어주세요. 전달 내용: {msg_context}. 인사말로 시작해 끝맺음 인사를 포함하고 줄바꿈과 이모지를 적절히 사용하세요."
                    try:
                        res_text = call_gemini_robust(st.session_state.api_key, prompt)
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
