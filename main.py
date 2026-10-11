from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pathlib import Path
from pydantic import BaseModel, EmailStr, Field
from typing import Any, Optional, List
import csv
import hashlib
import io
import json
import os
import uuid

from auth import create_access_token, get_current_user, hash_password, public_user, require_admin, verify_password
from mongo_store import get_store
from pipeline import generate_pipeline
from question_bank import QuestionBank, QuestionStatus
from execution_engine import verify_in_sandbox

app = FastAPI(
    title="SQLArena AI Question Generator",
    description="7-step AI pipeline for SQL question generation",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApiPrefixMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/api"):
            scope = dict(scope)
            scope["path"] = scope["path"][4:] or "/"
        await self.app(scope, receive, send)


app.add_middleware(ApiPrefixMiddleware)

_STATIC_DIR = Path(__file__).parent / "static"
_FRONTEND_DIR = Path(__file__).parent / "dist"
_LEGACY_FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"
_ASSET_DIR = next((path for path in (_FRONTEND_DIR, _LEGACY_FRONTEND_DIR, _STATIC_DIR) if path.is_dir()), _STATIC_DIR)


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(_ASSET_DIR / "index.html")


def _serve_asset(asset_root: Path, asset_path: str):
    asset = (asset_root / asset_path).resolve()
    if asset_root not in asset.parents or not asset.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(asset)


@app.get("/assets/{asset_path:path}", include_in_schema=False)
def frontend_asset(asset_path: str):
    return _serve_asset(_ASSET_DIR, "assets/" + asset_path)


@app.get("/static/{asset_path:path}", include_in_schema=False)
def static_asset(asset_path: str):
    return _serve_asset(_STATIC_DIR, asset_path)


# ---------------------------------------------------------------------------
# In-memory task registry (single-process; đủ cho dev/demo scope)
# ---------------------------------------------------------------------------
_tasks: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    specs: List[str] = Field(default=["easy", "medium", "hard"])
    questions_per_spec: int = Field(default=1, ge=1, le=10)
    excel_id: Optional[str] = None


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|archived)$")
    review_notes: str = ""


class VerifyRequest(BaseModel):
    ddl_sql: str
    seed_sql: str
    answer_sql: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=200)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=200)


class GenerationJobRequest(BaseModel):
    specs: List[str] = Field(default=["easy", "medium", "hard"])
    questions_per_spec: int = Field(default=1, ge=1, le=10)
    excel_id: Optional[str] = None


class UserUpdateRequest(BaseModel):
    role: Optional[str] = Field(default=None, pattern="^(learner|admin)$")
    status: Optional[str] = Field(default=None, pattern="^(active|locked)$")


# ---------------------------------------------------------------------------
# Background task runner


def _learner_question(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": question.get("id"),
        "question_text": question.get("question_text", ""),
        "difficulty": question.get("difficulty"),
        "topic": question.get("topic"),
        "status": question.get("status"),
    }


def _safe_login_response(user: dict[str, Any]) -> dict[str, Any]:
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": public_user(user)}


def _document_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".md", ".txt", ".json", ".csv"}:
        return content.decode("utf-8-sig")
    if suffix == ".xlsx":
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        rows = []
        for sheet in workbook.worksheets:
            rows.append(f"# {sheet.title}")
            rows.extend(" | ".join("" if cell is None else str(cell) for cell in row) for row in sheet.iter_rows(values_only=True))
        return "\\n".join(rows)
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF upload requires pypdf dependency") from exc
        return "\\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    raise ValueError("Supported files: .csv, .xlsx, .json, .md, .txt, .pdf")


def _seed_questions_from_document(filename: str, text: str) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        parsed = json.loads(text)
        items = parsed if isinstance(parsed, list) else parsed.get("questions", [])
        return [item for item in items if isinstance(item, dict) and item.get("question_text")]
    if suffix == ".csv":
        return [{"question_text": row.get("question_text", ""), "difficulty": row.get("difficulty", "medium"), "topic": row.get("topic", "Imported")} for row in csv.DictReader(io.StringIO(text)) if row.get("question_text")]
    return []


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------

def _sync_generated_questions_to_mongo(question_ids: list[str]) -> None:
    qb = QuestionBank()
    store = get_store()
    for question_id in question_ids:
        question = qb.get(question_id)
        if question:
            store.save_question(question)


def _run_generate(
    task_id: str,
    specs: List[str],
    questions_per_spec: int,
    excel_id: Optional[str] = None,
):
    store = get_store()
    try:
        _tasks[task_id]["status"] = "running"
        store.save_job({**_tasks[task_id], "id": task_id, "status": "running"})
        result = generate_pipeline(
            specs=specs,
            questions_per_spec=questions_per_spec,
            excel_id=excel_id,
        )
        _sync_generated_questions_to_mongo(result.get("question_ids", []))
        _tasks[task_id].update({"status": "done", "result": result})
        store.save_job({**_tasks[task_id], "id": task_id})
    except Exception as exc:
        _tasks[task_id].update({"status": "failed", "error": str(exc)})
        store.save_job({**_tasks[task_id], "id": task_id})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    store = get_store()
    return {"status": "ok", "version": "2.0.0", "persistence": store.mode}


@app.post("/auth/register", status_code=201)
def register(req: RegisterRequest):
    store = get_store()
    try:
        user = store.create_user({
            "email": str(req.email),
            "password_hash": hash_password(req.password),
            "role": "learner",
            "status": "active",
        })
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _safe_login_response(user)


