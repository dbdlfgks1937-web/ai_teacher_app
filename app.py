import streamlit as st
import pdfplumber
import json
import io
import time
import base64
import numpy as np
import pandas as pd
from datetime import datetime
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from google import genai

# ---------------------------------------------------------
# 1. 화면 기본 설정 & 외부 CSS 파일 불러오기
# ---------------------------------------------------------
st.set_page_config(page_title="AI 에듀테크 수퍼 앱", layout="wide", initial_sidebar_state="collapsed")

custom_css = """
<style>
    div[data-baseweb="tab-list"] button p {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }
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

# 🌟 서명용 캔버스 초기화 키
if "canvas_key" not in st.session_state: st.session_state.canvas_key = 0

if "registry_df" not in st.session_state: 
    st.session_state.registry_df = pd.DataFrame(columns=["연번", "연수명", "일시", "장소", "소속", "직위", "이름", "서명 상태", "서명 이미지", "등록 일시"])

# 상단 헤더
st.title("🚀 AI 에듀테크 수퍼 앱 (feat. 개념기반 교육과정)")
st.write("---")

# ==========================================
# 🌟 [AI 호출 함수] 
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
    
    st.markdown("<div class='menu-title'>🛡️ 교권/상담 지원</div>", unsafe_allow_html=True)
    nav_button("🛡️ 사안/민원 쉴드", "사안 보고")
    
    st.markdown("<div class='menu-title'>🏫 행정/학급 운영</div>", unsafe_allow_html=True)
    nav_button("🎉 행사 기획 마스터", "행사 기획")
    nav_button("💌 학급 알림장/문자", "알림장")
    nav_button("📋 온라인 등록부", "등록부")

with col_main:
    # --------------------------------------------------------------------------------
    # [메뉴 1] 과정안 생성기
    # --------------------------------------------------------------------------------
    if st.session_state.current_page == "과정안 생성":
        st.subheader("📝 개념기반 공개수업 마스터플랜 생성기")
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["⚙️ 1. 기본 설정", "📊 2. 단원 분석", "🎯 3. 지도안 생성", "📝 4. 활동지 생성", "❓ 5. 평가 출제", "🖨️ 6. 인쇄/추출"])
        
        with tab1:
            st.markdown("#### ⚙️ 수업 기본 정보 세팅")
            c1, c2 = st.columns(2)
            with c1:
                subj_list = ["공통국어", "윤리와 사상", "생활과 윤리", "➕ 직접 입력 (새 과목 추가)"]
                sel_subj = st.selectbox("📚 담당 과목", subj_list)
                if sel_subj == "➕ 직접 입력 (새 과목 추가)": st.session_state.final_subject = st.text_input("✨ 새 과목명 입력")
                else: st.session_state.final_subject = sel_subj
                st.text_input("🏫 소속 학교명", placeholder="예) 광영고등학교", key="school_name")
                st.text_input("📅 수업 일시", placeholder="예) 2026. 10. 14. (수) 14:00", key="class_date")
            with c2:
                st.text_input("👨‍🏫 지도 교사", placeholder="예) 유일한", key="teacher_name")
                st.text_input("👥 수업 대상", placeholder="예) 1학년 6반 학생", key="target_students")
                st.text_input("🏫 수업 장소", placeholder="예) 1학년 6반 교실", key="class_location")
            st.write("---")
            st.markdown("#### 📄 교과서 PDF 업로드")
            uploaded_file = st.file_uploader("단원 분석을 위한 PDF 파일을 업로드해 주세요.", type=["pdf"])
                
        with tab2:
            st.markdown("#### 📊 단원 구조 분석")
            if uploaded_file and st.session_state.get("api_key"):
                if st.button("🚀 AI 단원 분석 시작", type="primary"):
                    with st.spinner("AI가 교과서를 분석하여 개념기반 흐름을 추출하고 있습니다..."):
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
                        except Exception as e: st.error(str(e))
            elif not st.session_state.get("api_key"): st.error("👈 우측 상단에 API 키를 먼저 입력해 주세요.")
            else: st.warning("1단계 탭에서 교과서 PDF를 업로드해 주세요.")
                
        with tab3:
            st.markdown("#### 🎯 개념기반 공개수업 지도안 생성")
            if st.session_state.proposed_sessions:
                options = {f"{s['session']}차시 - {s['title']}": s for s in st.session_state.proposed_sessions}
                sel_opt = st.radio("과정안을 생성할 차시를 선택하세요:", list(options.keys()))
                if st.button("📝 개념기반 공개수업 지도안 생성", type="primary"):
                    chosen = options[sel_opt]
                    with st.spinner("학생 주도형 탐구 수업을 설계 중입니다..."):
                        prompt2 = f"""당신은 {st.session_state.final_subject} 수석 교사입니다. 주제: {chosen['title']}. 
