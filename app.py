import streamlit as st
import pdfplumber
import json
import io
import time
import pandas as pd
from datetime import datetime
from streamlit_drawable_canvas import st_canvas
from google import genai  # 구글 최신 공식 SDK

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

# ---------------------------------------------------------
# 2. 세션 상태 초기화
# ---------------------------------------------------------
if "current_page" not in st.session_state: st.session_state.current_page = "과정안 생성"
if "extracted_text" not in st.session_state: st.session_state.extracted_text = ""
if "proposed_sessions" not in st.session_state: st.session_state.proposed_sessions = None
if "selected_session_detail" not in st.session_state: st.session_state.selected_session_detail = None
if "extra_materials" not in st.session_state: st.session_state.extra_materials = None
if "api_key" not in st.session_state: st.session_state.api_key = ""

if "training_list" not in st.session_state: 
    st.session_state.training_list = ["2026학년도 새학년 집중준비기간 연수", "전남글빛국어교육연구회 공개수업"]
if "registry_df" not in st.session_state: 
    st.session_state.registry_df = pd.DataFrame(columns=["연번", "연수명", "소속", "직위", "이름", "서명 상태", "등록 일시"])

# 상단 헤더
st.title("✨ AI 맞춤형 교무·학습 지원 시스템")
st.write("---")

# ==========================================
# 🌟 [최신 3.8-flash 적용 & 503 과부하 방어 로직]
# ==========================================
def call_gemini_robust(api_key, prompt, max_retries=3):
    client = genai.Client(api_key=api_key)
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
            )
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

# ==========================================
# [왼쪽 20%] 업무 내비게이션 메뉴
# ==========================================
def nav_button(label, page_name):
    is_active = (st.session_state.current_page == page_name)
    if st.button(label, type="primary" if is_active else "secondary", use_container_width=True):
        st.session_state.current_page = page_name
        st.rerun()

with col_menu:
    st.subheader("📌 업무 메뉴")
    
    st.markdown("<div class='menu-title'>📚 수업 지원</div>", unsafe_allow_html=True)
    nav_button("📝 과정안 생성기", "과정안 생성")
    nav_button("🎨 보조 자료 추출", "보조 자료")
    
    st.markdown("<div class='menu-title'>📝 평가/기록 지원</div>", unsafe_allow_html=True)
    nav_button("🎯 평가 문항 출제", "문항 출제")
    nav_button("💡 학생 세특 초안", "세특 초안")
    
    st.markdown("<div class='menu-title'>🏫 행정/학급 운영</div>", unsafe_allow_html=True)
    nav_button("📋 온라인 등록부", "등록부")
    nav_button("💌 학급 알림장/문자", "알림장")
    
    st.write("---")
    st.markdown("##### ⚙️ 기본 설정")
    selected_subject = st.selectbox("📚 담당 과목", ["공통국어", "윤리와 사상", "생활과 윤리", "기타"], label_visibility="collapsed")
    
    st.session_state.api_key = st.text_input("🔑 Gemini API 키 입력", type="password")
    
    st.markdown("<br><p style='font-size:11px; color:#2b8a3e; font-weight:bold;'>🟢 gemini-3.8-flash (트래픽 방어 모드)</p>", unsafe_allow_html=True)

# ==========================================
# [가운데 60%] 메인 작업 영역
# ==========================================
with col_main:
    # --- 1. 과정안 생성기 ---
    if st.session_state.current_page == "과정안 생성":
        st.subheader(f"📝 {selected_subject} 교수학습 과정안 생성기")
        uploaded_file = st.file_uploader("📄 교과서 PDF 업로드", type=["pdf"])
        tab1, tab2, tab3 = st.tabs(["📊 1. 단원 분석", "🎯 2. 차시 선택", "📝 3. 인쇄 출력"])
        
        with tab1:
            if uploaded_file and st.session_state.api_key:
                if st.button("🚀 AI 분석 시작", type="primary"):
                    with st.spinner("최신 AI가 교과서를 꼼꼼히 분석 중입니다..."):
                        text_data = ""
                        with pdfplumber.open(uploaded_file) as pdf:
                            for page in pdf.pages:
                                ext = page.extract_text()
                                if ext: text_data += ext + "\n"
                        st.session_state.extracted_text = text_data
                        
                        prompt1 = f"당신은 고등학교 {selected_subject} 수석 교사입니다. 다음 텍스트를 분석해 최적 총 차시를 설계하세요. 반드시 JSON 배열 형식으로만 답변하세요 (키: session, type, title, desc). [내용] {text_data}"
                        try:
                            res1_text = call_gemini_robust(st.session_state.api_key, prompt1)
                            clean_txt = res1_text.replace("```json", "").replace("```", "").strip()
                            st.session_state.proposed_sessions = json.loads(clean_txt)
                            st.success("분석 완료! 2단계 탭으로 이동하세요.")
                        except Exception as e:
                            st.error(str(e))
            else:
                st.info("좌측에 개인 API 키를 넣고 교과서 PDF를 업로드해 주세요.")
                
        with tab2:
            if st.session_state.proposed_sessions:
                options = {f"{s['session']}차시 [{s['type']}] - {s['title']}": s for s in st.session_state.proposed_sessions}
                selected_option = st.radio("과정안을 생성할 차시 선택:", list(options.keys()))
                if st.button("📝 과정안 생성하기", type="primary"):
                    chosen_session = options[selected_option]
                    with st.spinner("공개수업용 수준의 상세 과정안을 작성 중입니다..."):
                        # 공개수업지도안 수준의 초정밀 프롬프트로 변경
                        prompt2 = f"""당신은 고등학교 {selected_subject} 수석 교사입니다. 
차시: {chosen_session['session']} / 주제: {chosen_session['title']}. 
실제 '공개 수업'에 바로 제출할 수 있는 수준의 매우 전문적이고 상세한 교수·학습 과정안을 작성
