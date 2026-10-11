"""MongoDB persistence with an explicit development-only memory fallback."""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_production() -> bool:
    """True when this process must never use the in-memory fallback."""
    if os.getenv("ENV", "").strip().lower() == "production":
        return True
    return os.getenv("VERCEL", "").strip().lower() not in {"", "0", "false"}


_SEED_QUESTIONS = [
    {
        "id": "seed-select-001",
        "question_text": "Liệt kê tên và email người dùng đã đăng ký, sắp xếp theo tên.",
        "difficulty": "easy",
        "topic": "SELECT",
        "status": "approved",
        "valid": True,
        "schema_sql": "CREATE TABLE users (id INTEGER, name TEXT, email TEXT, registered_at TEXT);",
        "seed_sql": "INSERT INTO users VALUES (1, 'An', 'an@example.com', '2026-01-02');",
        "answer_sql": "SELECT name, email FROM users ORDER BY name;",
        "expected_output": [["An", "an@example.com"]],
        "created_at": _now(),
    },
    {
        "id": "seed-group-001",
        "question_text": "Tính số đơn hàng của từng khách hàng và chỉ lấy khách có từ 2 đơn.",
        "difficulty": "medium",
        "topic": "GROUP BY",
        "status": "approved",
        "valid": True,
        "schema_sql": "CREATE TABLE orders (id INTEGER, customer_id INTEGER);",
        "seed_sql": "INSERT INTO orders VALUES (1, 10), (2, 10), (3, 20);",
        "answer_sql": "SELECT customer_id, COUNT(*) AS order_count FROM orders GROUP BY customer_id HAVING COUNT(*) >= 2;",
        "expected_output": [[10, 2]],
        "created_at": _now(),
    },
]


