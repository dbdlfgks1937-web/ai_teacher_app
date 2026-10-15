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
실제 '공개 수업'에 바로 제출할 수 있는 수준의 매우 전문적이고 상세한 교수·학습 과정안을 작성해 주세요. 
교사와 학생의 상호작용(발문), 형성평가, 차시 예고 등을 꼼꼼히 포함해야 합니다.
반드시 아래 키(key)를 가진 JSON 형식으로 답변하세요:
{{
  "unit": "단원명",
  "objectives": "성취기준 및 학습목표",
  "intro": "도입 (동기유발, 전시학습 상기 등 구체적 활동)",
  "development": "전개 (주요 학습 활동, 교사-학생 발문 상호작용 상세히)",
  "conclusion": "정리 (형성평가, 내용 요약, 차시 예고)",
  "evaluation": "평가 계획 및 기준",
  "notes": "지도상의 유의점 및 준비물"
}}
[내용] {st.session_state.extracted_text}"""
                        try:
                            res2_text = call_gemini_robust(st.session_state.api_key, prompt2)
                            clean_txt2 = res2_text.replace("```json", "").replace("```", "").strip()
                            st.session_state.selected_session_detail = json.loads(clean_txt2)
                            st.session_state.selected_session_detail.update({'type': chosen_session['type'], 'session': chosen_session['session']})
                            st.success("고품질 과정안 완성! 3단계 탭으로 이동하세요.")
                        except Exception as e:
                            st.error(str(e))
            else:
                st.warning("1단계 분석을 완료해 주세요.")
                
        with tab3:
            if st.session_state.selected_session_detail:
                data = st.session_state.selected_session_detail
                st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
                st.write(f"### ✅ {data.get('session', '')}차시 공개수업 교수·학습 과정안 (미리보기)")
                st.markdown(f"**단원:** {data.get('unit', '')}")
                st.markdown(f"**학습목표:** {data.get('objectives', '')}")
                
                # HTML 양식 생성 함수 (인쇄 버튼 포함)
                def create_html(plan_data):
                    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{selected_subject} 교수학습 과정안</title>
<style>
    body {{ font-family: 'Malgun Gothic', dotum, sans-serif; line-height: 1.6; padding: 40px; max-width: 1000px; margin: auto; color: #333; }}
    h1 {{ text-align: center; font-size: 28px; border-bottom: 3px solid #000; padding-bottom: 15px; margin-bottom: 30px; letter-spacing: 2px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 15px; table-layout: fixed; }}
    th, td {{ border: 1px solid #000; padding: 15px; vertical-align: top; word-break: keep-all; }}
    th {{ background-color: #f2f2f2; font-weight: bold; text-align: center; }}
    .step {{ width: 12%; text-align: center; font-weight: bold; background-color: #f2f2f2; }}
    .content-cell {{ width: 68%; }}
    .note-cell {{ width: 20%; font-size: 13.5px; color: #444; }}
    .print-btn {{ display: block; width: 180px; margin: 0 auto 30px auto; padding: 12px; background-color: #2b8a3e; color: white; text-align: center; cursor: pointer; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: 0.2s; }}
    .print-btn:hover {{ background-color: #237032; transform: translateY(-2px); }}
    @media print {{ 
        .print-btn {{ display: none; }} 
        body {{ padding: 0; }} 
        th, td {{ padding: 10px; font-size: 13px; }}
    }}
</style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">🖨️ 과정안 바로 인쇄하기</button>
    <h1>{selected_subject} 교수·학습 과정안 ({plan_data.get('session', '')}차시)</h1>
    
    <table>
        <tr>
            <th>단원명</th>
            <td colspan="2">{plan_data.get('unit', '')}</td>
        </tr>
        <tr>
            <th>성취기준 및<br>학습 목표</th>
            <td colspan="2">{plan_data.get('objectives', '').replace(chr(10), '<br>')}</td>
        </tr>
        <tr>
            <th class="step">학습 단계</th>
            <th class="content-cell">교수·학습 활동 내용</th>
            <th class="note-cell">자료 및 유의점</th>
        </tr>
        <tr>
            <td class="step">도 입</td>
            <td class="content-cell">{plan_data.get('intro', '').replace(chr(10), '<br>')}</td>
            <td class="note-cell" rowspan="3">{plan_data.get('notes', '').replace(chr(10), '<br>')}</td>
        </tr>
        <tr>
            <td class="step">전 개</td>
            <td class="content-cell">{plan_data.get('development', '').replace(chr(10), '<br>')}</td>
        </tr>
        <tr>
            <td class="step">정 리</td>
            <td class="content-cell">{plan_data.get('conclusion', '').replace(chr(10), '<br>')}</td>
        </tr>
        <tr>
            <th>평가 계획</th>
            <td colspan="2">{plan_data.get('evaluation', '').replace(chr(10), '<br>')}</td>
        </tr>
    </table>
</body>
</html>"""
                    return html_content.encode('utf-8')

                st.download_button(
                    label="🖨️ 공개수업용 HTML 다운로드 (인쇄 버튼 포함)", 
                    data=create_html(data), 
                    file_name=f"공개수업과정안_{data.get('session', '1')}차시.html",
                    mime="text/html",
                    type="primary"
                )
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
                        res3_text = call_gemini_robust(st.session_state.api_key, prompt3)
                        st.session_state.extra_materials = res3_text
                    except Exception as e:
                        st.error(str(e))
                        
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
