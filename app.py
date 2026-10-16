<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>교무실 — 추가 기능 연동 안내</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone@7.29.7/babel.min.js"></script>
  <script src="https://unpkg.com/lucide@0.577.0"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            brand: "#6550bb",
            ink: "#262635",
            paper: "#f7f8fb",
            line: "#e8e9ef"
          },
          fontFamily: {
            sans: ["Pretendard Variable", "sans-serif"]
          }
        }
      }
    };
  </script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" />
  <style>
    body { margin: 0; }
    button, a { -webkit-tap-highlight-color: transparent; }
    :is(button, a, input):focus-visible {
      outline: 2px solid #6550bb;
      outline-offset: 4px;
    }
    pre { tab-size: 4; }
    @media (prefers-reduced-motion: reduce) {
      * { scroll-behavior: auto !important; }
    }
  </style>
</head>
<body class="bg-paper font-sans text-ink">
<div id="root"></div>

<script type="text/babel">
  import {
    Layers, ArrowRight, Check, Copy, Download, File,
    Database, Cloud, Lock, AlertCircle, ChevronRight,
    Code2, CheckCircle, Info
  } from 'lucide-react';

  const { useState, useEffect } = React;

  const backendCode = String.raw`import base64
import binascii
import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "classroom.db"

app = FastAPI(title="교무실 추가 기능 API")

# 개인 컴퓨터의 개발용 출처만 허용합니다.
# CORS는 로그인이나 접근 권한을 대신하지 않습니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8501",
        "http://localhost:8501",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

def connect():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def initialize():
    with connect() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL UNIQUE,
            date TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            position TEXT NOT NULL,
            name TEXT NOT NULL,
            signature TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(training_id) REFERENCES trainings(id)
        );
        """)

initialize()

class TrainingInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    date: str = Field(default="", max_length=100)
    location: str = Field(default="", max_length=200)

class RegistryInput(BaseModel):
    training_id: int = Field(gt=0)
    department: str = Field(default="", max_length=100)
    position: str = Field(default="", max_length=100)
    name: str = Field(min_length=1, max_length=100)
    signature: str = Field(min_length=1, max_length=700000)

@app.get("/api/health")
def health():
    return {"ok": True, "storage": "SQLite"}

@app.get("/api/trainings")
def get_trainings():
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM trainings ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]

@app.post("/api/trainings", status_code=201)
def add_training(body: TrainingInput):
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "연수명을 입력해 주세요.")
    try:
        with connect() as db:
            cursor = db.execute(
                "INSERT INTO trainings (title, date, location) VALUES (?, ?, ?)",
                (title, body.date.strip(), body.location.strip()),
            )
            new_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "같은 이름의 연수가 이미 있습니다.")
    return {"id": new_id, "title": title}

@app.post("/api/pdf-text")
def extract_pdf(file: UploadFile = File(...)):
    # 🌟 [최적화 반영] 동기 함수(def)로 변경하고, 파일 객체 직접 읽기로 변경 
    # 최대 10MiB까지만 읽습니다.
    try:
        content = file.file.read(10 * 1024 * 1024 + 1)
    finally:
        file.file.close()

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "PDF는 10MB 이하로 업로드해 주세요.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(400, "올바른 PDF 파일을 선택해 주세요.")

    try:
        # 개인용 예제입니다. 공개 운영에서는 PDF 분석을
        # 별도 작업 프로세스로 분리하고 처리 시간도 제한하세요.
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if len(pdf.pages) > 80:
                raise HTTPException(400, "한 번에 80쪽 이하로 업로드해 주세요.")
            pages = []
            total_length = 0
            for page in pdf.pages:
                text = page.extract_text() or ""
                total_length += len(text)
                if total_length > 100000:
                    raise HTTPException(
                        400, "추출 분량이 큽니다. PDF를 나누어 올려 주세요."
                    )
                pages.append(text)
            page_count = len(pdf.pages)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            400, "PDF를 읽지 못했습니다. 암호화 또는 파일 손상 여부를 확인하세요."
        )

    text = "\n\n".join(pages).strip()
    if not text:
        raise HTTPException(
            422, "추출할 글자가 없습니다. 스캔 PDF는 별도 OCR 처리가 필요합니다."
        )
    return {"text": text, "pages": page_count}

def validate_signature(value):
    prefix = "data:image/png;base64,"
    if value.startswith(prefix):
        value = value[len(prefix):]

    try:
        raw = base64.b64decode(value, validate=True)
        if not raw or len(raw) > 500000:
            raise ValueError()

        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "PNG":
                raise ValueError()
            if not (100 <= image.width <= 1600 and 50 <= image.height <= 800):
                raise ValueError()
            image.load()
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            rgb = Image.alpha_composite(background, rgba).convert("RGB")
            # 빈 캔버스에 가까운 이미지는 거절합니다.
            dark_pixels = sum(
                1 for r, g, b in rgb.getdata()
                if min(r, g, b) < 180
            )
            if dark_pixels < 30:
                raise ValueError()
            output = io.BytesIO()
            rgb.save(output, format="PNG")
    except (
        ValueError, binascii.Error, UnidentifiedImageError,
        OSError, Image.DecompressionBombError
    ):
        raise HTTPException(
            400, "서명을 확인할 수 없습니다. 흰 배경의 PNG 서명을 다시 제출하세요."
        )
    return base64.b64encode(output.getvalue()).decode("ascii")

@app.post("/api/registry", status_code=201)
def add_registry(body: RegistryInput):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "이름을 입력해 주세요.")

    signature = validate_signature(body.signature)

    with connect() as db:
        training = db.execute(
            "SELECT id FROM trainings WHERE id = ?",
            (body.training_id,),
        ).fetchone()
        if training is None:
            raise HTTPException(404, "해당 연수를 찾을 수 없습니다.")

        cursor = db.execute(
            """
            INSERT INTO registry
              (training_id, department, position, name, signature, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                body.training_id,
                body.department.strip(),
                body.position.strip(),
                name,
                signature,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        record_id = cursor.lastrowid

    return {"id": record_id, "message": "등록했습니다."}

@app.get("/api/registry")
def get_registry(training_id: int):
    if training_id < 1:
        raise HTTPException(400, "연수 번호를 확인해 주세요.")
    with connect() as db:
        # 목록에서는 개인정보 노출과 전송량을 줄이기 위해
        # 서명 이미지 본문을 반환하지 않습니다.
        rows = db.execute(
            """
            SELECT id, training_id, department, position, name, created_at
            FROM registry WHERE training_id = ? ORDER BY id
            """,
            (training_id,),
        ).fetchall()
    return [dict(row) for row in rows]

@app.get("/api/registry/{record_id}/signature")
def get_signature(record_id: int):
    # 공개 운영 시 관리자 권한이 필요한 경로입니다.
    with connect() as db:
        row = db.execute(
            "SELECT signature FROM registry WHERE id = ?",
            (record_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "등록 기록이 없습니다.")
    return {"signature": "data:image/png;base64," + row["signature"]}
`;

  const migrationCode = String.raw`# 기존 파일을 읽어 새 데이터베이스에 한 번만 옮기는 스크립트입니다.
# 원본 training_data.json, registry.csv는 수정하지 않습니다.
# classroom_api.py와 같은 폴더에 저장한 뒤 실행하세요.

import base64
import csv
import json
import sqlite3
from pathlib import Path

from classroom_api import DB_PATH, initialize

ROOT = Path(__file__).resolve().parent
initialize()

with sqlite3.connect(DB_PATH) as db:
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            name TEXT PRIMARY KEY
        )
    """)
    if db.execute(
        "SELECT 1 FROM migrations WHERE name = ?",
        ("legacy-files-v1",)
    ).fetchone():
        raise SystemExit("이미 이전을 완료했습니다. 중복 실행을 중단합니다.")

    def ensure_training(title, date="", location=""):
        db.execute(
            "INSERT OR IGNORE INTO trainings (title, date, location) VALUES (?, ?, ?)",
            (title, date, location),
        )
        return db.execute(
            "SELECT id FROM trainings WHERE title = ?", (title,)
        ).fetchone()[0]

    training_file = ROOT / "training_data.json"
    registry_file = ROOT / "registry.csv"

    if not training_file.exists() and not registry_file.exists():
        raise SystemExit("이전할 파일이 없습니다. 기존 파일을 같은 폴더에 복사하세요.")

    if training_file.exists():
        data = json.loads(training_file.read_text(encoding="utf-8"))
        for title, detail in data.items():
            ensure_training(
                title, detail.get("date", ""), detail.get("loc", "")
            )

    count = 0
    if registry_file.exists():
        with registry_file.open(encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                title = row.get("연수명", "").strip()
                name = row.get("이름", "").strip()
                if not title or not name:
                    raise ValueError("연수명 또는 이름이 없는 행이 있습니다.")

                signature = row.get("서명 이미지", "")
                if signature:
                    base64.b64decode(signature, validate=True)

                training_id = ensure_training(
                    title, row.get("일시", ""), row.get("장소", "")
                )
                db.execute(
                    """
                    INSERT INTO registry
                      (training_id, department, position, name, signature, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        training_id,
                        row.get("소속", ""),
                        row.get("직위", ""),
                        name,
                        signature,
                        row.get("등록 일시", ""),
                    ),
                )
                count += 1

    db.execute(
        "INSERT INTO migrations (name) VALUES (?)",
        ("legacy-files-v1",),
    )

print(f"이전을 완료했습니다. 등록 기록 {count}건")
`;

  const streamlitCode = String.raw`# 기존 Streamlit 파일에 통합할 연결 함수입니다.
# 기존 set_page_config 호출은 그대로 하나만 유지하세요.
import requests
import streamlit as st

CLASSROOM_API = "http://127.0.0.1:8001"

def classroom_request(method, path, **kwargs):
    try:
        response = requests.request(
            method,
            CLASSROOM_API + path,
            timeout=(5, 90),
            **kwargs
        )
        if not response.ok:
            try:
                detail = response.json().get("detail", "요청에 실패했습니다.")
            except ValueError:
                detail = "서버 응답을 읽지 못했습니다."
            raise RuntimeError(str(detail))
        return response.json()
    except requests.RequestException as error:
        raise RuntimeError(
            "추가 기능 서버에 연결하지 못했습니다. 8001번 서버를 확인하세요."
        ) from error

# 1. 기존 load_training_data() 대신 API 조회
try:
    trainings = classroom_request("GET", "/api/trainings")
except RuntimeError as error:
    st.error(str(error))
    st.stop()

if not trainings:
    st.info("먼저 API에 연수를 등록해 주세요.")
else:
    selected = st.selectbox(
        "연수 선택",
        trainings,
        format_func=lambda item: item["title"],
    )

    # 2. 기존 load_registry() 대신 선택 연수의 기록 조회
    try:
        records = classroom_request(
            "GET",
            "/api/registry",
            params={"training_id": selected["id"]},
        )
        st.dataframe(records, use_container_width=True)
    except RuntimeError as error:
        st.error(str(error))

# 3. 기존 연수 추가 버튼에서 호출
# classroom_request("POST", "/api/trainings", json={
#     "title": new_title,
#     "date": new_date,
#     "location": new_loc,
# })

# 4. 기존 서명 처리에서 만든 sig_base64를 API에 저장
# 기존 save_registry(df)를 함께 호출하지 마세요.
#
# classroom_request("POST", "/api/registry", json={
#     "training_id": selected["id"],
#     "department": in_dept,
#     "position": in_pos,
#     "name": in_name,
#     "signature": sig_base64,
# })
# st.rerun()

# 5. 기존 PDF 업로더의 uploaded_file을 API로 전달
#
# result = classroom_request(
#     "POST",
#     "/api/pdf-text",
#     files={
#         "file": (
#             uploaded_file.name,
#             uploaded_file.getvalue(),
#             "application/pdf",
#         )
#     },
# )
# st.session_state.extracted_text = result["text"]
#
# 이후 기존 Gemini 분석 프롬프트에 extracted_text를 사용하세요.
`;

  const reactCode = String.raw`// 기존 HTML의 text/babel 안, App 바깥에 추가할 연결 함수입니다.
// 기존 apiBase는 Gemini용 8000번 서버이므로 바꾸지 않습니다.
const CLASSROOM_API = "http://127.0.0.1:8001";

async function classroomRequest(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(CLASSROOM_API + path, {
      ...options,
      signal: controller.signal,
    });
    let result;
    try {
      result = await response.json();
    } catch {
      throw new Error("서버 응답 형식을 확인해 주세요.");
    }
    if (!response.ok) {
      throw new Error(
        typeof result.detail === "string"
          ? result.detail
          : "요청 내용을 확인해 주세요."
      );
    }
    return result;
  } finally {
    clearTimeout(timer);
  }
}

function createTraining(title, date, location) {
  return classroomRequest("/api/trainings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, date, location }),
  });
}

function loadTrainings() {
  return classroomRequest("/api/trainings");
}

function loadRegistry(trainingId) {
  return classroomRequest(
    "/api/registry?training_id=" + encodeURIComponent(trainingId)
  );
}

function uploadPdf(file) {
  const form = new FormData();
  form.append("file", file);
  // FormData에서는 Content-Type을 직접 지정하지 않습니다.
  return classroomRequest("/api/pdf-text", {
    method: "POST",
    body: form,
  });
}

function submitSignature(trainingId, department, position, name, canvas) {
  return classroomRequest("/api/registry", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      training_id: trainingId,
      department,
      position,
      name,
      signature: canvas.toDataURL("image/png"),
    }),
  });
}

// App 내부의 이벤트 핸들러에서 호출하는 예:
// try {
//   const result = await uploadPdf(selectedFile);
//   setDraft(result.text);
//   setToast(result.pages + "쪽의 텍스트를 추출했습니다.");
// } catch (error) {
//   setToast(error.message);
// }
//
// 주의:
// submitSignature 함수는 서명판 UI를 만들지 않습니다.
// canvas ref와 포인터 이벤트를 가진 서명 컴포넌트가 별도로 필요합니다.
// 제출 중에는 버튼을 비활성화하여 중복 제출을 막으세요.
`;

  const signatureCode = String.raw`// 기존 React 코드와 같은 text/babel 안에 추가하세요.
// React.useRef 등을 직접 사용하므로 별도 훅 import가 필요하지 않습니다.

function SignaturePad({ onSubmit }) {
  const canvasRef = React.useRef(null);
  const drawingRef = React.useRef(false);
  const lastRef = React.useRef(null);
  const hasInkRef = React.useRef(false);
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState("");

  function clear() {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    hasInkRef.current = false;
    setMessage("");
  }

  React.useEffect(() => {
    clear();
  }, []);

  function point(event) {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * canvas.width / rect.width,
      y: (event.clientY - rect.top) * canvas.height / rect.height,
    };
  }

  function start(event) {
    if (busy) return;
    if (event.pointerType === "mouse" && event.button !== 0) return;
    const canvas = canvasRef.current;
    canvas.setPointerCapture(event.pointerId);
    drawingRef.current = true;
    lastRef.current = point(event);
  }

  function move(event) {
    if (!drawingRef.current || busy) return;
    const next = point(event);
    const ctx = canvasRef.current.getContext("2d");
    ctx.strokeStyle = "#262635";
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(lastRef.current.x, lastRef.current.y);
    ctx.lineTo(next.x, next.y);
    ctx.stroke();
    lastRef.current = next;
    hasInkRef.current = true;
  }

  function stop() {
    drawingRef.current = false;
    lastRef.current = null;
  }

  async function submit() {
    if (!hasInkRef.current) {
      setMessage("서명을 먼저 작성해 주세요.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      await onSubmit(canvasRef.current);
      clear();
      setMessage("서명을 등록했습니다.");
    } catch (error) {
      setMessage(error.message || "등록에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <p id="signature-help" className="text-sm text-slate-600">
        마우스나 손가락으로 서명해 주세요.
        캔버스 입력이 어려운 경우 담당자에게 대체 등록을 요청하세요.
      </p>
      <canvas
        ref={canvasRef}
        width={600}
        height={180}
        aria-label="서명 입력 영역"
        aria-describedby="signature-help"
        className="w-full touch-none rounded-xl border border-slate-300 bg-white"
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={stop}
        onPointerCancel={stop}
        onLostPointerCapture={stop}
      />
      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={clear}
          className="rounded-lg border px-4 py-2 disabled:opacity-50"
        >
          지우기
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="rounded-lg bg-brand px-4 py-2 text-white disabled:opacity-50"
        >
          {busy ? "등록 중…" : "서명 제출"}
        </button>
      </div>
      <p role="status" className="text-sm text-slate-600">{message}</p>
    </div>
  );
}

// 온라인 등록부 화면에 배치하는 예:
// selectedTraining은 API에서 조회한 연수 객체입니다.
// department, position, name은 폼 입력 상태입니다.
//
// <SignaturePad onSubmit={async canvas => {
//   await submitSignature(
//     selectedTraining.id, department, position, name, canvas
//   );
//   const records = await loadRegistry(selectedTraining.id);
//   setRegistry(records);
// }} />
`;

  const commands = String.raw`# 1. 추가 패키지 설치
python -m pip install fastapi uvicorn python-multipart pdfplumber pillow requests

# 2. 기존 파일 이전 — 서버 실행 전 한 번만 실행
# training_data.json, registry.csv를 같은 폴더에 복사한 경우에만 실행
python migrate_legacy.py

# 3. 추가 API 서버 실행
python -m uvicorn classroom_api:app --host 127.0.0.1 --port 8001

# 기존 AI 서버(8000번)와 Streamlit은 다른 터미널에서 계속 실행합니다.
`;

  const tabs = [
    { id: "overview", label: "연결 구조", icon: Layers },
    { id: "server", label: "공유 API 서버", icon: Database },
    { id: "streamlit", label: "Streamlit 연결", icon: Cloud },
    { id: "react", label: "React 연결", icon: Code2 },
    { id: "migration", label: "데이터 이전", icon: File }
  ];

  function downloadFile(filename, content) {
    const url = URL.createObjectURL(
      new Blob([content], { type: "text/plain;charset=utf-8" })
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  function CodeBlock({ title, code, filename, notify }) {
    async function copy() {
      try {
        await navigator.clipboard.writeText(code);
        notify("복사했습니다.");
      } catch {
        notify("복사 권한이 없습니다. 다운로드를 이용해 주세요.");
      }
    }
    return (
      <section className="min-w-0 overflow-hidden rounded-xl border border-line">
        <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 px-4 py-3">
          <h3 className="text-sm font-semibold">{title}</h3>
          <div className="flex gap-3">
            <button onClick={copy} className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-brand">
              <Copy className="h-3.5 w-3.5" aria-hidden="true" />복사
            </button>
            {filename && (
              <button onClick={() => downloadFile(filename, code)} className="flex items-center gap-1.5 text-xs font-medium text-brand">
                <Download className="h-3.5 w-3.5" aria-hidden="true" />다운로드
              </button>
            )}
          </div>
        </div>
        <pre className="max-h-[520px] overflow-auto bg-[#252536] p-5 text-xs leading-6 text-slate-100">
          <code>{code}</code>
        </pre>
      </section>
    );
  }

  function Callout({ title, children, warning = false }) {
    return (
      <div className={`flex gap-3 rounded-xl border p-4 ${warning ? "border-amber-200 bg-amber-50" : "border-violet-100 bg-violet-50"}`}>
        {warning
          ? <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" aria-hidden="true" />
          : <Info className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />}
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">{title}</h3>
          <div className="mt-2 text-sm leading-7 text-slate-600">{children}</div>
        </div>
      </div>
    );
  }

  function App() {
    const [active, setActive] = useState("overview");
    const [toast, setToast] = useState("");

    useEffect(() => {
      if (!toast) return;
      const timer = setTimeout(() => setToast(""), 3000);
      return () => clearTimeout(timer);
    }, [toast]);

    const codeProps = { notify: setToast };

    return (
      <div>
        <header className="border-b border-line bg-white">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-5 md:px-8">
            <a href="#main" className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-white">
                <Layers className="h-5 w-5" aria-hidden="true" />
              </span>
              <span>
                <span className="block text-lg font-bold">교무실<span className="text-brand">.</span></span>
                <span className="text-xs text-slate-500">추가 기능 연동 안내</span>
              </span>
            </a>
            <span className="rounded-full border border-line bg-paper px-3 py-1.5 text-xs text-slate-600">
              기존 앱과 별도로 보는 안내 문서
            </span>
          </div>
        </header>

        <main id="main" className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-14">
          <div className="mb-8 max-w-3xl">
            <p className="mb-3 text-xs font-semibold tracking-wide text-brand">Streamlit · React · FastAPI</p>
            <h1 className="text-3xl font-bold leading-tight tracking-tight md:text-4xl">
              화면은 둘이어도,<br className="sm:hidden" /> 데이터는 하나로.
            </h1>
            <p className="mt-4 text-sm leading-8 text-slate-500 md:text-base">
              PDF 텍스트 추출과 전자서명은 서버 기능으로 분리하고,
              연수·등록부는 같은 데이터베이스에 저장합니다.
              기존 AI 서버와 업무 화면을 통째로 바꿀 필요는 없습니다.
            </p>
          </div>

          <div className="grid items-start gap-6 lg:grid-cols-[210px_minmax(0,1fr)]">
            <nav className="flex flex-wrap gap-2 lg:sticky lg:top-6 lg:flex-col" aria-label="연동 안내">
              {tabs.map((tab, index) => (
                <button
                  key={tab.id}
                  onClick={() => setActive(tab.id)}
                  aria-pressed={active === tab.id}
                  className={`flex items-center gap-3 rounded-xl px-4 py-3 text-left text-sm ${active === tab.id ? "bg-brand font-semibold text-white" : "border border-line bg-white text-slate-600 hover:bg-slate-50"}`}
                >
                  <tab.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>{index + 1}. {tab.label}</span>
                </button>
              ))}
            </nav>

            <article className="min-w-0 rounded-2xl border border-line bg-white p-5 md:p-7">
              {active === "overview" && (
                <div className="space-y-7">
                  <div>
                    <h2 className="text-xl font-bold">무엇을 어디에 연결하나요?</h2>
                    <p className="mt-2 text-sm leading-7 text-slate-500">
                      기존 코드에서 별도 연동이 필요한 세 부분을 나누면 다음과 같습니다.
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-3">
                    {[
                      ["PDF 분석", "PDF 업로드 → 글자 추출 → 기존 AI 생성 요청"],
                      ["전자서명", "서명판 → PNG 이미지 → 등록부 API 저장"],
                      ["데이터 공유", "React·Streamlit → 같은 API → SQLite"]
                    ].map(([title, text]) => (
                      <div key={title} className="rounded-xl border border-line bg-paper p-4">
                        <h3 className="text-sm font-semibold">{title}</h3>
                        <p className="mt-2 text-xs leading-6 text-slate-500">{text}</p>
                      </div>
                    ))}
                  </div>

                  <section className="rounded-xl border border-line p-5">
                    <h3 className="mb-4 text-sm font-semibold">서버 역할을 분리합니다</h3>
                    <div className="space-y-3">
                      {[
                        ["8000번", "기존 AI 서버", "Gemini 초안 생성과 HTML 제공"],
                        ["8001번", "추가 기능 서버", "PDF 추출·연수·등록부·서명 저장"],
                        ["8501번", "기존 Streamlit", "Python 업무 화면"]
                      ].map(([port, title, text]) => (
                        <div key={port} className="flex flex-wrap items-center gap-3 rounded-lg bg-paper p-3">
                          <span className="rounded bg-white px-2 py-1 text-xs font-semibold text-brand">{port}</span>
                          <div className="flex-1">
                            <p className="text-sm font-medium">{title}</p>
                            <p className="mt-1 text-xs text-slate-500">{text}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>

                  <Callout title="핵심은 저장 경로를 하나로 바꾸는 것입니다">
                    기존 Streamlit의 <code>save_registry()</code>와 React의
                    브라우저 저장을 그대로 둔 채 서버만 추가하면 데이터는 공유되지 않습니다.
                    연수·등록부 화면의 조회와 저장을 양쪽 모두 API 호출로 바꿔야 합니다.
                    할 일·출결·상담 메모는 이번 서버 예제의 연결 범위에 포함하지 않았습니다.
                  </Callout>

                  <div>
                    <h3 className="mb-3 text-sm font-semibold">권장 적용 순서</h3>
                    <ol className="space-y-3">
                      {[
                        "원본 Python 파일과 JSON·CSV를 먼저 백업합니다.",
                        "공유 API 파일을 저장하고 기존 데이터를 한 번 이전합니다.",
                        "8001번 서버를 실행해 /docs에서 API를 확인합니다.",
                        "Streamlit 등록부를 API 조회·저장 방식으로 바꿉니다.",
                        "React 등록부와 PDF 업로드·서명 UI를 연결합니다."
                      ].map((text, i) => (
                        <li key={text} className="flex gap-3 text-sm leading-7 text-slate-600">
                          <span className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-50 text-xs font-semibold text-brand">{i + 1}</span>
                          {text}
                        </li>
                      ))}
                    </ol>
                  </div>
                  <button onClick={() => setActive("server")} className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2.5 text-sm font-medium text-white">
                    서버 코드부터 보기<ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              )}

              {active === "server" && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-xl font-bold">추가 기능 API 서버</h2>
                    <p className="mt-2 text-sm leading-7 text-slate-500">
                      기존 backend.py는 그대로 두고, 아래 파일을
                      classroom_api.py라는 이름으로 같은 프로젝트 폴더에 저장하세요.
                      데이터는 이 파일 옆의 classroom.db에 저장됩니다.
                    </p>
                  </div>
                  <Callout title="개인 컴퓨터에서만 실행하는 예제입니다" warning>
                    로그인·권한 확인이 없는 로컬 개발용입니다.
                    반드시 127.0.0.1에 바인딩하고 인터넷에 직접 공개하지 마세요.
                    서명 이미지는 암호학적 전자서명이나 본인 인증을 제공하지 않습니다.
                  </Callout>
                  <CodeBlock title="classroom_api.py · 전체 서버 코드" code={backendCode} filename="classroom_api.py" {...codeProps} />
                  <CodeBlock title="설치·실행 명령" code={commands} filename="실행_안내.txt" {...codeProps} />
                  <div className="rounded-xl border border-line p-4">
                    <h3 className="text-sm font-semibold">실행 후 확인할 주소</h3>
                    <a href="http://127.0.0.1:8001/docs" target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-2 break-all text-sm text-brand underline">
                      http://127.0.0.1:8001/docs<ChevronRight className="h-4 w-4 shrink-0" aria-hidden="true" />
                    </a>
                    <p className="mt-3 text-xs leading-6 text-slate-500">
                      이 안내 페이지가 서버를 실행하지는 않습니다. Python 파일을 저장하고 터미널에서 실행해야 합니다.
                      API 문서에서 연수를 하나 등록한 뒤 등록부 조회와 PDF 업로드를 확인하세요.
                    </p>
                  </div>
                  <Callout title="PDF 추출과 AI 분석은 서로 다른 단계입니다">
                    이 API는 글자만 추출합니다. 결과의 text를 기존 8000번 서버의
                    /api/generate에 보내야 AI 분석이 됩니다.
                    기존 생성 API의 입력 제한은 20,000자이므로 긴 PDF는 단원별로
                    나누거나 분할 요약 기능을 추가해야 합니다. 스캔 PDF는 별도 OCR이 필요합니다.
                  </Callout>
                </div>
              )}

              {active === "streamlit" && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-xl font-bold">기존 Streamlit에서 호출하기</h2>
                    <p className="mt-2 text-sm leading-7 text-slate-500">
                      requests로 같은 API를 호출합니다. 기존 전체 파일을 아래 코드로
                      덮어쓰지 말고, 연결 함수와 각 버튼의 저장 부분을 통합하세요.
                    </p>
                  </div>
                  <CodeBlock title="Streamlit 연결 함수와 적용 위치" code={streamlitCode} filename="streamlit_api_example.py" {...codeProps} />
                  <section className="space-y-3 rounded-xl border border-line p-5">
                    <h3 className="text-sm font-semibold">기존 코드에서 바꿀 부분</h3>
                    {[
                      ["load_training_data()", "GET /api/trainings로 교체"],
                      ["save_training_data()", "POST /api/trainings로 교체"],
                      ["load_registry()", "GET /api/registry로 교체"],
                      ["save_registry(df)", "POST /api/registry로 교체"],
                      ["pdfplumber.open(...)", "POST /api/pdf-text로 교체 가능"]
                    ].map(([before, after]) => (
                      <div key={before} className="flex flex-wrap items-center gap-2 border-t border-line pt-3 text-xs">
                        <code className="text-slate-600">{before}</code>
                        <ArrowRight className="h-3 w-3 text-slate-400" aria-hidden="true" />
                        <span className="font-medium text-brand">{after}</span>
                      </div>
                    ))}
                  </section>
                  <Callout title="session_state에 최초 한 번만 불러오면 최신 자료가 보이지 않습니다">
                    React에서 추가된 기록을 확인하려면 조회할 때 API를 다시 호출하거나
                    새로고침 버튼을 제공하세요. 오래된 session_state의 데이터프레임을
                    서버에 통째로 다시 저장하면 다른 화면에서 추가한 자료를 덮어쓸 수 있습니다.
                  </Callout>
                  <p className="text-sm leading-7 text-slate-600">
                    기존 CSV 다운로드는 API에서 받은 목록으로 데이터프레임을 만들면 됩니다.
                    서명 포함 인쇄에는 각 기록의
                    <code className="mx-1 break-all">/api/registry/기록번호/signature</code>
                    응답을 추가로 사용하세요. 제공 예제의 서명 조회에는 권한 검사가 없으므로 공개 배포하면 안 됩니다.
                  </p>
                </div>
              )}

              {active === "react" && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-xl font-bold">기존 React 화면에서 호출하기</h2>
                    <p className="mt-2 text-sm leading-7 text-slate-500">
                      기존 8000번 AI 서버 주소는 바꾸지 않습니다.
                      추가 기능 호출에만 8001번 주소를 사용하세요.
                    </p>
                  </div>
                  <CodeBlock title="API 연결 함수 · 기존 text/babel 안에 추가" code={reactCode} filename="classroom_api_helpers.jsx" {...codeProps} />
                  <CodeBlock title="마우스·터치 서명 입력 컴포넌트" code={signatureCode} filename="SignaturePad.jsx" {...codeProps} />
                  <Callout title="이 코드는 연결 부품이지 기존 앱 전체를 교체하는 파일이 아닙니다">
                    연수 선택 상태, 이름·소속 입력 상태, 등록부 목록 상태를 기존 App 안에
                    만들고 연결해야 합니다. 현재 ‘온라인 등록부’의 CSV 양식 다운로드 영역을
                    연수 선택·입력 폼·SignaturePad·등록 목록으로 바꾸는 작업이 필요합니다.
                  </Callout>
                  <section className="rounded-xl border border-line p-5">
                    <h3 className="mb-3 text-sm font-semibold">React 화면 연결 순서</h3>
                    <ol className="list-decimal space-y-2 pl-5 text-sm leading-7 text-slate-600">
                      <li>등록부 메뉴 진입 시 loadTrainings()로 연수 목록을 가져옵니다.</li>
                      <li>연수 선택 시 loadRegistry(연수번호)로 등록 목록을 표시합니다.</li>
                      <li>이름·소속·직위를 입력하고 SignaturePad에서 서명합니다.</li>
                      <li>저장 성공 후에만 입력 내용을 정리하고 목록을 다시 조회합니다.</li>
                      <li>PDF는 파일 입력으로 선택한 File 객체를 uploadPdf()에 전달합니다.</li>
                    </ol>
                  </section>
                  <Callout title="HTML 파일을 더블클릭해서 열지 마세요" warning>
                    기존 서버의 http://127.0.0.1:8000/app에서 여세요.
                    file:// 출처는 예제의 CORS 허용 대상이 아닙니다.
                    다른 개발 포트를 사용한다면 classroom_api.py의 허용 출처에
                    실제 주소를 정확히 추가해야 합니다.
                  </Callout>
                </div>
              )}

              {active === "migration" && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-xl font-bold">기존 JSON·CSV를 한 번만 이전하기</h2>
                    <p className="mt-2 text-sm leading-7 text-slate-500">
                      새 서버는 SQLite를 사용합니다. 기존 파일은 자동 연결되지 않으므로
                      아래 스크립트로 이전한 뒤 API 저장 방식으로 전환하세요.
                    </p>
                  </div>
                  <Callout title="이전 전에 원본 파일을 백업하세요" warning>
                    기존 Streamlit과 추가 API 서버를 멈추고 진행하세요.
                    training_data.json과 registry.csv를 classroom_api.py 옆에 복사합니다.
                    스크립트는 원본 파일을 수정하지 않으며 완료 여부를 기록해 중복 실행을 막습니다.
                  </Callout>
                  <CodeBlock title="migrate_legacy.py · 일회성 이전 스크립트" code={migrationCode} filename="migrate_legacy.py" {...codeProps} />
                  <CodeBlock title="이전 실행" code={"python migrate_legacy.py"} {...codeProps} />
                  <section className="rounded-xl border border-line p-5">
                    <h3 className="mb-4 text-sm font-semibold">전환 완료 확인</h3>
                    <ul className="space-y-3">
                      {[
                        "기존 연수명과 등록 건수가 API 조회 결과와 같은지 확인합니다.",
                        "Streamlit에서 추가한 기록이 React에서도 조회되는지 확인합니다.",
                        "React에서 등록한 서명이 Streamlit 인쇄에 표시되는지 확인합니다.",
                        "기존 CSV·JSON 쓰기 함수는 더 이상 호출하지 않습니다.",
                        "브라우저 할 일·출결 데이터는 여전히 별도라는 점을 구분합니다."
                      ].map(text => (
                        <li key={text} className="flex gap-2 text-sm leading-7 text-slate-600">
                          <CheckCircle className="mt-1.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />{text}
                        </li>
                      ))}
                    </ul>
                  </section>
                  <Callout title="여러 선생님이 함께 사용하려면 추가 설계가 필요합니다">
                    이 예제는 개인용입니다. 실제 배포에서는 HTTPS, 로그인, 학급별 접근 권한,
                    관리자 전용 등록부 조회, 파일 처리 제한, 백업·보존·삭제 정책이 필요합니다.
                    서버가 여러 대이거나 저장 공간이 초기화되는 환경에서는 로컬 SQLite 대신
                    PostgreSQL 같은 영속 저장소를 권장합니다.
                    Streamlit Community Cloud에 FastAPI가 함께 자동 실행되는 것은 아닙니다.
                  </Callout>
                </div>
              )}
            </article>
          </div>

          <footer className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5 text-xs text-slate-500">
            <span>교무실 · 추가 기능 연동 안내</span>
            <span className="flex items-center gap-1.5">
              <Lock className="h-3.5 w-3.5" aria-hidden="true" />
              실제 학생 자료 연결 전 접근 권한부터 확인하세요
            </span>
          </footer>
        </main>

        <div aria-live="polite" className="pointer-events-none fixed bottom-5 left-1/2 z-50 max-w-[90vw] -translate-x-1/2">
          {toast && (
            <div className="flex items-center gap-2 rounded-xl bg-ink px-5 py-3 text-sm text-white shadow-lg">
              <Check className="h-4 w-4 shrink-0" aria-hidden="true" />{toast}
            </div>
          )}
        </div>
      </div>
    );
  }

  ReactDOM.createRoot(document.getElementById("root")).render(<App />);
</script>
</body>
</html>
