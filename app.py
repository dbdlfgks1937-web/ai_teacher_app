import streamlit as st
import pdfplumber
import json
import io
import pandas as pd
from datetime import datetime
from docx import Document
from streamlit_drawable_canvas import st_canvas
import requests  # 외부 라이브러리 충돌을 원천 차단하는 표준 통신 모듈

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
# 🌟 [1번 방식] 순수 REST API 직접 호출 함수 (v1 / gemini-1.5-flash)
# ==========================================
def call_gemini_direct(api_key, prompt):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        try:
            return result['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError) as e:
            raise Exception(f"응답 데이터 파싱 오류: {result}")
    else:
        # 구글 서버에서 반환하는 정확한 에러 메시지를 함께 출력합니다.
        try:
            err_msg = response.json().get('error', {}).get('message', response.text)
        except:
            err_msg = response.text
        raise Exception(f"Google API 오류 ({response.status_code}): {err_msg}")

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
    
    tooltip_html = """
    <div style='margin-bottom: 5px;'>
        <span style='font-size: 14px; font-weight: 600; color: #495057;'>🔑 Gemini API 키</span>
        <div class="tooltip">?
            <span class="tooltiptext">
                <strong>[API 키 발급 및 보안 안내]</strong><br><br>
                • <strong>발급 방법:</strong> Google AI Studio 접속 > 'Get API key' 클릭 > 복사<br>
                • <strong>왜 필요한가요?</strong> 선생님만의 전용 회선으로 AI를 호출하여 대기 시간 없이 빠르고 정확한 결과를 얻기 위함입니다.<br>
                • <strong>보안:</strong> 입력하신 키는 이 브라우저를 닫으면 <strong>즉시 사라지며</strong>, 외부에 절대 유출되지 않습니다.
            </span>
        </div>
    </div>
    """
    st.markdown(tooltip_html, unsafe_allow_html=True)
    st.session_state.api_key = st.text_input("Gemini API 키", type="password", label_visibility="collapsed")
    
    st.markdown("<br><p style='font-size:11px; color:#2b8a3e; font-weight:bold;'>🟢 시스템 상태: 순수 표준 REST API 연동됨</p>", unsafe_allow_html=True)

# ==========================================
# [가운데 60%] 메인 작업 영역
# ==========================================
with col_main:
    # --- 1. 과정안 생성기 ---
    if st.session_state.current_page == "과정안 생성":
        st.subheader(f"📝 {selected_subject} 교수학습 과정안 생성기")
        uploaded_file = st.file_uploader("📄 교과서 PDF 업로드", type=["pdf"])
        tab1, tab2, tab3 = st.tabs(["📊 1. 단원 분석", "🎯 2. 차시 선택", "📝 3. 문서 출력"])
        
        with tab1:
            if uploaded_file and st.session_state.api_key:
                if st.button("🚀 AI 분석 시작", type="primary"):
                    with st.spinner("표준 회선을 통해 교과서를 꼼꼼히 분석 중입니다..."):
                        text_data = ""
                        with pdfplumber.open(uploaded_file) as pdf:
                            for page in pdf.pages:
                                ext = page.extract_text()
                                if ext: text_data += ext + "\n"
                        st.session_state.extracted_text = text_data
                        
                        prompt1 = f"당신은 고등학교 {selected_subject} 교육 전문가입니다. 다음 교과서 텍스트를 분석해 최적 총 차시를 설계하세요. 반드시 JSON 배열 형식으로만 답변하세요 (키: session, type, title, desc). [내용] {text_data}"
                        try:
                            res1_text = call_gemini_direct(st.session_state.api_key, prompt1)
                            clean_txt = res1_text.replace("```json", "").replace("```", "").strip()
                            st.session_state.proposed_sessions = json.loads(clean_txt)
                            st.success("분석 완료! 2단계 탭으로 이동하세요.")
                        except Exception as e:
                            st.error(f"오류가 발생했습니다: {e}")
            else:
                st.info("좌측에 API 키를 넣고 교과서 PDF를 업로드해 주세요.")
                
        with tab2:
            if st.session_state.proposed_sessions:
                options = {f"{s['session']}차시 [{s['type']}] - {s['title']}": s for s in st.session_state.proposed_sessions}
                selected_option = st.radio("과정안을 생성할 차시 선택:", list(options.keys()))
                if st.button("📝 과정안 생성하기", type="primary"):
                    chosen_session = options[selected_option]
                    with st.spinner("상세 과정안을 작성 중입니다..."):
                        prompt2 = f"당신은 고등학교 {selected_subject} 교육 전문가입니다. 차시: {chosen_session['session']} / 주제: {chosen_session['title']}. 반드시 JSON 형식(unit, objectives, intro_act, dev_act, conc_act)으로 답변하세요. [내용] {st.session_state.extracted_text}"
                        try:
                            res2_text = call_gemini_direct(st.session_state.api_key, prompt2)
                            clean_txt2 = res2_text.replace("```json", "").replace("```", "").strip()
                            st.session_state.selected_session_detail = json.loads(clean_txt2)
                            st.session_state.selected_session_detail.update({'type': chosen_session['type'], 'session': chosen_session['session']})
                            st.success("과정안 완성! 3단계 탭으로 이동하세요.")
                        except Exception as e:
                            st.error(f"오류가 발생했습니다: {e}")
            else:
                st.warning("1단계 분석을 완료해 주세요.")
                
        with tab3:
            if st.session_state.selected_session_detail:
                data = st.session_state.selected_session_detail
                st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
                st.write(f"### ✅ {data['session']}차시 교수학습 과정안")
                st.markdown(f"**학습목표:** {data['objectives']}")
                
                def create_docx(plan_data):
                    doc = Document()
                    doc.add_heading(f"{selected_subject} {plan_data['session']}차시 과정안", 0)
                    table = doc.add_table(rows=5, cols=2)
                    table.style = 'Table Grid'
                    rows = table.rows
                    rows[0].cells[0].text, rows[0].cells[1].text = "단원", plan_data['unit']
                    rows[1].cells[0].text, rows[1].cells[1].text = "학습 목표", plan_data['objectives']
                    rows[2].cells[0].text, rows[2].cells[1].text = "도입", plan_data['intro_act']
                    rows[3].cells[0].text, rows[3].cells[1].text = "전개", plan_data['dev_act']
                    rows[4].cells[0].text, rows[4].cells[1].text = "정리", plan_data['conc_act']
                    docx_buffer = io.BytesIO()
                    doc.save(docx_buffer)
                    return docx_buffer.getvalue()

                st.download_button("📝 워드(Docx) 다운로드", data=create_docx(data), file_name=f"과정안_{data['session']}차시.docx")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.warning("2단계에서 차시를 선택해 주세요.")

    # --- 2. 보조 자료 추출 ---
    elif st.session_state.current_page == "보조 자료":
        st.subheader("🎨 수업 보조 자료 자동 생성기")
        if st.session_state.selected_session_detail:
            if st.button("🚀 보조 자료(퀴즈/루브릭/캔바 대본) 일괄 생성", type="primary"):
                with st.spinner("수업 자료를 생성 중입니다..."):
                    plan_text = json.dumps(st.session_state.selected_session_detail, ensure_ascii=False)
                    prompt3 = f"당신은 고등학교 {selected_subject} 수석 교사입니다. 다음 교수학습 과정안을 바탕으로 실제 수업에 활용할 3가지 보조 자료를 마크다운 형식으로 작성하세요. 1. 퀴즈앤/패들렛용 핵심 질문 3가지 2. 수행평가/탐구 활동지 3단계 채점 루브릭 (상/중/하) 3. 캔바(Canva) 수업 슬라이드 구성안 (4~5장 대본). [과정안 데이터] {plan_text}"
                    try:
                        res3_text = call_gemini_direct(st.session_state.api_key, prompt3)
                        st.session_state.extra_materials = res3_text
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {e}")
                        
            if st.session_state.extra_materials:
                st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
                st.markdown(st.session_state.extra_materials)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("먼저 '과정안 생성' 메뉴에서 2단계까지 완료해 주세요.")

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
                        res_text = call_gemini_direct(st.session_state.api_key, prompt)
                        st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
                        st.markdown(res_text)
                        st.markdown("</div>", unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {e}")
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
                        res_text = call_gemini_direct(st.session_state.api_key, prompt)
                        st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
                        st.markdown(res_text)
                        st.markdown("</div>", unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {e}")
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

    else:
        st.subheader(st.session_state.current_page)
        st.write("🚀 이 기능은 곧 채워질 예정입니다!")

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