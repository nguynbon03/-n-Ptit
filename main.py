from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid

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
    allow_origins=["*"],
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


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------

def _run_generate(
    task_id: str,
    specs: List[str],
    questions_per_spec: int,
    excel_id: Optional[str] = None,
):
    try:
        _tasks[task_id]["status"] = "running"
        result = generate_pipeline(
            specs=specs,
            questions_per_spec=questions_per_spec,
            excel_id=excel_id,
        )
        _tasks[task_id].update({"status": "done", "result": result})
    except Exception as exc:
        _tasks[task_id].update({"status": "failed", "error": str(exc)})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/generate")
def generate_questions(req: GenerateRequest, background_tasks: BackgroundTasks):
    total = len(req.specs) * req.questions_per_spec

    if total <= 3:
        # Sync — đủ nhỏ để trả ngay
        try:
            result = generate_pipeline(
                specs=req.specs,
                questions_per_spec=req.questions_per_spec,
                excel_id=req.excel_id,
            )
            return JSONResponse(content={"status": "done", "result": result})
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # Async — chạy background
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {"status": "queued", "result": None, "error": None}
    background_tasks.add_task(
        _run_generate, task_id, req.specs, req.questions_per_spec, req.excel_id
    )
    return JSONResponse(
        status_code=202,
        content={
            "task_id": task_id,
            "status": "running",
            "message": f"Generating {total} questions in background. Poll GET /tasks/{task_id}",
        },
    )


@app.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/questions")
def list_questions(
    status: Optional[str] = Query(default=None),
    difficulty: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    qb = QuestionBank()
    questions = qb.list_questions(status=status, difficulty=difficulty, limit=limit)
    return {"questions": questions, "total": len(questions)}


@app.get("/questions/{question_id}")
def get_question(question_id: str):
    qb = QuestionBank()
    q = qb.get(question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return q


@app.put("/questions/{question_id}/status")
def update_question_status(question_id: str, req: StatusUpdateRequest):
    qb = QuestionBank()
    status_map = {
        "approved": QuestionStatus.APPROVED,
        "rejected": QuestionStatus.REJECTED,
        "archived": QuestionStatus.ARCHIVED,
    }
    new_status = status_map[req.status]
    success = qb.update_status(question_id, new_status, req.review_notes)
    if not success:
        raise HTTPException(status_code=404, detail="Question not found or update failed")
    return {"success": True}


@app.get("/stats")
def get_stats():
    qb = QuestionBank()
    return qb.get_stats()


@app.post("/verify-sql")
def verify_sql(req: VerifyRequest):
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