@app.post("/auth/login")
def login(req: LoginRequest):
    user = get_store().find_user_by_email(str(req.email))
    if not user or user.get("status", "active") != "active" or not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _safe_login_response(user)


@app.get("/me")
def current_profile(user: dict[str, Any] = Depends(get_current_user)):
    return public_user(user)


@app.post("/generate")
def generate_questions(req: GenerateRequest, background_tasks: BackgroundTasks, _: dict[str, Any] = Depends(require_admin)):
    return create_generation_job(req, background_tasks)


@app.post("/admin/generation-jobs")
def create_generation_job(req: GenerationJobRequest, background_tasks: BackgroundTasks, user: dict[str, Any] = Depends(require_admin)):
    total = len(req.specs) * req.questions_per_spec
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "id": task_id,
        "status": "queued",
        "result": None,
        "error": None,
        "requested_by": user["id"],
        "specs": req.specs,
        "questions_per_spec": req.questions_per_spec,
        "excel_id": req.excel_id,
    }
    get_store().save_job(_tasks[task_id])
    background_tasks.add_task(_run_generate, task_id, req.specs, req.questions_per_spec, req.excel_id)
    return JSONResponse(status_code=202, content={"task_id": task_id, "status": "queued", "message": f"Generating {total} questions. Poll GET /tasks/{task_id}"})


@app.get("/tasks/{task_id}")
def get_task_status(task_id: str, _: dict[str, Any] = Depends(require_admin)):
    task = _tasks.get(task_id) or get_store().job(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/questions")
def list_questions(
    status: Optional[str] = Query(default=None),
    difficulty: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: dict[str, Any] = Depends(get_current_user),
):
    store = get_store()
    visible_status = status if user.get("role") == "admin" else QuestionStatus.APPROVED.value
    questions = store.questions(status=visible_status, difficulty=difficulty, limit=limit)
    if user.get("role") != "admin":
        questions = [_learner_question(question) for question in questions]
    return {"questions": questions, "total": len(questions)}


@app.get("/questions/{question_id}")
def get_question(question_id: str, user: dict[str, Any] = Depends(get_current_user)):
    q = get_store().question(question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")
    if user.get("role") != "admin" and q.get("status") != QuestionStatus.APPROVED.value:
        raise HTTPException(status_code=404, detail="Question not found")
    return q if user.get("role") == "admin" else _learner_question(q)


@app.put("/questions/{question_id}/status")
def update_question_status(question_id: str, req: StatusUpdateRequest, _: dict[str, Any] = Depends(require_admin)):
    store = get_store()
    status_map = {
        "approved": QuestionStatus.APPROVED,
        "rejected": QuestionStatus.REJECTED,
        "archived": QuestionStatus.ARCHIVED,
    }
    new_status = status_map[req.status]
    success = store.update_question_status(question_id, new_status, req.review_notes)
    if not success:
        raise HTTPException(status_code=404, detail="Question not found or update failed")
    return {"success": True}


@app.get("/stats")
def get_stats(_: dict[str, Any] = Depends(require_admin)):
    return get_store().admin_stats()


@app.get("/admin/stats")
def admin_stats(_: dict[str, Any] = Depends(require_admin)):
    return get_store().admin_stats()


@app.get("/admin/users")
def admin_users(_: dict[str, Any] = Depends(require_admin)):
    return {"users": get_store().users(), "total": len(get_store().users())}


@app.patch("/admin/users/{user_id}")
def update_user(user_id: str, req: UserUpdateRequest, current: dict[str, Any] = Depends(require_admin)):
    if user_id == current["id"] and (req.status == "locked" or req.role == "learner"):
        raise HTTPException(status_code=400, detail="Admin cannot lock or demote self")
    store = get_store()
    user = store.user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if req.role:
        user["role"] = req.role
    if req.status:
        user["status"] = req.status
    return public_user(store.save_user(user))


@app.get("/weekly/current")
def weekly_current(user: dict[str, Any] = Depends(get_current_user)):
    store = get_store()
    challenge = store.current_challenge() or {"id": "none", "number": 42, "title": "Thử thách tuần #42", "status": "active"}
    questions = [_learner_question(q) for q in store.challenge_questions(challenge)]
    done = 0
    total = max(len(questions), 8)
    return {"challenge": challenge, "questions": questions, "progress": {"done": done, "total": total, "percent": round(done / total * 100)}}


@app.get("/admin/documents")
def admin_documents(_: dict[str, Any] = Depends(require_admin)):
    return {"documents": get_store().documents(), "total": len(get_store().documents())}


@app.post("/admin/documents")
async def upload_document(file: UploadFile = File(...), user: dict[str, Any] = Depends(require_admin)):
    content = await file.read()
    if len(content) > int(os.getenv("MAX_UPLOAD_BYTES", "5242880")):
        raise HTTPException(status_code=413, detail="File too large")
    checksum = hashlib.sha256(content).hexdigest()
    try:
        text = _document_text(file.filename or "upload", content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    document = get_store().save_document({
        "filename": file.filename,
        "content_type": file.content_type,
        "checksum": checksum,
        "size": len(content),
        "text": text[:20000],
        "preview": text[:500],
        "uploaded_by": user["id"],
    })
    return document


@app.get("/admin/generation-jobs")
def list_generation_jobs(_: dict[str, Any] = Depends(require_admin)):
    return {"jobs": get_store().jobs(), "total": len(get_store().jobs())}


@app.post("/verify-sql")
def verify_sql(req: VerifyRequest, _: dict[str, Any] = Depends(require_admin)):
    try:
        result = verify_in_sandbox(req.ddl_sql, req.seed_sql, req.answer_sql)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
