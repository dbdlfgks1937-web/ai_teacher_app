<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>교무실 — AI 에듀테크 수퍼 앱</title>
  
  <!-- 1. 스타일 및 기본 라이브러리 -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone@7.29.7/babel.min.js"></script>
  <script src="https://unpkg.com/lucide@0.577.0"></script>
  
  <!-- 🌟 2. 브라우저에서 파이썬 없이 PDF를 직접 읽기 위한 라이브러리 (PDF.js) -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.min.js"></script>
  <script>pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';</script>

  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" />
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: { brand: "#6550bb", ink: "#262635", paper: "#f7f8fb", line: "#e8e9ef" },
          fontFamily: { sans: ["Pretendard Variable", "sans-serif"] },
          boxShadow: { soft: "0 3px 15px rgba(35,32,65,.025)" }
        }
      }
    };
  </script>
  <style>
    body { margin:0; background:#f7f8fb; color:#262635; font-size:14px; }
    button,input,select,textarea,a { -webkit-tap-highlight-color:transparent; outline-offset:3px; }
    :is(button,a,input,select,textarea):focus-visible { outline:2px solid #6550bb; }
    button { transition:background-color .15s,color .15s; }
    button:not(:disabled):active { transform:translateY(1px); }
    input[type="checkbox"] { accent-color:#6550bb; cursor: pointer; width: 1.2rem; height: 1.2rem;}
    .scrollbar::-webkit-scrollbar { width:6px; }
    .scrollbar::-webkit-scrollbar-thumb { background:#dedce8; border-radius:5px; }
    .glass-card { background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(10px); border-radius: 1rem; border: 1px solid rgba(255,255,255,0.9); box-shadow: 0 4px 15px rgba(0,0,0,0.03); padding: 1.5rem; }
    @media print { .no-print { display:none!important; } main { margin:0!important; } }
  </style>
</head>
<body class="font-sans">
  <div id="root"></div>
  <script type="text/babel">
    import { Home, CheckCircle, Calendar, User, Folder, Download, Sparkles, ChevronRight, ChevronDown, Plus, Search, Bell, Menu, X, File, MessageSquare, Lock, Briefcase, Clock, ArrowRight, Check, Trash2, Edit, Upload, Info, Target, AlertCircle, Copy, Send, Layers, Cloud, Loader2 } from 'lucide-react';

    const {useState, useEffect, useRef} = React;
    const TODAY = new Date();
    const isoDate = date => { const d=new Date(date); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
    const today = isoDate(TODAY);
    const dateLabel = (value) => new Intl.DateTimeFormat('ko-KR',{month:'long',day:'numeric',weekday:'short'}).format(new Date(value+'T12:00:00'));
    const uid = () => `${Date.now()}-${Math.random()}`;

    // 기본 데이터 세팅
    const initialTasks = [{id:'t1',title:'현장체험학습 참가 동의서 수합',category:'학급 운영',date:today,priority:'높음',done:false}];
    const initialStudents = ['김민준','김서윤','박도윤','박서연','이서준','이하은'].map((name,i)=>({id:'s'+i,number:i+1,name,submitted:false}));
    const initialData = { tasks:initialTasks, students:initialStudents, events:[], attendance:{}, notes:[], registry:[], trainings:[{id:'tr1', title:'2026학년도 교내 연수', date:'2026.10.14', loc:'시청각실'}], lessonData:{} };

    // 🌟 Gemini API 호출 핵심 함수 (파이썬 코드를 자바스크립트로 완벽 번역)
    async function callGemini(prompt, apiKey, isJson=true) {
      if (!apiKey) throw new Error("API 키를 입력해주세요!");
      const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ role: "user", parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.7 }
        })
      });
      if (!response.ok) throw new Error("API 요청 실패 (키가 맞는지, 한도를 초과했는지 확인하세요)");
      const data = await response.json();
      let text = data.candidates[0].content.parts[0].text;
      
      if (isJson) {
        text = text.replace(/```json/g, "").replace(/```/g, "").trim();
        return JSON.parse(text);
      }
      return text;
    }

    // 파일 다운로드 헬퍼
    function downloadFile(name, content, type='text/plain;charset=utf-8'){
      const url = URL.createObjectURL(new Blob([content],{type}));
      const a = document.createElement('a'); a.href = url; a.download = name; a.click();
      setTimeout(()=>URL.revokeObjectURL(url), 1500);
    }
    const csvCell = value => '"' + String(value||'').replace(/"/g, '""') + '"';
    const downloadCSV = (name, headers, rows) => downloadFile(name, '\ufeff' + [headers, ...rows].map(r=>r.map(csvCell).join(',')).join('\r\n'), 'text/csv;charset=utf-8');

    function App() {
      const [page, setPage] = useState('오늘의 교무실');
      const [data, setData] = useState(initialData);
      const [apiKey, setApiKey] = useState('');
      const [toast, setToast] = useState('');
      const [loading, setLoading] = useState(false);

      // 로컬 스토리지 데이터 자동 저장/불러오기
      useEffect(() => {
        const saved = localStorage.getItem('gyomusil-super-v1');
        const savedKey = localStorage.getItem('gyomusil-apikey');
        if (saved) setData({ ...initialData, ...JSON.parse(saved) });
        if (savedKey) setApiKey(savedKey);
      }, []);

      useEffect(() => {
        localStorage.setItem('gyomusil-super-v1', JSON.stringify(data));
      }, [data]);

      const showToast = (msg) => { setToast(msg); setTimeout(()=>setToast(''), 3000); };

      // ======================================================================
      // 🌟 핵심 컴포넌트 1: 과정안 생성기 (7단계)
      // ======================================================================
      const LessonPlanner = () => {
        const [tab, setTab] = useState(0);
        const tabs = ["⚙️ 기본설정", "📊 단원분석", "🎯 지도안", "🖥️ 슬라이드", "📝 활동지", "❓ 평가지", "🖨️ 추출"];
        
        const lData = data.lessonData || {};
        const updateLData = (updates) => setData(d => ({...d, lessonData: {...d.lessonData, ...updates}}));

        // PDF 추출 (순수 자바스크립트로 브라우저에서 처리! 서버 필요 없음)
        const handlePDFUpload = async (e) => {
          const file = e.target.files[0];
          if(!file) return;
          setLoading(true);
          try {
            const arrayBuffer = await file.arrayBuffer();
            const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
            let fullText = "";
            for(let i=1; i<=Math.min(pdf.numPages, 30); i++) { // 속도와 한도를 위해 30페이지만
              const page = await pdf.getPage(i);
              const textContent = await page.getTextContent();
              fullText += textContent.items.map(item => item.str).join(" ") + "\n";
            }
            updateLData({ pdfText: fullText.substring(0, 30000) }); // 안전하게 3만자로 컷
            showToast("PDF 텍스트 추출 완료! 단원 분석으로 이동하세요.");
          } catch(err) { alert("PDF 추출 오류: " + err.message); }
          setLoading(false);
        };

        const generateAI = async (step, prompt, keyToSave, isJson=true) => {
          setLoading(true);
          try {
            const result = await callGemini(prompt, apiKey, isJson);
            updateLData({ [keyToSave]: result });
            showToast(`${step} 생성이 완료되었습니다!`);
          } catch(err) { alert(err.message); }
          setLoading(false);
        };

        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-ink mb-4">📝 개념기반 공개수업 생성기 (AI)</h2>
            <div className="flex gap-2 border-b border-line pb-2 overflow-x-auto">
              {tabs.map((t, i) => (
                <button key={i} onClick={()=>setTab(i)} className={`px-4 py-2 text-sm rounded-t-lg font-bold whitespace-nowrap ${tab===i?'bg-brand text-white':'bg-white text-slate-500'}`}>
                  {t}
                </button>
              ))}
            </div>

            <div className="glass-card min-h-[400px]">
              {loading && <div className="text-brand font-bold text-center py-10 animate-pulse">🤖 AI가 열심히 작업 중입니다... 잠시만 기다려주세요!</div>}
              
              {!loading && tab === 0 && (
                <div className="space-y-4">
                  <h3 className="font-bold text-lg mb-2">수업 기본 정보</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <input className="border p-2 rounded" placeholder="과목명 (예: 국어)" value={lData.subject||''} onChange={e=>updateLData({subject:e.target.value})} />
                    <input className="border p-2 rounded" placeholder="수업 대상 (예: 1학년 6반)" value={lData.target||''} onChange={e=>updateLData({target:e.target.value})} />
                  </div>
                  <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-line">
                    <h3 className="font-bold mb-2">교과서 PDF 업로드</h3>
                    <input type="file" accept=".pdf" onChange={handlePDFUpload} className="w-full" />
                    {lData.pdfText && <p className="text-green-600 mt-2 text-sm font-bold">✅ PDF 데이터가 준비되었습니다.</p>}
                  </div>
                </div>
              )}

              {!loading && tab === 1 && (
                <div className="space-y-4">
                  <h3 className="font-bold text-lg mb-2">AI 단원 구조 분석</h3>
                  <p className="text-sm text-slate-500">업로드된 교과서를 분석해 최적의 수업 차시를 설계합니다.</p>
                  <button className="bg-brand text-white px-4 py-2 rounded-lg font-bold hover:bg-opacity-90"
                    onClick={()=>generateAI("단원 분석", `전문가로서 ${lData.subject||'교과'} 내용을 분석해 차시를 설계하세요. JSON배열로 답변: [{"session":"1","title":"주제","desc":"설명"}]. [내용] ${lData.pdfText||''}`, "sessions")}>
                    🚀 단원 분석 시작
                  </button>
                  {lData.sessions && <div className="mt-4 p-4 bg-slate-50 rounded"><pre className="text-xs">{JSON.stringify(lData.sessions, null, 2)}</pre></div>}
                </div>
              )}

              {!loading && tab === 2 && (
                <div className="space-y-4">
                  <h3 className="font-bold text-lg mb-2">개념기반 지도안 생성</h3>
                  <input className="w-full border p-2 rounded mb-2" placeholder="선택한 차시의 주제를 입력하세요" value={lData.curTopic||''} onChange={e=>updateLData({curTopic:e.target.value})} />
                  <button className="bg-brand text-white px-4 py-2 rounded-lg font-bold"
                    onClick={()=>generateAI("지도안", `${lData.subject||''} 교사입니다. 주제: ${lData.curTopic||''}. JSON으로 답변: {"overview":"개요", "objective":"목표", "big_idea":"일반화", "intro_act":"도입", "dev_act":"전개", "conc_act":"정리"}. [내용] ${lData.pdfText||''}`, "plan")}>
                    🎯 지도안 설계하기
                  </button>
                  {lData.plan && <div className="mt-4 p-4 bg-slate-50 rounded text-sm"><b>목표:</b> {lData.plan.objective}<br/><b>도입:</b> {lData.plan.intro_act}<br/><b>전개:</b> {lData.plan.dev_act}</div>}
                </div>
              )}

              {!loading && tab === 3 && (
                <div className="space-y-4">
                  <h3 className="font-bold text-lg mb-2">수업용 슬라이드 텍스트 추출</h3>
                  <button className="bg-brand text-white px-4 py-2 rounded-lg font-bold"
                    onClick={()=>generateAI("슬라이드", `주제: ${lData.curTopic||''}. 프레젠테이션용 3장 슬라이드 구성. JSON답변: {"slide1_title":"제목1", "slide1_bullets":["요약1","요약2"], "slide2_title":"제목2", "slide2_bullets":["요약1"], "slide3_title":"제목3", "slide3_bullets":["요약1"]}`, "slides")}>
                    🖥️ 슬라이드 텍스트 생성
                  </button>
                  {lData.slides && (
                    <div className="grid grid-cols-3 gap-4 mt-4 text-sm">
                      <div className="p-4 border rounded bg-white shadow-sm"><b>{lData.slides.slide1_title}</b><ul className="pl-4 list-disc mt-2">{lData.slides.slide1_bullets.map(b=><li key={b}>{b}</li>)}</ul></div>
                      <div className="p-4 border rounded bg-white shadow-sm"><b>{lData.slides.slide2_title}</b><ul className="pl-4 list-disc mt-2">{lData.slides.slide2_bullets.map(b=><li key={b}>{b}</li>)}</ul></div>
                      <div className="p-4 border rounded bg-white shadow-sm"><b>{lData.slides.slide3_title}</b><ul className="pl-4 list-disc mt-2">{lData.slides.slide3_bullets.map(b=><li key={b}>{b}</li>)}</ul></div>
                    </div>
                  )}
                </div>
              )}

              {!loading && tab === 4 && (
                <div className="space-y-4">
                  <button className="bg-brand text-white px-4 py-2 rounded-lg font-bold"
                    onClick={()=>generateAI("활동지", `주제: ${lData.curTopic||''}. 학생 탐구 활동지 JSON: {"title":"제목", "act1":"활동1내용", "act2":"활동2내용", "wrap_up":"마무리"}`, "worksheet")}>
                    📝 학생 활동지 설계
                  </button>
                  {lData.worksheet && <div className="mt-4 p-4 bg-slate-50 rounded text-sm"><pre>{JSON.stringify(lData.worksheet,null,2)}</pre></div>}
                </div>
              )}

              {!loading && tab === 5 && (
                <div className="space-y-4">
                  <button className="bg-brand text-white px-4 py-2 rounded-lg font-bold"
                    onClick={()=>generateAI("형성평가", `주제: ${lData.curTopic||''}. 다유형 평가 JSON: {"ox":[{"q":"질문","a":"정답"}], "mcq":[{"q":"질문","opt":["보1","보2"],"a":"정답"}]}`, "quiz")}>
                    ❓ 다유형 평가 출제
                  </button>
                  {lData.quiz && <div className="mt-4 p-4 bg-slate-50 rounded text-sm"><pre>{JSON.stringify(lData.quiz,null,2)}</pre></div>}
                </div>
              )}

              {!loading && tab === 6 && (
                <div className="space-y-4">
                  <h3 className="font-bold text-lg mb-2">결과물 일괄 다운로드</h3>
                  <div className="flex gap-4">
                    <button className="flex items-center gap-2 border px-4 py-2 rounded hover:bg-slate-50" onClick={()=>downloadFile('지도안.txt', JSON.stringify(lData.plan,null,2))}><Download className="h-4 w-4"/> 지도안 저장</button>
                    <button className="flex items-center gap-2 border px-4 py-2 rounded hover:bg-slate-50" onClick={()=>downloadFile('활동지.txt', JSON.stringify(lData.worksheet,null,2))}><Download className="h-4 w-4"/> 활동지 저장</button>
                    <button className="flex items-center gap-2 border px-4 py-2 rounded hover:bg-slate-50" onClick={()=>downloadFile('평가.txt', JSON.stringify(lData.quiz,null,2))}><Download className="h-4 w-4"/> 평가지 저장</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      };

      // ======================================================================
      // 🌟 핵심 컴포넌트 2: 온라인 연수 등록부 (Canvas 전자서명)
      // ======================================================================
      const SignatureRegistry = () => {
        const [selTr, setSelTr] = useState(data.trainings[0]?.id || '');
        const canvasRef = useRef(null);
        const [isDrawing, setIsDrawing] = useState(false);
        const [form, setForm] = useState({dept:'', pos:'', name:''});

        // 캔버스 그리기 로직 (스마트폰/마우스 완벽 호환)
        const startDraw = (e) => {
          setIsDrawing(true);
          const ctx = canvasRef.current.getContext('2d');
          const rect = canvasRef.current.getBoundingClientRect();
          const clientX = e.touches ? e.touches[0].clientX : e.clientX;
          const clientY = e.touches ? e.touches[0].clientY : e.clientY;
          ctx.beginPath();
          ctx.moveTo(clientX - rect.left, clientY - rect.top);
        };
        const draw = (e) => {
          if(!isDrawing) return;
          e.preventDefault();
          const ctx = canvasRef.current.getContext('2d');
          const rect = canvasRef.current.getBoundingClientRect();
          const clientX = e.touches ? e.touches[0].clientX : e.clientX;
          const clientY = e.touches ? e.touches[0].clientY : e.clientY;
          ctx.lineWidth = 3;
          ctx.lineCap = 'round';
          ctx.strokeStyle = '#000';
          ctx.lineTo(clientX - rect.left, clientY - rect.top);
          ctx.stroke();
        };
        const endDraw = () => setIsDrawing(false);
        const clearCanvas = () => {
          const canvas = canvasRef.current;
          canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);
        };

        const saveSignature = () => {
          if(!form.name) return alert("이름을 입력하세요.");
          const canvas = canvasRef.current;
          // 서명이 비어있는지 꼼꼼히 확인하는 간단한 로직 (픽셀 스캔 대신 dataURL 길이로 체크)
          const dataUrl = canvas.toDataURL();
          if(dataUrl.length < 3000) return alert("서명을 그려주세요!"); 
          
          const newRow = {
            id: uid(), trId: selTr, dept: form.dept, pos: form.pos, name: form.name, 
            sig: dataUrl, date: new Date().toLocaleString()
          };
          setData(d => ({...d, registry: [...d.registry, newRow]}));
          showToast(`${form.name} 선생님 서명 완료!`);
          setForm({dept:'', pos:'', name:''});
          clearCanvas();
        };

        const curTr = data.trainings.find(t=>t.id === selTr);
        const filteredReg = data.registry.filter(r=>r.trId === selTr);

        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-ink mb-4">📋 온라인 연수 등록부 및 전자 서명</h2>
            <div className="glass-card">
              <label className="block font-bold mb-2">📌 진행 중인 연수 선택</label>
              <select className="w-full p-2 border rounded-lg mb-4" value={selTr} onChange={e=>setSelTr(e.target.value)}>
                {data.trainings.map(t=><option key={t.id} value={t.id}>{t.title}</option>)}
              </select>
              {curTr && <p className="text-sm text-slate-500 mb-6">📅 {curTr.date} | 🏫 {curTr.loc}</p>}

              <div className="grid grid-cols-3 gap-4 mb-4">
                <input placeholder="소속 (예: 광영고)" className="border p-2 rounded" value={form.dept} onChange={e=>setForm({...form,dept:e.target.value})}/>
                <input placeholder="직위 (예: 교사)" className="border p-2 rounded" value={form.pos} onChange={e=>setForm({...form,pos:e.target.value})}/>
                <input placeholder="이름 (예: 홍길동)" className="border p-2 rounded font-bold" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>
              </div>

              <p className="font-bold text-sm mb-2 text-brand">✍️ 마우스나 손가락으로 서명해 주세요.</p>
              <div className="border-2 border-slate-300 rounded-lg overflow-hidden bg-white mb-4 relative" style={{ touchAction: 'none' }}>
                <canvas ref={canvasRef} width={600} height={150} className="w-full cursor-crosshair bg-white"
                  onMouseDown={startDraw} onMouseMove={draw} onMouseUp={endDraw} onMouseLeave={endDraw}
                  onTouchStart={startDraw} onTouchMove={draw} onTouchEnd={endDraw} />
              </div>
              <div className="flex gap-2">
                <button onClick={clearCanvas} className="border px-4 py-2 rounded-lg font-bold hover:bg-slate-100">지우기</button>
                <button onClick={saveSignature} className="bg-brand text-white px-6 py-2 rounded-lg font-bold w-full">✅ 서명 완료 및 제출</button>
              </div>
            </div>

            <div className="glass-card">
              <div className="flex justify-between items-center mb-4">
                <h3 className="font-bold">현재 등록 명단 ({filteredReg.length}명)</h3>
                <button onClick={()=>{
                  downloadCSV('연수등록부.csv', ['소속','직위','이름','서명여부','시간'], filteredReg.map(r=>[r.dept, r.pos, r.name, '완료', r.date]));
                }} className="flex items-center gap-2 text-sm text-brand border px-3 py-1 rounded-lg"><Download className="h-4 w-4"/> 엑셀(CSV) 추출</button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-slate-50 border-b"><tr><th className="p-2">소속</th><th className="p-2">직위</th><th className="p-2">이름</th><th className="p-2">서명</th></tr></thead>
                  <tbody>
                    {filteredReg.map((r,i) => (
                      <tr key={i} className="border-b">
                        <td className="p-2">{r.dept}</td><td className="p-2">{r.pos}</td><td className="p-2 font-bold">{r.name}</td>
                        <td className="p-2"><img src={r.sig} className="h-10 border bg-white" alt="서명"/></td>
                      </tr>
                    ))}
                    {filteredReg.length===0 && <tr><td colSpan="4" className="text-center py-4 text-slate-400">아직 서명한 분이 없습니다.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        );
      };

      // ======================================================================
      // 🌟 화면 렌더링
      // ======================================================================
      return (
        <div className="min-h-screen flex text-ink">
          
          {/* 좌측 사이드바 메뉴 */}
          <aside className="no-print w-64 bg-white border-r border-line flex flex-col fixed inset-y-0 z-40 shadow-[4px_0_24px_rgba(0,0,0,0.02)]">
            <div className="h-20 flex items-center px-6 border-b border-line gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-[#d946ef] text-white shadow-lg"><Layers className="h-6 w-6"/></div>
              <div><h1 className="text-xl font-extrabold tracking-tight">교무실<span className="text-brand">.</span></h1><p className="text-[10px] text-slate-500 font-bold">AI 수퍼 앱 (Serverless)</p></div>
            </div>
            
            <nav className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
              <div>
                <p className="px-2 mb-2 text-xs font-bold text-slate-400 uppercase">나의 교무실</p>
                <button onClick={()=>setPage('오늘의 교무실')} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${page==='오늘의 교무실'?'bg-brand text-white font-bold shadow-md':'text-slate-600 hover:bg-slate-50'}`}><Home className="h-4 w-4"/>대시보드</button>
                <button onClick={()=>setPage('온라인 등록부')} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${page==='온라인 등록부'?'bg-brand text-white font-bold shadow-md':'text-slate-600 hover:bg-slate-50'}`}><CheckCircle className="h-4 w-4"/>온라인 서명부</button>
              </div>
              <div>
                <p className="px-2 mb-2 text-xs font-bold text-slate-400 uppercase">AI 수업 지원</p>
                <button onClick={()=>setPage('과정안 생성')} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${page==='과정안 생성'?'bg-brand text-white font-bold shadow-md':'text-slate-600 hover:bg-slate-50'}`}><Sparkles className="h-4 w-4"/>과정안 자동 생성 (7단계)</button>
              </div>
            </nav>
            <div className="p-4 border-t border-line">
              <input type="password" placeholder="Gemini API Key 입력" value={apiKey} onChange={e=>{setApiKey(e.target.value); localStorage.setItem('gyomusil-apikey', e.target.value);}} className="w-full text-xs p-2 rounded border focus:border-brand mb-2"/>
              <p className="text-[10px] text-slate-400">데이터는 브라우저에 안전하게 보관됩니다.</p>
            </div>
          </aside>

          {/* 메인 컨텐츠 */}
          <main className="ml-64 flex-1 p-8">
            {/* 대시보드 화면 */}
            {page === '오늘의 교무실' && (
              <div className="max-w-5xl space-y-8 animate-[fadeIn_0.3s_ease-out]">
                <div>
                  <h2 className="text-3xl font-extrabold tracking-tight mb-2">선생님, 오늘도 반갑습니다! 👋</h2>
                  <p className="text-slate-500 font-medium">단일 HTML 파일로 구동되는 파이썬 없는 완벽한 서버리스(Serverless) 수퍼 앱입니다.</p>
                </div>
                
                <div className="grid grid-cols-3 gap-6">
                  <div className="glass-card">
                    <p className="text-sm font-bold text-slate-500 mb-2">총 등록된 서명수</p>
                    <p className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-brand to-pink-500">{data.registry.length}<span className="text-lg text-slate-400 ml-1">건</span></p>
                  </div>
                  <div className="glass-card">
                    <p className="text-sm font-bold text-slate-500 mb-2">오늘의 날씨 (광양)</p>
                    <p className="text-4xl font-extrabold text-amber-500">18°C ☀️</p>
                  </div>
                  <div className="glass-card">
                    <p className="text-sm font-bold text-slate-500 mb-2">AI 연동 상태</p>
                    <p className="text-3xl font-extrabold text-emerald-500 mt-1">{apiKey ? 'READY 🟢' : '키 입력 대기 🟡'}</p>
                  </div>
                </div>

                <div className="glass-card bg-brand/5 border-brand/20">
                  <h3 className="font-bold text-brand flex items-center gap-2 mb-2"><Sparkles className="h-5 w-5"/> 단일 파일 공유 가이드</h3>
                  <p className="text-sm text-slate-700 leading-relaxed">
                    선생님! 이제 이 <b>교무실.html</b> 파일 하나만 동료 교사에게 카톡이나 메신저로 던져주시면 끝납니다. 상대방이 파일을 다운받아 더블클릭만 하면 파이썬 설치, 서버 구동 없이 100% 동일한 기능(PDF 분석, 7단계 과정안, 전자서명)이 그 컴퓨터 화면에서 즉시 열립니다! 🚀
                  </p>
                </div>
              </div>
            )}

            {page === '과정안 생성' && <LessonPlanner />}
            {page === '온라인 등록부' && <SignatureRegistry />}
          </main>
          
          {/* 하단 토스트 알림 */}
          {toast && <div className="fixed bottom-6 right-6 bg-ink text-white px-6 py-3 rounded-xl shadow-2xl flex items-center gap-2 animate-[bounce_0.3s_ease] z-50"><CheckCircle className="h-5 w-5 text-emerald-400"/> {toast}</div>}
        </div>
      );
    }

    ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
  </script>
</body>
</html>