class MongoStore:
    """Small repository used by API routes and CLI tools.

    Memory mode is allowed only for local dev/test when MONGO_URI is absent.
    A configured but unreachable MongoDB never silently becomes the source of
    truth: every read/write raises and `mode` reports `unavailable`. When
    `ENV=production` or `VERCEL` is set, a missing or unreachable URI fails at
    construction time.
    """

    def __init__(self, *, require_connection: bool = False):
        self.uri = os.getenv("MONGO_URI", "").strip()
        self.db_name = os.getenv("MONGO_DB_NAME", "sqlarena").strip() or "sqlarena"
        self.require_connection = require_connection or is_production()
        self._client = None
        self._db = None
        self.error: str | None = None
        self._lock = threading.RLock()
        self.memory: dict[str, list[dict[str, Any]]] = {
            "users": [],
            "questions": [dict(item) for item in _SEED_QUESTIONS],
            "documents": [],
            "settings": [],
            "audit_logs": [],
            "challenges": [
                {
                    "id": "seed-week-42",
                    "number": 42,
                    "title": "Thử thách tuần #42",
                    "status": "active",
                    "starts_at": "2026-10-05T00:00:00+00:00",
                    "ends_at": "2026-10-11T23:59:59+00:00",
                    "question_ids": ["seed-select-001", "seed-group-001"],
                }
            ],
            "jobs": [],
            "submissions": [],
        }
        if self.uri:
            self._connect()
            if not self.connected and self.require_connection:
                raise RuntimeError(f"MongoDB connection required but unavailable: {self.error}")
        elif self.require_connection:
            raise RuntimeError("MONGO_URI is required when ENV=production or VERCEL is set")

    def _connect(self) -> None:
        try:
            from pymongo import MongoClient

            self._client = MongoClient(self.uri, serverSelectionTimeoutMS=2500)
            self._client.admin.command("ping")
            self._db = self._client[self.db_name]
            self._ensure_indexes()
        except Exception as exc:
            self.error = f"MongoDB unavailable: {exc.__class__.__name__}"
            self._client = None
            self._db = None

    @property
    def connected(self) -> bool:
        return self._db is not None

    @property
    def mode(self) -> str:
        if self.connected:
            return "mongo"
        return "unavailable" if self.uri else "memory"

    def _ensure_indexes(self) -> None:
        assert self._db is not None
        self._db.users.create_index("email", unique=True)
        self._db.users.create_index("id", unique=True)
        self._db.questions.create_index("id", unique=True)
        self._db.questions.create_index([("status", 1), ("difficulty", 1), ("topic", 1), ("created_at", -1)])
        self._db.documents.create_index("checksum", unique=True)
        self._db.documents.create_index("id", unique=True)
        self._db.challenges.create_index([("status", 1), ("starts_at", -1)])
        self._db.jobs.create_index("id", unique=True)
        self._db.jobs.create_index([("status", 1), ("created_at", -1)])
        self._db.audit_logs.create_index([("actor_id", 1), ("created_at", -1)])
        self._db.audit_logs.create_index([("resource_type", 1), ("resource_id", 1), ("created_at", -1)])
        self._db.settings.create_index("key", unique=True)
        self._db.submissions.create_index([("user_id", 1), ("created_at", -1)])
        self._db.submissions.create_index([("question_id", 1), ("created_at", -1)])

    @staticmethod
    def _without_id(item: dict[str, Any] | None) -> dict[str, Any] | None:
        if item is None:
            return None
        item.pop("_id", None)
        return item

    def _collection(self, name: str):
        if self._db is None:
            if self.uri:
                raise RuntimeError(self.error or "MongoDB unavailable")
            return None
        return self._db[name]

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        email = email.strip().lower()
        collection = self._collection("users")
        if collection is not None:
            return self._without_id(collection.find_one({"email": email}))
        with self._lock:
            return next((dict(x) for x in self.memory["users"] if x.get("email") == email), None)

    def users(self, limit: int = 200) -> list[dict[str, Any]]:
        collection = self._collection("users")
        if collection is not None:
            return [self._without_id(x) for x in collection.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(limit)]
        with self._lock:
            return [{k: v for k, v in x.items() if k != "password_hash"} for x in self.memory["users"][-limit:]][::-1]

    def user_by_id(self, user_id: str) -> dict[str, Any] | None:
        collection = self._collection("users")
        if collection is not None:
            return self._without_id(collection.find_one({"id": user_id}, {"_id": 0}))
        with self._lock:
            return next((dict(x) for x in self.memory["users"] if x.get("id") == user_id), None)

    def save_user(self, user: dict[str, Any]) -> dict[str, Any]:
        item = {**user, "email": user["email"].strip().lower()}
        if not item.get("id"):
            item["id"] = str(uuid.uuid4())
        item.setdefault("created_at", _now())
        collection = self._collection("users")
        if collection is not None:
            collection.replace_one({"id": item["id"]}, item, upsert=True)
        else:
            with self._lock:
                self.memory["users"] = [x for x in self.memory["users"] if x.get("id") != item["id"]]
                self.memory["users"].append(dict(item))
        return dict(item)

    def create_user(self, user: dict[str, Any]) -> dict[str, Any]:
        item = {**user, "email": user["email"].strip().lower(), "id": str(uuid.uuid4()), "created_at": _now()}
        collection = self._collection("users")
        if collection is not None:
            try:
                collection.insert_one(dict(item))
            except Exception as exc:
                if exc.__class__.__name__ == "DuplicateKeyError":
                    raise ValueError("Email already registered") from exc
                raise
            return item
        with self._lock:
            if any(existing.get("email") == item["email"] for existing in self.memory["users"]):
                raise ValueError("Email already registered")
            self.memory["users"].append(dict(item))
        return item

    def questions(self, difficulty: str | None = None, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        query = {key: value for key, value in (("difficulty", difficulty), ("status", status)) if value}
        collection = self._collection("questions")
        if collection is not None:
            return [self._without_id(x) for x in collection.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)]
        items = [x for x in self.memory["questions"] if all(x.get(k) == v for k, v in query.items())]
        return [dict(x) for x in items[:limit]]

    def question(self, question_id: str) -> dict[str, Any] | None:
        collection = self._collection("questions")
        if collection is not None:
            return self._without_id(collection.find_one({"id": question_id}, {"_id": 0}))
        return next((dict(x) for x in self.memory["questions"] if x.get("id") == question_id), None)

    def save_question(self, question: dict[str, Any]) -> dict[str, Any]:
        item = {**question, "id": question.get("id", str(uuid.uuid4())), "created_at": question.get("created_at", _now())}
        collection = self._collection("questions")
        if collection is not None:
            collection.replace_one({"id": item["id"]}, item, upsert=True)
        else:
            with self._lock:
                self.memory["questions"] = [x for x in self.memory["questions"] if x.get("id") != item["id"]]
                self.memory["questions"].append(dict(item))
        return dict(item)

    def update_question_status(self, question_id: str, status: str, review_notes: str = "") -> bool:
        collection = self._collection("questions")
        if collection is not None:
            return collection.update_one({"id": question_id}, {"$set": {"status": status, "review_notes": review_notes, "updated_at": _now()}}).matched_count == 1
        with self._lock:
            for item in self.memory["questions"]:
                if item.get("id") == question_id:
                    item.update(status=status, review_notes=review_notes, updated_at=_now())
                    return True
        return False

    def save_document(self, document: dict[str, Any]) -> dict[str, Any]:
        """Insert one document. Duplicate checksum raises ValueError."""
        item = {**document, "id": document.get("id", str(uuid.uuid4())), "created_at": document.get("created_at", _now()), "status": document.get("status", "pending_review")}
        checksum = item.get("checksum")
        collection = self._collection("documents")
        if collection is not None:
            try:
                collection.insert_one(dict(item))
            except Exception as exc:
                if exc.__class__.__name__ == "DuplicateKeyError":
                    raise ValueError("Document with this checksum already exists") from exc
                raise
        else:
            with self._lock:
                if checksum and any(x.get("checksum") == checksum for x in self.memory["documents"]):
                    raise ValueError("Document with this checksum already exists")
                self.memory["documents"].append(dict(item))
        return item

    def document_by_checksum(self, checksum: str) -> dict[str, Any] | None:
        collection = self._collection("documents")
        if collection is not None:
            return self._without_id(collection.find_one({"checksum": checksum}, {"_id": 0}))
        with self._lock:
            return next((dict(x) for x in self.memory["documents"] if x.get("checksum") == checksum), None)

    def documents(self, limit: int = 100) -> list[dict[str, Any]]:
        collection = self._collection("documents")
        if collection is not None:
            return [self._without_id(x) for x in collection.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)]
        return [dict(x) for x in self.memory["documents"][-limit:]][::-1]

    def save_job(self, job: dict[str, Any]) -> dict[str, Any]:
        item = {**job, "id": job.get("id") or str(uuid.uuid4()), "created_at": job.get("created_at") or _now(), "updated_at": _now()}
        collection = self._collection("jobs")
        if collection is not None:
            collection.replace_one({"id": item["id"]}, item, upsert=True)
        else:
            with self._lock:
                self.memory["jobs"] = [x for x in self.memory["jobs"] if x.get("id") != item["id"]]
                self.memory["jobs"].append(dict(item))
        return dict(item)

    def job(self, job_id: str) -> dict[str, Any] | None:
        collection = self._collection("jobs")
        if collection is not None:
            return self._without_id(collection.find_one({"id": job_id}, {"_id": 0}))
        return next((dict(x) for x in self.memory["jobs"] if x.get("id") == job_id), None)

    def jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        collection = self._collection("jobs")
        if collection is not None:
            return [self._without_id(x) for x in collection.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)]
        return [dict(x) for x in self.memory["jobs"][-limit:]][::-1]

    def admin_stats(self) -> dict[str, Any]:
        users = self.users(limit=10000)
        questions = self.questions(limit=10000)
        documents = self.documents(limit=10000)
        jobs = self.jobs(limit=10000)
        return {
            "users": len(users),
            "active_users": sum(1 for x in users if x.get("status", "active") == "active"),
            "questions": len(questions),
            "approved_questions": sum(1 for x in questions if x.get("status") == "approved"),
            "pending_questions": sum(1 for x in questions if x.get("status") in {"pending_review", "draft"}),
            "documents": len(documents),
            "jobs": len(jobs),
        }

    def current_challenge(self) -> dict[str, Any] | None:
        collection = self._collection("challenges")
        if collection is not None:
            return self._without_id(collection.find_one({"status": "active"}, {"_id": 0}, sort=[("starts_at", -1)]))
        return next((dict(x) for x in reversed(self.memory["challenges"]) if x.get("status") == "active"), None)

    def challenge_questions(self, challenge: dict[str, Any]) -> list[dict[str, Any]]:
        ids = set(challenge.get("question_ids", []))
        return [x for x in self.questions(status="approved", limit=500) if x.get("id") in ids]

    def latest_job(self) -> dict[str, Any] | None:
        collection = self._collection("jobs")
        if collection is not None:
            return self._without_id(collection.find_one({}, {"_id": 0}, sort=[("created_at", -1)]))
        return dict(self.memory["jobs"][-1]) if self.memory["jobs"] else None

    def setting(self, key: str) -> dict[str, Any] | None:
        collection = self._collection("settings")
        if collection is not None:
            return self._without_id(collection.find_one({"key": key}, {"_id": 0}))
        with self._lock:
            return next((dict(x) for x in self.memory["settings"] if x.get("key") == key), None)

    def save_setting(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        item = {"key": key, "value": value, "updated_at": _now()}
        collection = self._collection("settings")
        if collection is not None:
            collection.replace_one({"key": key}, item, upsert=True)
        else:
            with self._lock:
                self.memory["settings"] = [x for x in self.memory["settings"] if x.get("key") != key]
                self.memory["settings"].append(dict(item))
        return dict(item)

    def save_audit(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Append one audit record. Caller must pass an already-redacted summary."""
        item = {
            "id": str(uuid.uuid4()),
            "actor_id": entry.get("actor_id", ""),
            "action": entry.get("action", ""),
            "resource_type": entry.get("resource_type", ""),
            "resource_id": entry.get("resource_id", ""),
            "summary": entry.get("summary", ""),
            "created_at": _now(),
        }
        collection = self._collection("audit_logs")
        if collection is not None:
            collection.insert_one(dict(item))
        else:
            with self._lock:
                self.memory["audit_logs"].append(dict(item))
        return item

    def audit_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        collection = self._collection("audit_logs")
        if collection is not None:
            return [self._without_id(x) for x in collection.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)]
        with self._lock:
            return [dict(x) for x in self.memory["audit_logs"][-limit:]][::-1]


_store: MongoStore | None = None


def get_store() -> MongoStore:
    global _store
    if _store is None:
        _store = MongoStore()
    return _store


def reset_store_for_tests() -> None:
    global _store
    _store = None