학생들이 '핵심 아이디어'에 도달할 수 있는 탐구 수업을 설계해 주세요. 아래 JSON 구조로 답변하세요:
{{
  "overview": "수업 개요", "macro": "거시 개념", "micro": "미시 개념", "objective": "본시 학습 목표", "big_idea": "핵심 아이디어 / 일반화",
  "intro_act": "도입 활동", "intro_time": "10분", "intro_note": "유의점",
  "dev_act": "전개 활동 (구체적 교사-학생 발문 상호작용 상세화)", "dev_time": "30분", "dev_note": "모둠 활동 등",
  "conc_act": "정리 활동", "conc_time": "10분", "conc_note": "형성평가 및 성찰"
}}
[내용] {st.session_state.extracted_text}"""
                        try:
                            res2 = call_gemini_robust(st.session_state.api_key, prompt2)
                            st.session_state.selected_session_detail = json.loads(res2.replace("```json", "").replace("```", "").strip())
                            st.session_state.selected_session_detail.update({'session': chosen['session'], 'title': chosen['title']})
                            st.success("개념기반 지도안 완성! 4단계 탭으로 이동하세요.")
                        except Exception as e: st.error(str(e))

        with tab4:
            st.markdown("#### 📝 A4 맞춤형 학생 활동지 생성")
            if st.session_state.selected_session_detail:
                if st.button("📝 개념기반 학생 활동지 설계", type="primary"):
                    with st.spinner("탐구 질문과 논리 구조가 포함된 학생 활동지를 디자인 중입니다..."):
                        prompt3 = f"""당신은 {st.session_state.final_subject} 수석 교사입니다. 앞서 설계한 '{st.session_state.selected_session_detail['title']}' 수업의 학생용 활동지를 아래 JSON 구조로 답변하세요:
{{
  "title": "활동지 제목",
  "act1_title": "[활동 1] 지식 탐구 및 분석", "act1_desc": "표로 정리할 내용 안내",
  "act2_title": "[활동 2] 생각을 여는 탐구 질문 만들기", "act2_desc": "질문 예시 안내",
  "act3_title": "[활동 3] 나만의 관점 세우기", "act3_desc": "3단 마법의 문장 틀 포함",
  "wrap_up": "[마무리] 상호작용 및 성찰 체크리스트"
}}"""
                        try:
                            res3 = call_gemini_robust(st.session_state.api_key, prompt3)
                            st.session_state.worksheet_detail = json.loads(res3.replace("```json", "").replace("```", "").strip())
                            st.success("활동지 완성! 5단계 탭으로 이동하세요.")
                        except Exception as e: st.error(str(e))

        with tab5:
            st.markdown("#### ❓ 다유형 형성평가지 출제")
            if st.session_state.selected_session_detail:
                if st.button("❓ 형성평가 출제 시작", type="primary"):
                    with st.spinner("O/X, 초성, 어휘, 4지선다 등 다양한 유형의 문제를 출제하고 있습니다..."):
                        prompt4 = f"""당신은 {st.session_state.final_subject} 평가 전문가입니다. '{st.session_state.selected_session_detail['title']}' 수업 내용에 대해 아래 JSON 구조로 출제하세요:
{{
  "title": "형성평가지 제목",
  "ox_quiz": [ {{"q": "질문 내용", "a": "O 또는 X", "exp": "해설"}} ],
  "initial_quiz": [ {{"q": "질문 내용 (초성 제시)", "a": "정답단어", "exp": "해설"}} ],
  "vocab_quiz": [ {{"q": "단답형 질문 내용", "a": "정답단어", "exp": "해설"}} ],
  "mcq": [ {{"q": "질문 내용", "options": ["보기1", "보기2", "보기3", "보기4"], "a": "정답번호(1~4)", "exp": "해설"}} ]
}}
목표: {st.session_state.selected_session_detail.get('objective','')}
"""
                        try:
                            res4 = call_gemini_robust(st.session_state.api_key, prompt4)
                            st.session_state.quiz_detail = json.loads(res4.replace("```json", "").replace("```", "").strip())
                            st.success("형성평가 출제 완료! 6단계(인쇄/추출) 탭으로 이동하세요.")
                        except Exception as e: st.error(str(e))

        with tab6:
            st.markdown("#### 🖨️ 생성 파일 인쇄 및 엑셀 추출")
            c_a, c_b, c_c, c_d = st.columns(4)
            sub = st.session_state.final_subject
            s_name = st.session_state.get('school_name', '')
            teacher_display = f"[{s_name}] {st.session_state.get('teacher_name', '')}".strip() if s_name else st.session_state.get('teacher_name', '')
            info_line = f"[{st.session_state.get('target_students', '')}] ___번 이름: _____________"
            
            if st.session_state.selected_session_detail:
                d = st.session_state.selected_session_detail
                html_plan = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><title>공개수업 지도안</title><style>@page {{ size: A4; margin: 20mm; }} body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.5; }} table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; }} th, td {{ border: 1px solid #000; padding: 8px; }} th {{ background-color: #f2f2f2; text-align: center; }} .print-btn {{ display: block; width: 200px; margin: 0 auto 20px auto; padding: 10px; background-color: #1a73e8; color: white; text-align: center; cursor: pointer; border-radius: 5px; border:none; }} @media print {{ .print-btn {{ display: none; }} }}</style></head><body><button class="print-btn" onclick="window.print()">🖨️ 지도안 인쇄하기</button><h1 style="text-align:center;">{sub}과 교수·학습 과정안</h1><table><tr><th>일 시</th><td>{st.session_state.get('class_date','')}</td><th>장 소</th><td>{st.session_state.get('class_location','')}</td></tr><tr><th>대 상</th><td>{st.session_state.get('target_students','')}</td><th>지도 교사</th><td>{teacher_display}</td></tr></table><h3>| 1. 수업 개요 및 의도</h3><p>{d.get('overview','')}</p><h3>| 2. CBI 목표</h3><ul><li><b>거시/미시:</b> {d.get('macro','')} / {d.get('micro','')}</li><li><b>목표:</b> {d.get('objective','')}</li><li><b>일반화:</b> {d.get('big_idea','')}</li></ul><h3>| 3. 전개</h3><table><tr><th width="10%">단계</th><th width="10%">시량</th><th width="60%">교수·학습 활동</th><th width="20%">유의점</th></tr><tr><td align="center">도 입</td><td align="center">{d.get('intro_time','')}</td><td>{d.get('intro_act','').replace(chr(10), '<br>')}</td><td>{d.get('intro_note','').replace(chr(10), '<br>')}</td></tr><tr><td align="center">전 개</td><td align="center">{d.get('dev_time','')}</td><td>{d.get('dev_act','').replace(chr(10), '<br>')}</td><td>{d.get('dev_note','').replace(chr(10), '<br>')}</td></tr><tr><td align="center">정 리</td><td align="center">{d.get('conc_time','')}</td><td>{d.get('conc_act','').replace(chr(10), '<br>')}</td><td>{d.get('conc_note','').replace(chr(10), '<br>')}</td></tr></table></body></html>"""
                with c_a: st.download_button("📥 1. 지도안", data=html_plan.encode('utf-8'), file_name="지도안.html", mime="text/html", type="primary", use_container_width=True)

            if st.session_state.worksheet_detail:
                w = st.session_state.worksheet_detail
                d = st.session_state.selected_session_detail
                html_work = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><style>@page {{ size: A4; margin: 20mm; }} body {{ font-family: 'Malgun Gothic', sans-serif; }} .box {{ border: 1px dashed #333; padding: 15px; margin-bottom: 10px; }} .print-btn {{ display: block; width: 200px; margin: 0 auto 20px auto; padding: 10px; background-color: #2b8a3e; color: white; cursor: pointer; border-radius: 5px; text-align:center; border:none; }} @media print {{ .print-btn {{ display: none; }} }}</style></head><body><button class="print-btn" onclick="window.print()">🖨️ 활동지 인쇄하기</button><div style="border: 2px solid #000; padding: 15px; border-radius: 8px;"><h1 style="text-align:center; margin:0;">[탐구 활동지] {w.get('title','')}</h1><div style="text-align:right; font-weight:bold; margin-top:10px;">{info_line}</div><div><b>[거시/미시]</b> {d.get('macro','')} / {d.get('micro','')}</div><div><b>[목표]</b> {d.get('objective','')}</div><div><b>[핵심 아이디어]</b> {d.get('big_idea','')}</div></div><h3>{w.get('act1_title','')}</h3><div class="box">{w.get('act1_desc','').replace(chr(10), '<br>')}</div><h3>{w.get('act2_title','')}</h3><div class="box"><b>▶ 나의 질문: </b></div><h3>{w.get('act3_title','')}</h3><div class="box" style="min-height:100px;"></div><h3>{w.get('wrap_up','[마무리]')}</h3></body></html>"""
                with c_b: st.download_button("📥 2. 활동지", data=html_work.encode('utf-8'), file_name="활동지.html", mime="text/html", type="primary", use_container_width=True)

            if st.session_state.quiz_detail:
                q = st.session_state.quiz_detail
                ox_html = "".join([f"<li>{item['q']} ( O , X )</li>" for item in q.get('ox_quiz', [])])
                init_html = "".join([f"<li>{item['q']} ( 정답: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; )</li>" for item in q.get('initial_quiz', [])])
                vocab_html = "".join([f"<li>{item['q']}<br>( 정답: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; )</li>" for item in q.get('vocab_quiz', [])])
                mcq_html = ""
                for item in q.get('mcq', []):
                    opt_str = "<ol>" + "".join([f"<li>{opt}</li>" for item_opt in item.get('options', [])]) + "</ol>"
                    mcq_html += f"<li>{item['q']}{opt_str}</li>"
                ans_html = "<ul>"
                for item in q.get('ox_quiz', []): ans_html += f"<li><b>[O/X]</b> 정답: {item['a']} - {item.get('exp','')}</li>"
                for item in q.get('initial_quiz', []): ans_html += f"<li><b>[초성]</b> 정답: {item['a']} - {item.get('exp','')}</li>"
                for item in q.get('vocab_quiz', []): ans_html += f"<li><b>[어휘]</b> 정답: {item['a']} - {item.get('exp','')}</li>"
                for item in q.get('mcq', []): ans_html += f"<li><b>[객관식]</b> 정답: {item['a']} - {item.get('exp','')}</li>"
                ans_html += "</ul>"

                html_quiz = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><style>@page {{ size: A4; margin: 20mm; }} body {{ font-family: 'Malgun Gothic', sans-serif; }} .print-btn {{ display: block; width: 200px; margin: 0 auto 20px auto; padding: 10px; background-color: #f59f00; color: white; text-align: center; cursor: pointer; border-radius: 5px; border:none; }} .page-break {{ page-break-before: always; margin-top: 40px; padding-top: 20px; border-top: 2px dashed #000; }} @media print {{ .print-btn {{ display: none; }} }}</style></head><body><button class="print-btn" onclick="window.print()">🖨️ 평가 및 해설지 인쇄</button><div style="border:2px solid #000; padding:15px; text-align:center; border-radius:8px;"><h1 style="margin:0;">[형성평가] {q.get('title', '')}</h1><div style="text-align:right; font-weight:bold; margin-top:10px;">{info_line}</div></div><h3>🎯 O/X 퀴즈</h3><ul>{ox_html}</ul><h3>🎯 초성 퀴즈</h3><ul>{init_html}</ul><h3>🎯 어휘 퀴즈</h3><ul>{vocab_html}</ul><h3>🎯 객관식 퀴즈</h3><ol>{mcq_html}</ol>
                <div class="page-break"><h2 style="color: #e03131;">[교사용] 정답 및 해설</h2>{ans_html}</div></body></html>"""
                with c_c: st.download_button("📥 3. 평가/해설", data=html_quiz.encode('utf-8'), file_name="형성평가.html", mime="text/html", type="primary", use_container_width=True)

                csv_rows = []
                for item in q.get('ox_quiz', []): csv_rows.append({"유형": "OX", "문제": item['q'], "정답": item['a'], "보기1": "O", "보기2": "X", "보기3": "", "보기4": "", "해설": item.get('exp','')})
                for item in q.get('initial_quiz', []): csv_rows.append({"유형": "단답형", "문제": item['q'], "정답": item['a'], "보기1": "", "보기2": "", "보기3": "", "보기4": "", "해설": item.get('exp','')})
                for item in q.get('vocab_quiz', []): csv_rows.append({"유형": "단답형", "문제": item['q'], "정답": item['a'], "보기1": "", "보기2": "", "보기3": "", "보기4": "", "해설": item.get('exp','')})
                for item in q.get('mcq', []):
                    opts = item.get('options', ["","","",""])
                    csv_rows.append({"유형": "객관식", "문제": item['q'], "정답": item['a'], "보기1": opts[0] if len(opts)>0 else "", "보기2": opts[1] if len(opts)>1 else "", "보기3": opts[2] if len(opts)>2 else "", "보기4": opts[3] if len(opts)>3 else "", "해설": item.get('exp','')})
                df_quiz = pd.DataFrame(csv_rows)
                with c_d: st.download_button("📥 4. 퀴즈앤(CSV)", data=df_quiz.to_csv(index=False, encoding='utf-8-sig'), file_name="퀴즈앤_일괄등록.csv", mime="text/csv", type="secondary", use_container_width=True)

    # --------------------------------------------------------------------------------
    # [메뉴 2, 3, 4] 행사, 사안, 세특, 알림장
    # --------------------------------------------------------------------------------
    elif st.session_state.current_page == "행사 기획":
        st.subheader("🎉 대형 행사 시나리오 & 기안문 자동 생성기")
        col1, col2 = st.columns(2)
        with col1: event_name = st.text_input("행사명", placeholder="예) 2026학년도 교실로 찾아가는 교육과정 박람회")
        with col2: event_date = st.text_input("행사 일시 및 장소", placeholder="예) 6월 10일 (수), 대강당")
        event_purpose = st.text_area("행사 목적 및 주요 식순(키워드)", placeholder="예) 개회식, 교장선생님 인사말, 학생 서포터즈 발대식, 부스 투어")
        if st.button("🎉 공식 기안문 & 대본 생성하기", type="primary"):
            if not st.session_state.get("api_key"): st.error("👈 우측 상단에 API 키를 먼저 입력해 주세요.")
            elif event_name and event_purpose:
                with st.spinner("AI가 교무 행정 양식에 맞춰 완벽한 문서를 기안하고 있습니다..."):
                    prompt = f"당신은 고등학교 부장교사입니다. 행사명: {event_name}, 일시/장소: {event_date}, 주요내용: {event_purpose}. \n두 가지를 작성하세요.\n1. 내부 결재용 기안문 초안 (목적, 방침, 세부 일정 포함)\n2. 행사 당일 사회자(진행자)의 매끄러운 오프닝 및 진행 시나리오 대본"
                    try:
                        res_text = call_gemini_robust(st.session_state.api_key, prompt)
                        st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
                        st.markdown(res_text)
                        st.markdown("</div>", unsafe_allow_html=True)
                    except Exception as e: st.error(str(e))

    elif st.session_state.current_page == "사안 보고":
        st.subheader("🛡️ 교권 보호 사안 보고서 & 상담 매뉴얼 생성기")
        incident_memo = st.text_area("발생한 사안이나 민원 내용을 자유롭게 적어주세요.", placeholder="예) 수업 중에 A학생이 엎드려 자길래 깨웠더니 소리를 지르고 욕설을 함.", height=150)
        if st.button("🛡️ 객관적 보고서 및 대응 스크립트 생성", type="primary"):
            if not st.session_state.get("api_key"): st.error("👈 우측 상단에 API 키를 먼저 입력해 주세요.")
            elif incident_memo:
                with st.spinner("AI가 감정을 배제하고 공식 보고서와 정중한 대응 매뉴얼을 작성 중입니다..."):
                    prompt = f"당신은 학교 폭력 및 교권 침해 대응 전문가입니다. 다음 교사의 메모를 바탕으로 두 가지를 작성하세요: {incident_memo}\n1. 육하원칙에 입각한 객관적이고 건조한 공식 사안 보고서 초안\n2. 학부모 상담 시 감정적 충돌을 피하면서 단호하고 정중하게 대응할 수 있는 교사용 전화/면담 스크립트"
                    try:
                        res_text = call_gemini_robust(st.session_state.api_key, prompt)
                        st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
                        st.markdown(res_text)
                        st.markdown("</div>", unsafe_allow_html=True)
                    except Exception as e: st.error(str(e))

    elif st.session_state.current_page == "세특 초안":
        st.subheader("💡 학생 세특(관찰) 초안 생성기")
        col1, col2 = st.columns(2)
        with col1: stu_name = st.text_input("학생 이름")
        with col2: stu_level = st.selectbox("성취 수준", ["상 (우수함, 주도적)", "중 (성실함, 무난함)", "하 (노력 요함)"])
        stu_activity = st.text_area("주요 관찰 내용 및 활동 키워드", placeholder="예) 인공지능 윤리를 주제로 한 찬반 토론에서 사회자 역할을 맡아 갈등을 조율함.")
        if st.button("✨ 세특 초안 생성하기", type="primary"):
            if not st.session_state.get("api_key"): st.error("👈 우측 상단에 API 키를 먼저 입력해 주세요.")
            elif stu_name and stu_activity:
                with st.spinner("NEIS 양식에 맞게 문장을 작성 중입니다..."):
                    prompt = f"당신은 고등학교 교사입니다. 학생 '{stu_name}'의 세특을 작성합니다. 수준: {stu_level} / 관찰: {stu_activity}. 명사형 종결어미(~함, ~임)를 사용하고, 500자 내외로 전문적이고 긍정적으로 작성하세요."
                    try:
                        st.markdown("<div class='custom-card'>" + call_gemini_robust(st.session_state.api_key, prompt) + "</div>", unsafe_allow_html=True)
                    except Exception as e: st.error(str(e))

    elif st.session_state.current_page == "알림장":
        st.subheader("💌 학급 알림장/가정통신문 자동 생성기")
        msg_context = st.text_area("전달할 핵심 내용 입력", placeholder="예) 내일 체험학습 감. 도시락 꼭 싸오고 8시 반까지 운동장 집합.")
        if st.button("💌 알림장 문구 생성", type="primary"):
            if not st.session_state.get("api_key"): st.error("👈 우측 상단에 API 키를 먼저 입력해 주세요.")
            elif msg_context:
                with st.spinner("정중한 문구로 변환 중입니다..."):
                    prompt = f"다정하고 꼼꼼한 고등학교 담임교사입니다. 학부모님과 학생 단체 문자로 보낼 수 있게 알림장 형태로 다듬어주세요. 내용: {msg_context}."
                    try:
                        st.markdown("<div class='custom-card'>" + call_gemini_robust(st.session_state.api_key, prompt) + "</div>", unsafe_allow_html=True)
                    except Exception as e: st.error(str(e))

    # --------------------------------------------------------------------------------
    # 🌟 [메뉴 5] 등록부 (연수명+일시+장소 세트 관리 및 HTML 인쇄 개선)
    # --------------------------------------------------------------------------------
    elif st.session_state.current_page == "등록부":
        st.subheader("📋 온라인 등록부 및 전자 서명 (HTML 인쇄 지원)")
        
        # 🌟 데이터 구조 변경: 연수명, 일시, 장소를 딕셔너리로 세트 관리
        if "training_data" not in st.session_state:
            st.session_state.training_data = {
                "2026학년도 새학년 집중준비기간 연수": {"date": "2026. 02. 11. 14:00", "loc": "본관 대강당"},
                "전남글빛국어교육연구회 공개수업": {"date": "2026. 10. 14. 14:00", "loc": "1학년 6반 교실"}
            }

        with st.expander("⚙️ 연수 관리자 설정 (비밀번호: 1234)"):
            if st.text_input("비밀번호", type="password", key="reg_pw") == "1234":
                st.markdown("**새로운 연수 개설**")
                c_new1, c_new2, c_new3 = st.columns([2, 1, 1])
                with c_new1: new_title = st.text_input("연수명")
                with c_new2: new_date = st.text_input("일시", placeholder="예) 10. 20. 15:00")
                with c_new3: new_loc = st.text_input("장소", placeholder="예) 시청각실")
                if st.button("➕ 연수 추가하기"):
                    if new_title:
                        st.session_state.training_data[new_title] = {"date": new_date, "loc": new_loc}
                        st.success(f"'{new_title}' 추가 완료!")
                        time.sleep(0.5)
                        st.rerun()
        
        st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
        # 🌟 등록 화면: 선택 시 일시와 장소가 자동으로 따라옴
        selected_training = st.selectbox("📌 참여할 연수 선택", list(st.session_state.training_data.keys()))
        
        reg_date = st.session_state.training_data[selected_training]["date"]
        reg_loc = st.session_state.training_data[selected_training]["loc"]
        
        st.info(f"📅 **일시:** {reg_date if reg_date else '미지정'} &nbsp;&nbsp;|&nbsp;&nbsp; 🏫 **장소:** {reg_loc if reg_loc else '미지정'}")
        st.write("---")
        
        c1, c2, c3 = st.columns(3)
        with c1: in_dept = st.text_input("소속", placeholder="예) 광영고")
        with c2: in_pos = st.text_input("직위", placeholder="예) 교사")
        with c3: in_name = st.text_input("이름", placeholder="예) 홍길동")
        
        st.write("✍️ **서명** - 마우스나 스마트폰 터치로 서명해 주세요.")
        
        canvas_result = st_canvas(
            stroke_width=3, 
            stroke_color="#000000", 
            background_color="#ffffff", 
            height=100, 
            width=400, 
            drawing_mode="freedraw", 
            update_streamlit=True, 
            return_image_data=True, 
            key=f"sig_canvas_{st.session_state.canvas_key}"
        )

        if st.button("✅ 서명 완료 및 제출", type="primary", use_container_width=True):
            if not in_name:
                st.warning("이름을 입력하세요.")
            elif canvas_result.image_data is None:
                st.warning("⚠️ 서명을 그려주세요!")
            else:
                sig_base64 = ""
                img_array = canvas_result.image_data
                
                # 배경이 완전히 비어있는지(흰색/투명) 확인
                if np.min(img_array[:, :, :3]) < 255:
                    img_pil = Image.fromarray(img_array.astype('uint8'), 'RGBA')
                    img_rgb = Image.new("RGB", img_pil.size, (255, 255, 255))
                    img_rgb.paste(img_pil, mask=img_pil.split()[3])
                    
                    buffered = io.BytesIO()
                    img_rgb.save(buffered, format="PNG")
                    sig_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                    
                    new_row = pd.DataFrame([{
                        "연번": len(st.session_state.registry_df)+1, 
                        "연수명": selected_training, 
                        "일시": reg_date,
                        "장소": reg_loc,
                        "소속": in_dept, 
                        "직위": in_pos, 
                        "이름": in_name, 
                        "서명 상태": "✅ 완료", 
                        "서명 이미지": sig_base64, 
                        "등록 일시": datetime.now().strftime("%m-%d %H:%M")
                    }])
                    st.session_state.registry_df = pd.concat([st.session_state.registry_df, new_row], ignore_index=True)
                    st.success(f"{in_name} 선생님의 손글씨 서명이 완벽하게 등록되었습니다!")
                    
                    st.session_state.canvas_key += 1
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("⚠️ 서명이 인식되지 않았습니다. 캔버스에 서명을 다시 그려주세요!")
                    
        st.markdown("</div>", unsafe_allow_html=True)
        
        # 화면 출력용 데이터 프레임 (이미지는 숨김)
        display_df = st.session_state.registry_df[st.session_state.registry_df["연수명"] == selected_training]
        st.dataframe(display_df.drop(columns=["서명 이미지", "연수명", "일시", "장소"], errors="ignore"), hide_index=True, use_container_width=True)
        
        if not display_df.empty:
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.download_button("📥 엑셀(CSV) 다운로드", data=display_df.to_csv(index=False, encoding='utf-8-sig'), file_name=f"{selected_training}_등록부.csv", mime="text/csv", use_container_width=True)
            
            with col_d2:
                rows_html = ""
                for idx, row in display_df.iterrows():
                    img_tag = f'<img src="data:image/png;base64,{row["서명 이미지"]}" style="height: 40px; max-width: 140px; object-fit: contain;"/>' if row.get("서명 이미지") else ""
                    rows_html += f"<tr><td>{row['연번']}</td><td>{row['소속']}</td><td>{row['직위']}</td><td>{row['이름']}</td><td>{img_tag}</td></tr>"

                html_registry = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>연수 등록부</title>
<style>
    @page {{ size: A4; margin: 20mm; }}
    body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.5; color: #000; }}
    h1 {{ text-align: center; font-size: 26px; border-bottom: 2px solid #000; padding-bottom: 15px; margin-bottom: 20px; letter-spacing: 2px; }}
    .info-table {{ width: 100%; border: none; margin-bottom: 15px; font-size: 15px; font-weight: bold; }}
    .info-table td {{ padding: 5px; border: none; }}
    .reg-table {{ width: 100%; border-collapse: collapse; font-size: 14px; text-align: center; table-layout: fixed; }}
    .reg-table th, .reg-table td {{ border: 1px solid #000; padding: 10px; vertical-align: middle; height: 45px; }}
    .reg-table th {{ background-color: #f2f2f2; font-weight: bold; border: 1px solid #000; }}
    .col-no {{ width: 8%; }}
    .col-dept {{ width: 25%; }}
    .col-pos {{ width: 15%; }}
    .col-name {{ width: 20%; }}
    .col-sig {{ width: 32%; }}
    .print-btn {{ display: block; width: 200px; margin: 0 auto 20px auto; padding: 10px; background-color: #2b8a3e; color: white; text-align: center; cursor: pointer; border: none; border-radius: 5px; font-size: 16px; font-weight: bold; }}
    @media print {{ .print-btn {{ display: none; }} }}
</style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">🖨️ 서명 포함 등록부 인쇄</button>
    <h1>연수(회의) 등록부</h1>
    <table class="info-table">
        <tr><td width="15%">연 수 명 :</td><td>{selected_training}</td></tr>
        <tr><td>일 시 :</td><td>{reg_date}</td></tr>
        <tr><td>장 소 :</td><td>{reg_loc}</td></tr>
    </table>
    <table class="reg-table">
        <tr><th class="col-no">연번</th><th class="col-dept">소속</th><th class="col-pos">직위</th><th class="col-name">이름</th><th class="col-sig">서명</th></tr>
        {rows_html}
    </table>
</body>
</html>"""
                st.download_button("🖨️ 등록부 인쇄 (손글씨 포함 HTML)", data=html_registry.encode('utf-8'), file_name=f"{selected_training}_등록부.html", mime="text/html", type="primary", use_container_width=True)

# ==========================================
# [오른쪽 20%] 🌟 API 키 및 유용한 정보
# ==========================================
with col_info:
    # 🌟 API 키 입력란 (우측 상단 대문짝 배치 유지)
    st.markdown("<div style='background-color:#e3f2fd; padding: 15px; border-radius: 10px; border: 2px solid #2196f3; margin-bottom: 20px;'>", unsafe_allow_html=True)
    st.markdown("<h4 style='margin-top:0; color:#0d47a1; text-align:center;'>🔑 API 키 입력 (필수)</h4>", unsafe_allow_html=True)
    st.session_state.api_key = st.text_input("Gemini API 키", type="password", placeholder="여기에 키를 붙여넣으세요", label_visibility="collapsed")
    if not st.session_state.api_key: 
        st.markdown("<div style='color:#c62828; font-weight:bold; text-align:center; font-size:14px;'>⚠️ 키 입력이 필요합니다</div>", unsafe_allow_html=True)
    else: 
        st.markdown("<div style='color:#2e7d32; font-weight:bold; text-align:center; font-size:14px;'>🟢 AI 연동 준비 완료!</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

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
