import streamlit as st
import pdfplumber
import json
import io
import os
import time
import base64
import numpy as np
import pandas as pd
from datetime import datetime, date
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from google import genai

# ---------------------------------------------------------
# 🌟 [통합 데이터베이스] 로컬 파일 영구 보관 로직
# ---------------------------------------------------------
CLASS_DATA_FILE = "class_data.json"
TRAINING_FILE = "training_data.json"
REGISTRY_FILE = "registry.csv"

def load_class_data():
    if os.path.exists(CLASS_DATA_FILE):
        with open(CLASS_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 예전 버전에 attendance 항목이 없으면 새로 만들어줍니다.
            if "attendance" not in data:
                data["attendance"] = {}
            return data
    else:
        default_data = {
            "tasks": [{"완료": False, "할 일": "현장체험학습 동의서 수합", "기한": str(date.today()), "중요도": "높음", "분류": "학급 운영"}],
            "schedule": [{"날짜": str(date.today()), "시간": "15:30", "일정명": "학부모 상담", "분류": "상담"}],
            "students": [{"번호": i, "이름": f"학생{i}", "제출확인": False} for i in range(1, 13)],
            "counseling": [],
            "attendance": {} # 🌟 날짜별 출결 데이터 저장 공간 추가!
        }
        save_class_data(default_data)
        return default_data

def save_class_data(data):
    with open(CLASS_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_training_data():
    if os.path.exists(TRAINING_FILE):
        with open(TRAINING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"2026학년도 새학년 집중준비기간 연수": {"date": "2026. 02. 11. 14:00", "loc": "본관 대강당"}}

def save_training_data(data):
    with open(TRAINING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_registry():
    if os.path.exists(REGISTRY_FILE):
        return pd.read_csv(REGISTRY_FILE)
    return pd.DataFrame(columns=["연번", "연수명", "일시", "장소", "소속", "직위", "이름", "서명 상태", "서명 이미지", "등록 일시"])

def save_registry(df):
    df.to_csv(REGISTRY_FILE, index=False, encoding="utf-8-sig")

# ---------------------------------------------------------
# 1. 화면 기본 설정 & 💎 블링블링 디자인 CSS
# ---------------------------------------------------------
st.set_page_config(page_title="교무실 - AI 수퍼 앱", layout="wide", initial_sidebar_state="collapsed")

css_content = """
<style>
    .stApp { background: linear-gradient(135deg, #f0f4ff 0%, #fef5ff 50%, #f6f0fd 100%); }
    .main-title { text-align: center; margin: 0; padding-top: 15px; font-weight: 900; font-size: 2.8rem; background: linear-gradient(135deg, #6550bb 0%, #d946ef 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1.5px; }
    .dash-card { background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); padding: 25px; border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.8); box-shadow: 0 8px 32px rgba(101, 80, 187, 0.08); margin-bottom: 15px; transition: transform 0.3s ease, box-shadow 0.3s ease; }
    .dash-card:hover { transform: translateY(-5px); box-shadow: 0 12px 40px rgba(101, 80, 187, 0.15); }
    .dash-number { font-size: 2.6rem; font-weight: 900; background: linear-gradient(135deg, #6550bb, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0; line-height: 1.1; }
    .dash-label { font-size: 0.95rem; color: #64748b; font-weight: 700; margin-bottom: 5px; }
    .menu-title { font-size: 0.9rem; font-weight: 800; color: #8b5cf6; margin-top: 30px; margin-bottom: 10px; padding-left: 5px; letter-spacing: -0.5px; }
    div.stButton > button { border-radius: 12px !important; font-weight: 700 !important; transition: all 0.3s ease !important; padding: 10px 15px !important; border: none !important; }
    div.stButton > button[kind="secondary"] { background: transparent !important; color: #475569 !important; justify-content: flex-start !important; }
    div.stButton > button[kind="secondary"]:hover { background: rgba(139, 92, 246, 0.1) !important; color: #6550bb !important; transform: translateX(5px); }
    div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #6550bb 0%, #b829ea 100%) !important; color: white !important; justify-content: flex-start !important; box-shadow: 0 4px 15px rgba(101, 80, 187, 0.4) !important; }
    div.stButton > button[kind="primary"]:hover { box-shadow: 0 6px 20px rgba(101, 80, 187, 0.6) !important; transform: translateY(-2px); }
    div[data-baseweb="tab-list"] button p { font-size: 1.1rem !important; font-weight: 700 !important; }
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div { border-radius: 12px !important; border: 1px solid #e2e8f0 !important; background-color: rgba(255, 255, 255, 0.8) !important; }
</style>
"""
st.markdown(css_content, unsafe_allow_html=True)

# 데이터 세션 초기화
if "class_data" not in st.session_state: st.session_state.class_data = load_class_data()
if "training_data" not in st.session_state: st.session_state.training_data = load_training_data()
if "registry_df" not in st.session_state: st.session_state.registry_df = load_registry()
if "current_page" not in st.session_state: st.session_state.current_page = "오늘의 교무실"
if "api_key" not in st.session_state: st.session_state.api_key = ""
if "canvas_key" not in st.session_state: st.session_state.canvas_key = 0

# ==========================================
# 🌟 상단 헤더 컨테이너
# ==========================================
c1, c2, c3 = st.columns([2, 6, 2])
with c2:
    st.markdown("<h1 class='main-title'>✨ AI 에듀테크 수퍼 앱</h1>", unsafe_allow_html=True)
with c3:
    st.text_input("API Key", type="password", placeholder="🔑 Gemini API 키 입력", label_visibility="collapsed", key="api_key")
st.markdown("<hr style='border-color: rgba(0,0,0,0.05); margin-top: 20px; margin-bottom: 30px;'>", unsafe_allow_html=True)

def call_gemini_robust(api_key, prompt, max_retries=3):
    client = genai.Client(api_key=api_key)
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
            return response.text
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
            raise Exception(f"AI 통신 오류: {e}")

# ---------------------------------------------------------
# 화면 분할 (좌측 대시보드 메뉴 : 메인 컨텐츠)
# ---------------------------------------------------------
col_menu, col_main = st.columns([2, 8], gap="large")

with col_menu:
    def nav_button(icon, label, page_name):
        btn_type = "primary" if st.session_state.current_page == page_name else "secondary"
        if st.button(f"{icon}  {label}", key=page_name, use_container_width=True, type=btn_type):
            st.session_state.current_page = page_name
            st.rerun()

    st.markdown("<div class='menu-title'>나의 교무실</div>", unsafe_allow_html=True)
    nav_button("🏠", "오늘의 교무실", "오늘의 교무실")
    nav_button("✅", "할 일 목록", "할 일 목록")
    nav_button("📅", "학급 일정", "학급 일정")
    
    st.markdown("<div class='menu-title'>학급 운영</div>", unsafe_allow_html=True)
    nav_button("👥", "출결·제출물 관리", "출결·제출물 관리")
    nav_button("💬", "상담 메모", "상담 메모")
    
    st.markdown("<div class='menu-title'>수업·업무 지원 (AI)</div>", unsafe_allow_html=True)
    nav_button("📝", "과정안·학습지", "과정안 생성")
    nav_button("💡", "학생 세특 초안", "세특 초안")
    nav_button("🛡️", "사안·민원 쉴드", "사안 보고")
    nav_button("🎉", "행사 기획 마스터", "행사 기획")
    nav_button("💌", "알림장·문자", "알림장")
    nav_button("📋", "온라인 연수 등록부", "등록부")

with col_main:
    # --------------------------------------------------------------------------------
    # 🌟 [대시보드] 오늘의 교무실
    # --------------------------------------------------------------------------------
    if st.session_state.current_page == "오늘의 교무실":
        st.markdown("<h3 style='margin-bottom: 5px; color:#1e293b; font-weight:800;'>선생님, 오늘도 반갑습니다! 👋</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b; margin-bottom: 25px; font-weight:500;'>수업부터 학급 운영까지, 오늘 필요한 일을 한곳에서 확인하세요.</p>", unsafe_allow_html=True)
        
        tasks_df = pd.DataFrame(st.session_state.class_data["tasks"])
        pending_tasks = len(tasks_df[tasks_df["완료"] == False]) if not tasks_df.empty else 0
        
        students_df = pd.DataFrame(st.session_state.class_data["students"])
        missing_subs = len(students_df[students_df["제출확인"] == False]) if not students_df.empty else 0
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"<div class='dash-card'><div class='dash-label'>오늘의 할 일</div><div class='dash-number'>{pending_tasks}<span style='font-size:1.2rem; color:#94a3b8;'>건</span></div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='dash-card'><div class='dash-label'>제출물 미확인</div><div class='dash-number' style='background: linear-gradient(135deg, #ef4444, #f97316); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>{missing_subs}<span style='font-size:1.2rem; color:#94a3b8;'>명</span></div></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='dash-card'><div class='dash-label'>총 등록된 서명</div><div class='dash-number'>{len(st.session_state.registry_df)}<span style='font-size:1.2rem; color:#94a3b8;'>건</span></div></div>", unsafe_allow_html=True)
        with c4:
            st.markdown(f"<div class='dash-card'><div class='dash-label'>AI 연동 상태</div><div class='dash-number' style='background: linear-gradient(135deg, #10b981, #14b8a6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>READY 🟢</div></div>", unsafe_allow_html=True)

        cl, cr = st.columns([6, 4])
        with cl:
            st.markdown("#### ⚡ 빠른 실행 가이드")
            st.info("**1️⃣ 학급 운영:** 좌측 [출결·제출물 관리]에서 엑셀처럼 화면을 클릭해 실시간으로 학생 상태를 변경하고 자동 저장하세요.\n\n**2️⃣ 수업 준비:** [과정안·학습지]에서 교과서를 업로드하면 AI가 슬라이드와 평가지까지 7단계로 뚝딱 만들어냅니다.\n\n**3️⃣ 연수 서명:** 태블릿 하나만 켜두고 [온라인 연수 등록부] 메뉴에서 서명을 받아 바로 엑셀로 추출하세요.")
        with cr:
            st.markdown("#### 💡 이 달의 에듀테크 꿀팁")
            st.success("**[Canva 매직 스튜디오 활용]**\nAI가 추출한 '수업용 슬라이드 텍스트'를 복사해서 캔바(Canva) 매직 스튜디오에 붙여넣으면 10초 만에 완벽한 디자인의 PPT가 완성됩니다! 🎉")

    # --------------------------------------------------------------------------------
    # 🌟 할 일 목록
    # --------------------------------------------------------------------------------
    elif st.session_state.current_page == "할 일 목록":
        st.markdown("<h3 style='margin-bottom: 5px; color:#1e293b;'>✅ 할 일 목록</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b; margin-bottom: 20px;'>기억해야 할 일은 여기에 적어두고, 선생님의 집중은 학생에게!</p>", unsafe_allow_html=True)
        
        st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
        df_tasks = pd.DataFrame(st.session_state.class_data["tasks"])
        edited_tasks = st.data_editor(
            df_tasks,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "완료": st.column_config.CheckboxColumn("완료 여부"),
                "중요도": st.column_config.SelectboxColumn("중요도", options=["높음", "보통", "낮음"]),
                "분류": st.column_config.SelectboxColumn("분류", options=["학급 운영", "수업 준비", "평가·기록", "행정 업무"])
            },
            hide_index=True
        )
        if st.button("💾 변경사항 영구 저장", type="primary", key="save_task"):
            st.session_state.class_data["tasks"] = edited_tasks.to_dict('records')
            save_class_data(st.session_state.class_data)
            st.success("할 일 목록이 안전하게 저장되었습니다! ✨")
        st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------------
    # 🌟 학급 일정
    # --------------------------------------------------------------------------------
    elif st.session_state.current_page == "학급 일정":
        st.markdown("<h3 style='margin-bottom: 5px; color:#1e293b;'>📅 학급 일정</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b; margin-bottom: 20px;'>수업, 상담, 학급 행사를 달력처럼 기록하세요.</p>", unsafe_allow_html=True)
        
        st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
        df_schedule = pd.DataFrame(st.session_state.class_data["schedule"])
        edited_sched = st.data_editor(
            df_schedule,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "분류": st.column_config.SelectboxColumn("분류", options=["학급", "수업", "상담", "행정"])
            },
            hide_index=True
        )
        if st.button("💾 변경사항 영구 저장", type="primary", key="save_sched"):
            st.session_state.class_data["schedule"] = edited_sched.to_dict('records')
            save_class_data(st.session_state.class_data)
            st.success("학급 일정이 안전하게 저장되었습니다! ✨")
        st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------------
    # 🌟 출결·제출물 관리 (날짜별 출결 분리 & 제출물 탭 구분 적용!)
    # --------------------------------------------------------------------------------
    elif st.session_state.current_page == "출결·제출물 관리":
        st.markdown("<h3 style='margin-bottom: 5px; color:#1e293b;'>👥 출결 및 제출물 분리 관리</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b; margin-bottom: 20px;'>날짜별 일일 출결 기록과 제출물 수합 여부를 따로따로 깔끔하게 관리하세요.</p>", unsafe_allow_html=True)
        
        tab_att, tab_sub = st.tabs(["📅 날짜별 출결 기록", "✅ 제출물 (동의서) 관리"])
        
        # [1] 날짜별 출결 관리 탭
        with tab_att:
            st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
            # 날짜 선택기
            att_date = st.date_input("📌 출결을 기록/조회할 날짜를 선택하세요", date.today())
            date_str = str(att_date)
            
            # 해당 날짜의 출결 데이터가 JSON에 없으면 전원 '출석'으로 초기 세팅
            if date_str not in st.session_state.class_data["attendance"]:
                st.session_state.class_data["attendance"][date_str] = {str(s["번호"]): "출석" for s in st.session_state.class_data["students"]}
            
            # 표에 보여줄 데이터 만들기
            att_records = []
            for s in st.session_state.class_data["students"]:
                s_num = str(s["번호"])
                status = st.session_state.class_data["attendance"][date_str].get(s_num, "출석")
                att_records.append({"번호": s["번호"], "이름": s["이름"], "출결상태": status})
            
            df_att = pd.DataFrame(att_records)
            st.info(f"**{date_str}**의 명렬표입니다. 엑셀처럼 클릭해서 상태를 변경하고 저장하세요.")
            
            edited_att = st.data_editor(
                df_att,
                use_container_width=True,
                column_config={
                    "번호": st.column_config.NumberColumn("번호", disabled=True),
                    "이름": st.column_config.TextColumn("이름", disabled=True),
                    "출결상태": st.column_config.SelectboxColumn("출결 상태", options=["출석", "지각", "조퇴", "결석", "인정결석"])
                },
                hide_index=True,
                key=f"att_editor_{date_str}"
            )
            
            if st.button("💾 해당 날짜 출결 영구 저장", type="primary", key="save_att"):
                for row in edited_att.to_dict('records'):
                    st.session_state.class_data["attendance"][date_str][str(row["번호"])] = row["출결상태"]
                save_class_data(st.session_state.class_data)
                st.success(f"{date_str} 출결 데이터가 파일에 영구 저장되었습니다! 나중에 이 날짜를 선택하면 그대로 불러와집니다. ✨")
            st.markdown("</div>", unsafe_allow_html=True)

        # [2] 제출물 관리 탭
        with tab_sub:
            st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
            st.info("현장체험학습 동의서, 가정통신문 회신서 등 수합 여부를 체크하세요.")
            
            # 제출물 관련 데이터만 추출
            sub_records = [{"번호": s["번호"], "이름": s["이름"], "제출확인": s.get("제출확인", False)} for s in st.session_state.class_data["students"]]
            df_sub = pd.DataFrame(sub_records)
            
            edited_sub = st.data_editor(
                df_sub,
                use_container_width=True,
                column_config={
                    "번호": st.column_config.NumberColumn("번호", disabled=True),
                    "이름": st.column_config.TextColumn("이름", disabled=True),
                    "제출확인": st.column_config.CheckboxColumn("동의서 등 제출 완료")
                },
                hide_index=True,
                key="sub_editor"
            )
            if st.button("💾 제출물 현황 영구 저장", type="primary", key="save_sub"):
                # 변경된 체크 결과를 원본 students 에 반영
                for i, row in enumerate(edited_sub.to_dict('records')):
                    st.session_state.class_data["students"][i]["제출확인"] = row["제출확인"]
                save_class_data(st.session_state.class_data)
                st.success("제출물 체크 현황이 안전하게 저장되었습니다! ✨")
            st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------------
    # 🌟 상담 메모
    # --------------------------------------------------------------------------------
    elif st.session_state.current_page == "상담 메모":
        st.markdown("<h3 style='margin-bottom: 5px; color:#1e293b;'>💬 상담 메모</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b; margin-bottom: 20px;'>학생 및 학부모 상담 기록을 남기세요. (민감한 정보는 요약해서 기록)</p>", unsafe_allow_html=True)
        
        with st.expander("➕ 새로운 상담 기록 추가하기", expanded=False):
            with st.form("counsel_form"):
                col1, col2, col3 = st.columns(3)
                with col1: c_date = st.date_input("상담일")
                with col2: c_target = st.selectbox("상담 대상", ["학생", "학부모"])
                with col3: c_student = st.text_input("학생명 (또는 학번)")
                c_title = st.text_input("상담 주제")
                c_body = st.text_area("상담 내용 및 후속 조치")
                if st.form_submit_button("저장하기", type="primary"):
                    new_note = {"날짜": str(c_date), "대상": c_target, "학생명": c_student, "주제": c_title, "내용": c_body}
                    st.session_state.class_data["counseling"].append(new_note)
                    save_class_data(st.session_state.class_data)
                    st.success("상담 기록이 추가되었습니다! ✨")
                    st.rerun()
                    
        st.write("---")
        notes = st.session_state.class_data.get("counseling", [])
        if not notes:
            st.info("아직 등록된 상담 메모가 없습니다.")
        else:
            for note in reversed(notes):
                st.markdown(f"""
                <div class='dash-card'>
                    <div style='display:flex; justify-content:space-between; margin-bottom:10px;'>
                        <span style='background:linear-gradient(135deg, #6550bb, #8b5cf6); color:white; padding:4px 10px; border-radius:8px; font-size:12px; font-weight:bold;'>{note['대상']} 상담</span>
                        <span style='color:#64748b; font-size:13px; font-weight:bold;'>{note['날짜']}</span>
                    </div>
                    <h4 style='margin:0 0 5px 0; color:#1e293b; font-size:1.2rem;'>{note['주제']}</h4>
                    <div style='font-size:13px; font-weight:bold; color:#ec4899; margin-bottom:10px;'>👤 학생: {note['학생명']}</div>
                    <p style='color:#475569; font-size:14px; white-space:pre-wrap; margin:0;'>{note['내용']}</p>
                </div>
                """, unsafe_allow_html=True)

    # --------------------------------------------------------------------------------
    # [기존 AI 기능] 1. 과정안 생성기 (7단계 슬라이드 포함)
    # --------------------------------------------------------------------------------
    elif st.session_state.current_page == "과정안 생성":
        st.markdown("<h3 style='margin-bottom: 20px; color:#1e293b;'>📝 개념기반 공개수업 마스터플랜 생성기</h3>", unsafe_allow_html=True)
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["⚙️ 1. 기본 설정", "📊 2. 단원 분석", "🎯 3. 지도안 생성", "🖥️ 4. 슬라이드", "📝 5. 활동지", "❓ 6. 평가 출제", "🖨️ 7. 인쇄/추출"])
        
        with tab1:
            st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
            c1_set, c2_set = st.columns(2)
            with c1_set:
                subj_list = ["공통국어", "윤리와 사상", "생활과 윤리", "➕ 직접 입력 (새 과목 추가)"]
                sel_subj = st.selectbox("📚 담당 과목", subj_list)
                st.session_state.final_subject = st.text_input("✨ 새 과목명 입력") if sel_subj == "➕ 직접 입력 (새 과목 추가)" else sel_subj
                st.text_input("🏫 소속 학교명", placeholder="예) 광영고등학교", key="school_name")
                st.text_input("📅 수업 일시", placeholder="예) 2026. 10. 14. (수) 14:00", key="class_date")
            with c2_set:
                st.text_input("👨‍🏫 지도 교사", placeholder="예) 유일한", key="teacher_name")
                st.text_input("👥 수업 대상", placeholder="예) 1학년 6반 학생", key="target_students")
                st.text_input("🏫 수업 장소", placeholder="예) 1학년 6반 교실", key="class_location")
            st.write("---")
            uploaded_file = st.file_uploader("단원 분석을 위한 PDF 파일을 업로드해 주세요.", type=["pdf"])
            st.markdown("</div>", unsafe_allow_html=True)
                
        with tab2:
            st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
            if uploaded_file and st.session_state.get("api_key"):
                if st.button("🚀 AI 단원 분석 시작", type="primary"):
                    with st.spinner("AI가 교과서를 분석 중입니다..."):
                        text_data = ""
                        with pdfplumber.open(uploaded_file) as pdf:
                            for page in pdf.pages:
                                ext = page.extract_text()
                                if ext: text_data += ext + "\n"
                        MAX_CHARS = 50000
                        if len(text_data) > MAX_CHARS:
                            st.warning(f"⚠️ PDF 용량이 커서 무료 API 한도 보호를 위해 앞부분만 분석합니다.")
                            text_data = text_data[:MAX_CHARS]
                        st.session_state.extracted_text = text_data
                        prompt1 = f"개념기반 교육과정 전문가로서 {st.session_state.final_subject} 텍스트를 분석해 최적 총 차시를 설계하세요. JSON 배열로 답변 (키: session, type, title, desc). [내용] {text_data}"
                        try:
                            res1 = call_gemini_robust(st.session_state.api_key, prompt1)
                            st.session_state.proposed_sessions = json.loads(res1.replace("```json", "").replace("```", "").strip())
                            st.success("완료! 3단계 탭으로 이동하세요. ✨")
                        except Exception as e: st.error(str(e))
            elif not st.session_state.get("api_key"): st.error("⚠️ 상단에 API 키를 입력해 주세요.")
            else: st.info("1단계에서 PDF를 업로드해 주세요.")
            st.markdown("</div>", unsafe_allow_html=True)
                
        with tab3:
            st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
            if st.session_state.proposed_sessions:
                options = {f"{s['session']}차시 - {s['title']}": s for s in st.session_state.proposed_sessions}
                sel_opt = st.radio("과정안을 생성할 차시를 선택하세요:", list(options.keys()))
                if st.button("📝 지도안 생성", type="primary"):
                    chosen = options[sel_opt]
                    with st.spinner("지도안을 설계 중입니다..."):
                        prompt2 = f"""{st.session_state.final_subject} 수석 교사입니다. 주제: {chosen['title']}. 아래 JSON 구조로 답변하세요:
{{"overview": "수업 개요", "macro": "거시 개념", "micro": "미시 개념", "objective": "본시 학습 목표", "big_idea": "일반화",
"intro_act": "도입 활동", "intro_time": "10분", "intro_note": "유의점",
"dev_act": "전개 활동", "dev_time": "30분", "dev_note": "모둠 활동",
"conc_act": "정리 활동", "conc_time": "10분", "conc_note": "형성평가"}}
[내용] {st.session_state.extracted_text}"""
                        try:
                            res2 = call_gemini_robust(st.session_state.api_key, prompt2)
                            st.session_state.selected_session_detail = json.loads(res2.replace("```json", "").replace("```", "").strip())
                            st.session_state.selected_session_detail.update({'session': chosen['session'], 'title': chosen['title']})
                            st.success("지도안 완성! 4단계로 이동하세요. ✨")
                        except Exception as e: st.error(str(e))
            st.markdown("</div>", unsafe_allow_html=True)

        with tab4:
            st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
            if st.session_state.selected_session_detail:
                if st.button("🪄 슬라이드 텍스트 자동 생성", type="primary"):
                    with st.spinner("교과서 내용과 지도안을 바탕으로 슬라이드를 구성 중입니다..."):
                        d = st.session_state.selected_session_detail
                        prompt_slide = f"""{st.session_state.final_subject} 교사입니다. 주제: {d.get('title','')}, 목표: {d.get('objective','')}. 수업용 슬라이드 3장 분량을 JSON 구조로 답변하세요:
{{"slide1_title": "1장 제목", "slide1_bullets": ["포인트1", "포인트2"], "slide2_title": "2장 제목", "slide2_bullets": ["설명1", "설명2"], "slide3_title": "3장 제목", "slide3_bullets": ["정리내용", "안내"]}}"""
                        try:
                            res_slide = call_gemini_robust(st.session_state.api_key, prompt_slide)
                            st.session_state.slide_detail = json.loads(res_slide.replace("```json", "").replace("```", "").strip())
                            st.success("완료! 5단계로 이동하세요. ✨")
                        except Exception as e: st.error(str(e))
                if st.session_state.slide_detail:
                    s = st.session_state.slide_detail
                    st.markdown("---")
                    col_s1, col_s2, col_s3 = st.columns(3)
                    with col_s1:
                        st.markdown(f"**[Slide 1] {s.get('slide1_title','')}**")
                        for b in s.get('slide1_bullets', []): st.write(f"• {b}")
                    with col_s2:
                        st.markdown(f"**[Slide 2] {s.get('slide2_title','')}**")
                        for b in s.get('slide2_bullets', []): st.write(f"• {b}")
                    with col_s3:
                        st.markdown(f"**[Slide 3] {s.get('slide3_title','')}**")
                        for b in s.get('slide3_bullets', []): st.write(f"• {b}")
            st.markdown("</div>", unsafe_allow_html=True)

        with tab5:
            st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
            if st.session_state.selected_session_detail:
                if st.button("📝 활동지 설계", type="primary"):
                    with st.spinner("활동지를 디자인 중입니다..."):
                        prompt3 = f"""{st.session_state.final_subject} 교사입니다. 주제: '{st.session_state.selected_session_detail['title']}'. 활동지를 JSON 구조로 답변하세요:
{{"title": "제목", "act1_title": "활동 1", "act1_desc": "설명", "act2_title": "활동 2", "act2_desc": "설명", "act3_title": "활동 3", "act3_desc": "설명", "wrap_up": "마무리"}}"""
                        try:
                            res3 = call_gemini_robust(st.session_state.api_key, prompt3)
                            st.session_state.worksheet_detail = json.loads(res3.replace("```json", "").replace("```", "").strip())
                            st.success("완료! 6단계로 이동하세요. ✨")
                        except Exception as e: st.error(str(e))
            st.markdown("</div>", unsafe_allow_html=True)

        with tab6:
            st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
            if st.session_state.selected_session_detail:
                if st.button("❓ 형성평가 출제", type="primary"):
                    with st.spinner("문제를 출제하고 있습니다..."):
                        prompt4 = f"""평가 전문가입니다. 주제: '{st.session_state.selected_session_detail['title']}'. 형성평가를 JSON 구조로 출제하세요:
{{"title": "제목", "ox_quiz": [{{"q": "질문", "a": "O/X", "exp": "해설"}}], "initial_quiz": [{{"q": "초성질문", "a": "정답단어", "exp": "해설"}}], "vocab_quiz": [{{"q": "단답질문", "a": "단어", "exp": "해설"}}], "mcq": [{{"q": "질문", "options": ["보1","보2","보3","보4"], "a": "정답번호(1~4)", "exp": "해설"}}]}}"""
                        try:
                            res4 = call_gemini_robust(st.session_state.api_key, prompt4)
                            st.session_state.quiz_detail = json.loads(res4.replace("```json", "").replace("```", "").strip())
                            st.success("완료! 7단계로 이동하세요. ✨")
                        except Exception as e: st.error(str(e))
            st.markdown("</div>", unsafe_allow_html=True)

        with tab7:
            st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
            st.info("이전 단계에서 생성한 모든 자료를 HTML과 CSV로 다운로드할 수 있습니다.")
            c_a, c_b, c_c, c_d = st.columns(4)
            if st.session_state.selected_session_detail:
                d = st.session_state.selected_session_detail
                html_plan = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><title>지도안</title></head><body><h1>{d.get('title','')} 지도안</h1><p>{d.get('overview','')}</p></body></html>"""
                with c_a: st.download_button("📥 1. 지도안(HTML)", data=html_plan.encode('utf-8'), file_name="지도안.html", mime="text/html", type="primary", use_container_width=True)
            if st.session_state.worksheet_detail:
                w = st.session_state.worksheet_detail
                html_work = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><title>활동지</title></head><body><h1>{w.get('title','')}</h1><p>{w.get('act1_desc','')}</p></body></html>"""
                with c_b: st.download_button("📥 2. 활동지(HTML)", data=html_work.encode('utf-8'), file_name="활동지.html", mime="text/html", type="primary", use_container_width=True)
            if st.session_state.quiz_detail:
                q = st.session_state.quiz_detail
                html_quiz = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><title>평가</title></head><body><h1>{q.get('title','')}</h1></body></html>"""
                with c_c: st.download_button("📥 3. 평가지(HTML)", data=html_quiz.encode('utf-8'), file_name="형성평가.html", mime="text/html", type="primary", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------------
    # [기존 AI 기능] 사안보고, 행사기획, 알림장, 세특초안
    # --------------------------------------------------------------------------------
    elif st.session_state.current_page == "행사 기획":
        st.markdown("<h3 style='margin-bottom: 20px; color:#1e293b;'>🎉 대형 행사 시나리오 & 기안문 자동 생성기</h3>", unsafe_allow_html=True)
        st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1: event_name = st.text_input("행사명", placeholder="예) 교육과정 박람회")
        with col2: event_date = st.text_input("행사 일시 및 장소")
        event_purpose = st.text_area("행사 목적 및 주요 식순(키워드)")
        if st.button("🎉 기안문 & 대본 생성하기", type="primary"):
            if not st.session_state.get("api_key"): st.error("⚠️ API 키를 입력해 주세요.")
            elif event_name and event_purpose:
                with st.spinner("작성 중입니다..."):
                    prompt = f"부장교사입니다. 행사명: {event_name}, 일시/장소: {event_date}, 내용: {event_purpose}. 1. 내부 결재 기안문 초안, 2. 진행 시나리오 대본을 작성하세요."
                    try: st.markdown(f"<div style='margin-top:20px; padding:20px; background:#f8fafc; border-radius:10px;'>{call_gemini_robust(st.session_state.api_key, prompt)}</div>", unsafe_allow_html=True)
                    except Exception as e: st.error(str(e))
        st.markdown("</div>", unsafe_allow_html=True)

    elif st.session_state.current_page == "사안 보고":
        st.markdown("<h3 style='margin-bottom: 20px; color:#1e293b;'>🛡️ 교권 보호 사안 보고서 & 상담 매뉴얼 생성기</h3>", unsafe_allow_html=True)
        st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
        incident_memo = st.text_area("발생한 사안이나 민원 내용을 적어주세요.", height=150)
        if st.button("🛡️ 대응 스크립트 생성", type="primary"):
            if not st.session_state.get("api_key"): st.error("⚠️ API 키를 입력해 주세요.")
            elif incident_memo:
                with st.spinner("작성 중입니다..."):
                    prompt = f"전문가입니다. 다음 메모로 작성하세요: {incident_memo}\n1. 객관적 사안 보고서 초안\n2. 단호하고 정중한 교사용 전화 상담 스크립트"
                    try: st.markdown(f"<div style='margin-top:20px; padding:20px; background:#f8fafc; border-radius:10px;'>{call_gemini_robust(st.session_state.api_key, prompt)}</div>", unsafe_allow_html=True)
                    except Exception as e: st.error(str(e))
        st.markdown("</div>", unsafe_allow_html=True)

    elif st.session_state.current_page == "세특 초안":
        st.markdown("<h3 style='margin-bottom: 20px; color:#1e293b;'>💡 학생 세특(관찰) 초안 생성기</h3>", unsafe_allow_html=True)
        st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1: stu_name = st.text_input("학생 이름")
        with col2: stu_level = st.selectbox("성취 수준", ["상 (우수함, 주도적)", "중 (성실함, 무난함)", "하 (노력 요함)"])
        stu_activity = st.text_area("주요 관찰 내용 및 활동 키워드")
        if st.button("✨ 세특 초안 생성하기", type="primary"):
            if not st.session_state.get("api_key"): st.error("⚠️ API 키를 입력해 주세요.")
            elif stu_name and stu_activity:
                with st.spinner("작성 중입니다..."):
                    prompt = f"교사입니다. 학생 '{stu_name}'의 세특 작성. 수준: {stu_level} / 관찰: {stu_activity}. 명사형 종결어미 사용, 전문적이고 긍정적으로 작성하세요."
                    try: st.markdown(f"<div style='margin-top:20px; padding:20px; background:#f8fafc; border-radius:10px;'>{call_gemini_robust(st.session_state.api_key, prompt)}</div>", unsafe_allow_html=True)
                    except Exception as e: st.error(str(e))
        st.markdown("</div>", unsafe_allow_html=True)

    elif st.session_state.current_page == "알림장":
        st.markdown("<h3 style='margin-bottom: 20px; color:#1e293b;'>💌 학급 알림장/가정통신문 자동 생성기</h3>", unsafe_allow_html=True)
        st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
        msg_context = st.text_area("전달할 핵심 내용 입력")
        if st.button("💌 알림장 문구 생성", type="primary"):
            if not st.session_state.get("api_key"): st.error("⚠️ API 키를 입력해 주세요.")
            elif msg_context:
                with st.spinner("작성 중입니다..."):
                    prompt = f"다정하고 꼼꼼한 교사입니다. 다음 내용을 알림장 형태로 다듬어주세요: {msg_context}."
                    try: st.markdown(f"<div style='margin-top:20px; padding:20px; background:#f8fafc; border-radius:10px;'>{call_gemini_robust(st.session_state.api_key, prompt)}</div>", unsafe_allow_html=True)
                    except Exception as e: st.error(str(e))
        st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------------
    # 🌟 [메뉴 5] 등록부 (온라인 서명) - 완벽 유지
    # --------------------------------------------------------------------------------
    elif st.session_state.current_page == "등록부":
        st.markdown("<h3 style='margin-bottom: 20px; color:#1e293b;'>📋 온라인 연수 등록부 및 전자 서명</h3>", unsafe_allow_html=True)

        with st.expander("⚙️ 연수 관리자 설정 (비밀번호: 1234)"):
            if st.text_input("비밀번호", type="password", key="reg_pw") == "1234":
                c_new1, c_new2, c_new3 = st.columns([2, 1, 1])
                with c_new1: new_title = st.text_input("연수명", key="new_title_input")
                with c_new2: new_date = st.text_input("일시", key="new_date_input")
                with c_new3: new_loc = st.text_input("장소", key="new_loc_input")
                if st.button("➕ 연수 추가하기", type="primary"):
                    if new_title:
                        st.session_state.training_data[new_title] = {"date": new_date, "loc": new_loc}
                        save_training_data(st.session_state.training_data)
                        st.success(f"'{new_title}' 추가 완료!")
                        time.sleep(1)
                        st.rerun()
        
        st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
        if not st.session_state.training_data:
            st.warning("등록된 연수가 없습니다. 관리자 설정에서 추가해주세요.")
        else:
            selected_training = st.selectbox("📌 참여할 연수 선택", list(st.session_state.training_data.keys()))
            reg_date = st.session_state.training_data[selected_training]["date"]
            reg_loc = st.session_state.training_data[selected_training]["loc"]
            st.info(f"📅 **일시:** {reg_date} &nbsp;&nbsp;|&nbsp;&nbsp; 🏫 **장소:** {reg_loc}")
            st.write("---")
            
            c1, c2, c3 = st.columns(3)
            with c1: in_dept = st.text_input("소속", placeholder="광영고")
            with c2: in_pos = st.text_input("직위", placeholder="교사")
            with c3: in_name = st.text_input("이름", placeholder="홍길동")
            
            st.write("✍️ **서명** - 마우스나 스마트폰 터치로 서명해 주세요.")
            canvas_result = st_canvas(
                stroke_width=3, stroke_color="#000000", background_color="#ffffff", 
                height=100, width=400, drawing_mode="freedraw", 
                update_streamlit=True, return_image_data=True, key=f"sig_canvas_{st.session_state.canvas_key}"
            )

            if st.button("✅ 서명 완료 및 제출", type="primary", use_container_width=True):
                if not in_name: st.warning("이름을 입력하세요.")
                elif canvas_result.image_data is None: st.warning("⚠️ 서명을 그려주세요!")
                else:
                    img_array = canvas_result.image_data
                    if np.min(img_array[:, :, :3]) < 255:
                        img_pil = Image.fromarray(img_array.astype('uint8'), 'RGBA')
                        img_rgb = Image.new("RGB", img_pil.size, (255, 255, 255))
                        img_rgb.paste(img_pil, mask=img_pil.split()[3])
                        buffered = io.BytesIO()
                        img_rgb.save(buffered, format="PNG")
                        sig_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                        
                        new_row = pd.DataFrame([{
                            "연번": len(st.session_state.registry_df[st.session_state.registry_df["연수명"] == selected_training])+1, 
                            "연수명": selected_training, "일시": reg_date, "장소": reg_loc,
                            "소속": in_dept, "직위": in_pos, "이름": in_name, 
                            "서명 상태": "✅ 완료", "서명 이미지": sig_base64, 
                            "등록 일시": datetime.now().strftime("%m-%d %H:%M")
                        }])
                        st.session_state.registry_df = pd.concat([st.session_state.registry_df, new_row], ignore_index=True)
                        save_registry(st.session_state.registry_df)
                        st.success(f"{in_name} 선생님 등록 완료!")
                        st.session_state.canvas_key += 1
                        time.sleep(1)
                        st.rerun()
                    else: st.warning("⚠️ 캔버스에 서명을 다시 그려주세요!")
                        
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.session_state.training_data:
            display_df = st.session_state.registry_df[st.session_state.registry_df["연수명"] == selected_training]
            st.dataframe(display_df.drop(columns=["서명 이미지", "연수명", "일시", "장소"], errors="ignore"), hide_index=True, use_container_width=True)
            if not display_df.empty:
                st.download_button("📥 엑셀(CSV) 다운로드", data=display_df.to_csv(index=False, encoding='utf-8-sig'), file_name=f"{selected_training}_등록부.csv", mime="text/csv", use_container_width=True)
