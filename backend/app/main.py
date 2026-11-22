from __future__ import annotations

import re
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

# ============================================================
# JARVIS 1B — local-first personal management backend
# ============================================================

APP_NAME = "JARVIS 1B"
MODEL = "llama3.2:1b"
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "jarvis.db"

app = FastAPI(
    title=APP_NAME,
    description="Local-first specialised personal assistant and management API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = """You are JARVIS 1B, a specialised personal assistant configured by your owner.
You are not a general-purpose chatbot. You may help only with:
1. Monthly budget auditing and expense organisation.
2. Assignment and academic deadline management.
3. Event planning and organisation.
4. Habit and addiction recovery support.
5. Behaviour and productivity tracking based on user-provided records.

STRICT TRUST AND DATA RULES:
- Never invent names, dates, events, transactions, assignments, activity logs,
  expenses, income, hours, screen-time values, recovery history or statistics.
- The application database is the source of truth. Only values explicitly
  included in the supplied context are saved records.
- If no saved records are supplied, say that no records are available.
- Never claim to have access to bank accounts, phone usage, calendars or apps.
- Do not fabricate a productivity score. Explain only calculations made from
  supplied records; prefer totals and trends over arbitrary scores.
- Distinguish saved facts from suggestions.
- For recovery support, be supportive and non-judgmental; do not diagnose or
  prescribe treatment. Suggest qualified help where appropriate.
- Do not answer unrelated general-knowledge questions. Briefly explain the
  five authorised areas and ask for an in-scope request.
- Do not claim information was saved unless the API actually saved it.

PERSONALITY: concise, clear, warm, practical and honest. Ask a focused question
when important details are missing. Never pretend to know something you do not.
"""

# Conversation context is deliberately temporary and local to this one process.
conversation_history: list[dict[str, str]] = []
last_domain: str | None = None

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "budget": (
        "budget", "expense", "expenses", "spending", "spent", "income",
        "savings", "transaction", "transactions", "allowance", "bill",
        "bills", "money audit", "financial audit", "save money", "purchase",
    ),
    "assignments": (
        "assignment", "assignments", "homework", "coursework", "submission",
        "deadline", "lab record", "exam schedule", "study schedule", "syllabus",
        "academic task", "college work", "pending work",
    ),
    "events": (
        "event", "events", "event plan", "event planning", "college fest",
        "workshop", "meetup", "guest list", "invitation", "venue", "party planning",
    ),
    "recovery": (
        "addiction", "recovery", "craving", "relapse", "urge", "trigger",
        "screen time", "doomscrolling", "scrolling addiction", "social media addiction",
        "gaming addiction", "quit smoking", "compulsive habit", "recovery progress",
        "habit tracker", "habit tracking",
    ),
    "behaviour": (
        "behaviour", "behavior", "routine", "productivity", "procrastination",
        "focus", "daily habits", "time management", "my patterns", "productivity pattern",
        "activity log", "daily activity", "work pattern",
    ),
}


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    connection = db()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS budget_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_type TEXT NOT NULL CHECK(transaction_type IN ('income','expense')),
                amount_paise INTEGER NOT NULL CHECK(amount_paise > 0),
                category TEXT NOT NULL,
                description TEXT,
                transaction_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_budget_date ON budget_transactions(transaction_date);

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_time TEXT,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);

            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subject TEXT,
                due_date TEXT,
                priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high')),
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','in_progress','completed')),
                description TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_assignments_due ON assignments(due_date);

            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                duration_minutes INTEGER NOT NULL CHECK(duration_minutes > 0),
                tasks_completed INTEGER NOT NULL DEFAULT 0 CHECK(tasks_completed >= 0),
                log_date TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_activity_date ON activity_logs(log_date);

            CREATE TABLE IF NOT EXISTS recovery_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('urge','managed','slip','success')),
                intensity INTEGER CHECK(intensity BETWEEN 0 AND 10),
                trigger TEXT,
                notes TEXT,
                log_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_recovery_date ON recovery_logs(log_date);

            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


init_db()


def rowdict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def money_to_paise(value: Decimal | float | int) -> int:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=422, detail="Enter a valid amount.")
    if not amount.is_finite() or amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be greater than zero.")
    return int(amount * 100)


def money_from_paise(value: int) -> float:
    return round(value / 100, 2)


def date_value(value: date) -> str:
    return value.isoformat()


def validate_month(month: str | None) -> str:
    selected = month or date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", selected):
        raise HTTPException(status_code=400, detail="Month must use YYYY-MM format.")
    try:
        date.fromisoformat(f"{selected}-01")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month.")
    return selected


# ============================================================
# Request schemas
# ============================================================

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class BudgetCreate(BaseModel):
    transaction_type: Literal["income", "expense"]
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category: str = Field(min_length=1, max_length=80)
    transaction_date: date
    description: str | None = Field(default=None, max_length=500)


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    event_date: date
    event_time: str | None = Field(default=None, max_length=40)
    details: str | None = Field(default=None, max_length=1000)


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    subject: str | None = Field(default=None, max_length=100)
    due_date: date | None = None
    priority: Literal["low", "medium", "high"] = "medium"
    description: str | None = Field(default=None, max_length=1000)


class AssignmentUpdate(BaseModel):
    status: Literal["pending", "in_progress", "completed"]


class ActivityCreate(BaseModel):
    activity: str = Field(min_length=1, max_length=100)
    category: str = Field(default="general", max_length=60)
    duration_minutes: int = Field(gt=0, le=1440)
    tasks_completed: int = Field(default=0, ge=0, le=1000)
    log_date: date
    notes: str | None = Field(default=None, max_length=1000)


class RecoveryCreate(BaseModel):
    habit: str = Field(min_length=1, max_length=120)
    status: Literal["urge", "managed", "slip", "success"]
    intensity: int | None = Field(default=None, ge=0, le=10)
    trigger: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)
    log_date: date


class PreferenceUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=200)


# ============================================================
# Budget operations
# ============================================================

def budget_record(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["amount"] = money_from_paise(item.pop("amount_paise"))
    return item


def budget_summary(month: str) -> dict:
    connection = db()
    try:
        totals = connection.execute(
            """SELECT
                 COALESCE(SUM(CASE WHEN transaction_type='income' THEN amount_paise ELSE 0 END),0) income,
                 COALESCE(SUM(CASE WHEN transaction_type='expense' THEN amount_paise ELSE 0 END),0) expenses,
                 COUNT(*) count
               FROM budget_transactions WHERE substr(transaction_date,1,7)=?""",
            (month,),
        ).fetchone()
        groups = connection.execute(
            """SELECT category, SUM(amount_paise) total
               FROM budget_transactions
               WHERE transaction_type='expense' AND substr(transaction_date,1,7)=?
               GROUP BY category ORDER BY total DESC""",
            (month,),
        ).fetchall()
        income = int(totals["income"])
        expenses = int(totals["expenses"])
        return {
            "month": month,
            "has_data": int(totals["count"]) > 0,
            "transaction_count": int(totals["count"]),
            "total_income": money_from_paise(income),
            "total_expenses": money_from_paise(expenses),
            "remaining_balance": money_from_paise(income - expenses),
            "expense_by_category": [
                {"category": r["category"], "total": money_from_paise(int(r["total"]))}
                for r in groups
            ],
        }
    finally:
        connection.close()


@app.get("/budget/summary")
def get_budget_summary(month: str | None = Query(default=None)):
    return budget_summary(validate_month(month))


@app.get("/budget/transactions")
def get_budget_transactions(month: str | None = Query(default=None)):
    connection = db()
    try:
        if month:
            selected = validate_month(month)
            rows = connection.execute(
                """SELECT * FROM budget_transactions WHERE substr(transaction_date,1,7)=?
                   ORDER BY transaction_date DESC,id DESC""", (selected,)
            ).fetchall()
        else:
            selected = None
            rows = connection.execute(
                "SELECT * FROM budget_transactions ORDER BY transaction_date DESC,id DESC"
            ).fetchall()
        records = [budget_record(r) for r in rows]
        return {"transactions": records, "count": len(records), "month": selected}
    finally:
        connection.close()


@app.post("/budget/transactions", status_code=201)
def create_budget_transaction(payload: BudgetCreate):
    category = payload.category.strip()
    if not category:
        raise HTTPException(status_code=422, detail="Category cannot be blank.")
    amount_paise = money_to_paise(payload.amount)
    connection = db()
    try:
        cursor = connection.execute(
            """INSERT INTO budget_transactions
               (transaction_type,amount_paise,category,description,transaction_date)
               VALUES (?,?,?,?,?)""",
            (payload.transaction_type, amount_paise, category,
             payload.description.strip() if payload.description else None,
             date_value(payload.transaction_date)),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM budget_transactions WHERE id=?", (cursor.lastrowid,)
        ).fetchone()
        return {"status": "saved", "transaction": budget_record(row)}
    finally:
        connection.close()


@app.delete("/budget/transactions/{transaction_id}")
def delete_budget_transaction(transaction_id: int):
    connection = db()
    try:
        cursor = connection.execute("DELETE FROM budget_transactions WHERE id=?", (transaction_id,))
        connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Transaction not found.")
        return {"status": "deleted", "id": transaction_id}
    finally:
        connection.close()


# ============================================================
# Events
# ============================================================

@app.get("/events")
def get_events():
    connection = db()
    try:
        rows = connection.execute(
            "SELECT * FROM events ORDER BY event_date ASC,event_time ASC,id ASC"
        ).fetchall()
        events = [dict(r) for r in rows]
        return {"events": events, "count": len(events)}
    finally:
        connection.close()


@app.post("/events", status_code=201)
def create_event(payload: EventCreate):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Event title cannot be blank.")
    connection = db()
    try:
        cursor = connection.execute(
            "INSERT INTO events(title,event_date,event_time,details) VALUES(?,?,?,?)",
            (title, date_value(payload.event_date), payload.event_time,
             payload.details.strip() if payload.details else None),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM events WHERE id=?", (cursor.lastrowid,)).fetchone()
        return {"status": "saved", "event": dict(row)}
    finally:
        connection.close()


@app.delete("/events/{event_id}")
def delete_event(event_id: int):
    connection = db()
    try:
        cursor = connection.execute("DELETE FROM events WHERE id=?", (event_id,))
        connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Event not found.")
        return {"status": "deleted", "id": event_id}
    finally:
        connection.close()


# ============================================================
# Assignments
# ============================================================

@app.get("/assignments")
def get_assignments(status: str | None = Query(default=None)):
    allowed = {"pending", "in_progress", "completed"}
    if status and status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid assignment status.")
    connection = db()
    try:
        if status:
            rows = connection.execute(
                "SELECT * FROM assignments WHERE status=? ORDER BY due_date IS NULL,due_date ASC,id DESC",
                (status,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM assignments ORDER BY due_date IS NULL,due_date ASC,id DESC"
            ).fetchall()
        records = [dict(r) for r in rows]
        return {"assignments": records, "count": len(records)}
    finally:
        connection.close()


@app.post("/assignments", status_code=201)
def create_assignment(payload: AssignmentCreate):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Assignment title cannot be blank.")
    connection = db()
    try:
        cursor = connection.execute(
            """INSERT INTO assignments(title,subject,due_date,priority,description)
               VALUES(?,?,?,?,?)""",
            (title, payload.subject.strip() if payload.subject else None,
             date_value(payload.due_date) if payload.due_date else None,
             payload.priority, payload.description.strip() if payload.description else None),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM assignments WHERE id=?", (cursor.lastrowid,)).fetchone()
        return {"status": "saved", "assignment": dict(row)}
    finally:
        connection.close()


@app.patch("/assignments/{assignment_id}")
def update_assignment(assignment_id: int, payload: AssignmentUpdate):
    connection = db()
    try:
        cursor = connection.execute(
            "UPDATE assignments SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (payload.status, assignment_id),
        )
        connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Assignment not found.")
        row = connection.execute("SELECT * FROM assignments WHERE id=?", (assignment_id,)).fetchone()
        return {"status": "updated", "assignment": dict(row)}
    finally:
        connection.close()


@app.delete("/assignments/{assignment_id}")
def delete_assignment(assignment_id: int):
    connection = db()
    try:
        cursor = connection.execute("DELETE FROM assignments WHERE id=?", (assignment_id,))
        connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Assignment not found.")
        return {"status": "deleted", "id": assignment_id}
    finally:
        connection.close()


# ============================================================
# Behaviour / productivity activity logs
# ============================================================

@app.get("/productivity/summary")
def get_productivity_summary(log_date: date | None = Query(default=None)):
    selected_date = date_value(log_date or date.today())
    connection = db()
    try:
        totals = connection.execute(
            """SELECT COALESCE(SUM(duration_minutes),0) minutes,
                      COALESCE(SUM(tasks_completed),0) tasks,
                      COUNT(*) entries
               FROM activity_logs WHERE log_date=?""", (selected_date,)
        ).fetchone()
        groups = connection.execute(
            """SELECT activity,category,SUM(duration_minutes) minutes,
                      SUM(tasks_completed) tasks
               FROM activity_logs WHERE log_date=?
               GROUP BY activity,category ORDER BY minutes DESC""", (selected_date,)
        ).fetchall()
        return {
            "date": selected_date,
            "has_data": int(totals["entries"]) > 0,
            "entry_count": int(totals["entries"]),
            "total_minutes": int(totals["minutes"]),
            "total_hours": round(int(totals["minutes"]) / 60, 2),
            "tasks_completed": int(totals["tasks"]),
            "activities": [dict(r) for r in groups],
        }
    finally:
        connection.close()


@app.get("/activity-logs")
def get_activity_logs(log_date: date | None = Query(default=None)):
    connection = db()
    try:
        if log_date:
            rows = connection.execute(
                "SELECT * FROM activity_logs WHERE log_date=? ORDER BY id DESC",
                (date_value(log_date),),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM activity_logs ORDER BY log_date DESC,id DESC LIMIT 100"
            ).fetchall()
        records = [dict(r) for r in rows]
        return {"logs": records, "count": len(records)}
    finally:
        connection.close()


@app.post("/activity-logs", status_code=201)
def create_activity_log(payload: ActivityCreate):
    activity = payload.activity.strip()
    if not activity:
        raise HTTPException(status_code=422, detail="Activity cannot be blank.")
    connection = db()
    try:
        cursor = connection.execute(
            """INSERT INTO activity_logs(activity,category,duration_minutes,tasks_completed,log_date,notes)
               VALUES(?,?,?,?,?,?)""",
            (activity, payload.category.strip() or "general",
             payload.duration_minutes, payload.tasks_completed, date_value(payload.log_date),
             payload.notes.strip() if payload.notes else None),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM activity_logs WHERE id=?", (cursor.lastrowid,)).fetchone()
        return {"status": "saved", "log": dict(row)}
    finally:
        connection.close()


@app.delete("/activity-logs/{log_id}")
def delete_activity_log(log_id: int):
    connection = db()
    try:
        cursor = connection.execute("DELETE FROM activity_logs WHERE id=?", (log_id,))
        connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Activity log not found.")
        return {"status": "deleted", "id": log_id}
    finally:
        connection.close()


# ============================================================
# Recovery support logs
# ============================================================

@app.get("/recovery/logs")
def get_recovery_logs(log_date: date | None = Query(default=None)):
    connection = db()
    try:
        if log_date:
            rows = connection.execute(
                "SELECT * FROM recovery_logs WHERE log_date=? ORDER BY id DESC",
                (date_value(log_date),),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM recovery_logs ORDER BY log_date DESC,id DESC LIMIT 100"
            ).fetchall()
        records = [dict(r) for r in rows]
        return {"logs": records, "count": len(records)}
    finally:
        connection.close()


@app.post("/recovery/logs", status_code=201)
def create_recovery_log(payload: RecoveryCreate):
    habit = payload.habit.strip()
    if not habit:
        raise HTTPException(status_code=422, detail="Habit cannot be blank.")
    connection = db()
    try:
        cursor = connection.execute(
            """INSERT INTO recovery_logs(habit,status,intensity,trigger,notes,log_date)
               VALUES(?,?,?,?,?,?)""",
            (habit, payload.status, payload.intensity,
             payload.trigger.strip() if payload.trigger else None,
             payload.notes.strip() if payload.notes else None, date_value(payload.log_date)),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM recovery_logs WHERE id=?", (cursor.lastrowid,)).fetchone()
        return {"status": "saved", "log": dict(row)}
    finally:
        connection.close()


@app.delete("/recovery/logs/{log_id}")
def delete_recovery_log(log_id: int):
    connection = db()
    try:
        cursor = connection.execute("DELETE FROM recovery_logs WHERE id=?", (log_id,))
        connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Recovery log not found.")
        return {"status": "deleted", "id": log_id}
    finally:
        connection.close()


# ============================================================
# User-approved basic profile memory
# ============================================================

@app.get("/profile")
def get_profile():
    connection = db()
    try:
        rows = connection.execute("SELECT key,value FROM preferences ORDER BY key").fetchall()
        return {"profile": {r["key"]: r["value"] for r in rows}}
    finally:
        connection.close()


@app.put("/profile/{key}")
def set_profile_value(key: str, payload: PreferenceUpdate):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", key):
        raise HTTPException(status_code=400, detail="Invalid profile key.")
    value = payload.value.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Profile value cannot be blank.")
    connection = db()
    try:
        connection.execute(
            """INSERT INTO preferences(key,value) VALUES(?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP""",
            (key, value),
        )
        connection.commit()
        return {"status": "saved", "key": key, "value": value}
    finally:
        connection.close()


# ============================================================
# Chat scope: deterministic for database queries, Ollama for in-scope help
# ============================================================

def detect_domain(message: str) -> str | None:
    text = message.lower().strip()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return domain
    if text in {"hi", "hello", "hey", "hi jarvis", "hello jarvis", "good morning", "good afternoon", "good evening"}:
        return "greeting"
    if any(p in text for p in ("who are you", "what can you do", "your capabilities", "what are your features")):
        return "assistant information"
    if "my name is" in text or re.search(r"\b(?:what is|what's|tell me)\s+my\s+name\b", text):
        return "personal profile"
    words = set(text.split())
    followups = {"it", "that", "this", "those", "them", "same", "more", "again", "continue"}
    if last_domain and len(words) <= 7 and (words & followups or text in {"why", "how", "what next", "tell me more"}):
        return last_domain
    return None


def remember(user: str, assistant: str) -> None:
    conversation_history.extend([
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ])
    del conversation_history[:-16]


def saved_name() -> str | None:
    connection = db()
    try:
        row = connection.execute("SELECT value FROM preferences WHERE key='name'").fetchone()
        return str(row[0]) if row else None
    finally:
        connection.close()


def build_budget_reply() -> tuple[str, dict]:
    summary = budget_summary(date.today().strftime("%Y-%m"))
    if not summary["has_data"]:
        return (f"There are no budget transactions saved for {summary['month']}. Add real income and expense records before asking for an audit.", summary)
    lines = [
        f"Income: ₹{summary['total_income']:,.2f}",
        f"Expenses: ₹{summary['total_expenses']:,.2f}",
        f"Balance: ₹{summary['remaining_balance']:,.2f}",
    ]
    if summary["expense_by_category"]:
        lines.append("Spending by category:")
        lines.extend(f"• {r['category']}: ₹{r['total']:,.2f}" for r in summary["expense_by_category"])
    lines.append("Calculated only from records saved in your JARVIS database.")
    return "\n".join(lines), summary


def is_record_query(domain: str, message: str) -> bool:
    """Return True only when the user clearly asks to retrieve saved records."""
    text = message.lower().strip()
    patterns = {
        "budget": (
            "audit my monthly budget", "audit my budget", "budget summary",
            "show my budget", "show budget", "monthly expenses", "my expenses",
            "my income", "list transactions", "show transactions",
            "how much have i spent", "how much did i spend", "spending summary",
            "budget records",
        ),
        "events": (
            "show all events", "show my events", "show events", "list events",
            "what events", "which events", "saved events", "upcoming events",
            "events in the database", "events in database", "event database",
            "retrieve events",
        ),
        "assignments": (
            "show my assignments", "show all assignments", "list assignments",
            "pending assignments", "what assignments", "which assignments",
            "my assignments", "due assignments", "upcoming deadlines",
            "check my assignments", "assignment list",
        ),
        "behaviour": (
            "analyse my daily productivity", "analyze my daily productivity",
            "my daily productivity", "daily productivity", "productivity summary",
            "activity logs", "activity summary", "time logged", "my activities",
            "review my productivity", "show my activity",
        ),
        "recovery": (
            "show my recovery", "list recovery", "recent recovery",
            "recovery records", "recovery check-ins", "recovery check ins",
            "recovery logs", "recovery history", "my recovery records",
        ),
    }
    return any(phrase in text for phrase in patterns.get(domain, ()))


@app.get("/")
def home():
    return {"assistant": APP_NAME, "status": "online", "mode": "specialised"}


@app.get("/health")
def health():
    connection = db()
    try:
        connection.execute("SELECT 1")
    finally:
        connection.close()
    return {
        "status": "healthy",
        "assistant": APP_NAME,
        "ai_model": MODEL,
        "database": "connected",
        "scope_control": "enabled",
        "modules": ["budget", "assignments", "events", "recovery", "behaviour"],
    }


@app.post("/chat")
async def chat(payload: ChatRequest):
    global last_domain
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    domain = detect_domain(message)
    if domain is None:
        return {
            "assistant": APP_NAME,
            "allowed": False,
            "reply": "I'm JARVIS 1B, configured for five areas only: budget auditing, assignment management, event planning, recovery support, and behaviour/productivity tracking. Please ask about one of these areas.",
        }
    if domain == "greeting":
        reply = "Hello. I'm JARVIS 1B. Which of your five focus areas should we work on?"
        remember(message, reply)
        return {"assistant": APP_NAME, "allowed": True, "reply": reply}
    if domain == "assistant information":
        reply = "I manage budget records, assignments, events, recovery logs, and productivity records. I only report information that you have saved or provided."
        remember(message, reply)
        return {"assistant": APP_NAME, "allowed": True, "reply": reply}
    if domain == "personal profile":
        match = re.search(r"my name is\s+([\w -]{1,60})", message, re.IGNORECASE)
        if match:
            name = match.group(1).strip(" .,!?:;").title()
            connection = db()
            try:
                connection.execute(
                    """INSERT INTO preferences(key,value) VALUES('name',?)
                       ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP""",
                    (name,),
                )
                connection.commit()
            finally:
                connection.close()
            reply = f"Nice to meet you, {name}. I've saved that name in your local JARVIS profile."
        else:
            name = saved_name()
            reply = f"Your saved name is {name}." if name else "You haven't saved your name in my profile yet."
        remember(message, reply)
        return {"assistant": APP_NAME, "allowed": True, "reply": reply}

    # Deterministic data-backed paths: model never invents records or totals.
    if domain == "budget" and is_record_query(domain, message):
        reply, summary = build_budget_reply()
        last_domain = domain
        remember(message, reply)
        return {"assistant": APP_NAME, "allowed": True, "category": domain, "reply": reply, "budget": summary}

    if domain == "events" and is_record_query(domain, message):
        connection = db()
        try:
            events = [dict(r) for r in connection.execute(
                "SELECT * FROM events ORDER BY event_date,event_time,id"
            ).fetchall()]
        finally:
            connection.close()
        if events:
            lines = [f"{e['title']} — {e['event_date']}" + (f" at {e['event_time']}" if e['event_time'] else "") for e in events]
            reply = "Saved events:\n" + "\n".join(lines)
        else:
            reply = "There are no events saved in your database yet. I won't invent any."
        last_domain = domain
        remember(message, reply)
        return {"assistant": APP_NAME, "allowed": True, "category": domain, "reply": reply, "events": events}

    if domain == "assignments" and is_record_query(domain, message):
        connection = db()
        try:
            assignments = [dict(r) for r in connection.execute(
                "SELECT * FROM assignments WHERE status != 'completed' ORDER BY due_date IS NULL,due_date,id"
            ).fetchall()]
        finally:
            connection.close()
        if assignments:
            lines = [f"{a['title']} — {a['status']} — due {a['due_date'] or 'date not set'}" for a in assignments]
            reply = "Your saved pending assignments:\n" + "\n".join(lines)
        else:
            reply = "There are no pending assignments saved in your database. Add your actual coursework and deadlines in Assignments."
        last_domain = domain
        remember(message, reply)
        return {"assistant": APP_NAME, "allowed": True, "category": domain, "reply": reply, "assignments": assignments}

    if domain == "behaviour" and is_record_query(domain, message):
        summary = get_productivity_summary(date.today())
        if not summary["has_data"]:
            reply = "I don't have activity records for today yet. Add your actual activities and durations in Behaviour Insights before I analyse your day."
        else:
            reply = (f"Today's saved activity: {summary['total_hours']} hours across {summary['entry_count']} records; "
                     f"{summary['tasks_completed']} tasks marked completed. These values are calculated only from your saved activity logs.")
            for item in summary["activities"]:
                reply += f"\n• {item['activity']}: {round(item['minutes']/60,2)} hours"
        last_domain = domain
        remember(message, reply)
        return {"assistant": APP_NAME, "allowed": True, "category": domain, "reply": reply, "productivity": summary}

    if domain == "recovery" and is_record_query(domain, message):
        connection = db()
        try:
            logs = [dict(r) for r in connection.execute(
                "SELECT * FROM recovery_logs ORDER BY log_date DESC,id DESC LIMIT 10"
            ).fetchall()]
        finally:
            connection.close()
        if not logs:
            reply = "I don't have any recovery records saved yet. You can record a voluntary check-in in the Recovery workspace. If you're facing an immediate safety concern, seek local emergency or professional support."
        else:
            counts: dict[str, int] = {}
            for item in logs:
                counts[item["status"]] = counts.get(item["status"], 0) + 1
            reply = "Your recent saved check-ins: " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) + ". This is a record summary, not a clinical assessment."
        last_domain = domain
        remember(message, reply)
        return {"assistant": APP_NAME, "allowed": True, "category": domain, "reply": reply, "recovery_logs": logs}

    # A vague mention of a new event is not a saved event. Ask for details instead
    # of claiming that an event exists or has been entered in the database.
    if domain == "events" and any(phrase in message.lower() for phrase in (
        "new event", "i have an event", "there is an event", "upcoming event",
    )):
        reply = (
            "I can help organise it, but I haven't saved an event yet. "
            "What is the event name and exact date? You can add it in the Event Planner workspace."
        )
        remember(message, reply)
        last_domain = domain
        return {"assistant": APP_NAME, "allowed": True, "category": domain, "reply": reply}

    # Only in-scope assistance that doesn't request fabricated records reaches Ollama.
    # The model may offer planning suggestions, but database-backed facts are
    # answered above by deterministic Python queries.
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": (
            f"The user's current authorised area is '{domain}'. "
            "You may give general planning suggestions only within this area. "
            "Do not claim that any record was created, changed, monitored, or retrieved. "
            "Do not invent personal history, figures, deadlines, events, or activity. "
            "When an action requires saving data, direct the user to the matching JARVIS workspace."
        )},
        *conversation_history[-12:],
        {"role": "user", "content": message},
    ]
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(OLLAMA_CHAT_URL, json={
                "model": MODEL,
                "messages": messages,
                "stream": False,
                "keep_alive": "10m",
                "options": {"num_predict": 180, "temperature": 0.25},
            })
            response.raise_for_status()
            result = response.json()
            reply = result.get("message", {}).get("content", "I couldn't form a response. Please try again.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Local AI timed out. Please retry.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Local AI unavailable: {exc}")
    remember(message, reply)
    last_domain = domain
    return {"assistant": APP_NAME, "allowed": True, "category": domain, "reply": reply}


@app.post("/reset")
def reset_conversation():
    global last_domain
    conversation_history.clear()
    last_domain = None
    return {"status": "success", "message": "Temporary conversation context cleared."}
