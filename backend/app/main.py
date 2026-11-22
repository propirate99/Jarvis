from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Literal

import asyncio
import json
import os

import httpx
from fastapi import FastAPI, HTTPException, Path as FastPath, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.jarvis_core import (
    ALLOWED_MODULES,
    MODULE_SYSTEM_PROMPTS,
    format_module_records,
    precheck,
    scrub,
)

# ============================================================
# JARVIS 1B — local-first isolated multi-module assistant backend
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
    description="Local-first multi-module assistant with isolated chat state, memory, and schemas",
    version="2.1.0",
)

# ----------------------------------------------------------------
# Request logging middleware: helps verify traffic from mobile devices
# ----------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    origin = request.headers.get("origin", "-")
    response = await call_next(request)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {client_ip} {request.method} {request.url.path} -> {response.status_code} (origin: {origin})", flush=True)
    return response

# ----------------------------------------------------------------
# CORS: Permissive for all LAN origins (192.168.x.x, 10.x.x.x, 172.x.x.x, localhost)
# ----------------------------------------------------------------
_extra_origins: list[str] = []
_jarvis_web_origin = os.environ.get("JARVIS_WEB_ORIGIN", "").strip()
if _jarvis_web_origin:
    _extra_origins.append(_jarvis_web_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$",
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://propirate99.github.io",
        *_extra_origins,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        # Check if chat_threads table exists and needs migration for assistant/academics
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='chat_threads'"
        ).fetchone()
        if table_sql and "assistant" not in table_sql[0]:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_threads_migrated (
                    module_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT OR IGNORE INTO chat_threads_migrated SELECT * FROM chat_threads;
                DROP TABLE chat_threads;
                ALTER TABLE chat_threads_migrated RENAME TO chat_threads;
                """
            )

        connection.executescript(
            """
            -- Chat threads keyed strictly by module_id
            CREATE TABLE IF NOT EXISTS chat_threads (
                module_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            -- Chat messages scoped strictly to module_id
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_id) REFERENCES chat_threads(module_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_module ON chat_messages(module_id, id);
            CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(module_id, created_at);

            -- Domain tables
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

        # Pre-seed isolated thread slots
        default_threads = [
            ("overview", "Executive Overview"),
            ("assistant", "Assistant Workspace & Private Memory"),
            ("budget", "Budget & Expense Audit"),
            ("assignments", "Assignments & Academic Deadlines"),
            ("events", "Event Planning & Logistics"),
            ("recovery", "Habit & Addiction Recovery"),
            ("behaviour", "Behaviour & Productivity Insights"),
        ]
        for mod_id, title in default_threads:
            connection.execute(
                """INSERT INTO chat_threads(module_id, title) VALUES (?, ?)
                   ON CONFLICT(module_id) DO NOTHING""",
                (mod_id, title),
            )

        connection.commit()
    finally:
        connection.close()


init_db()


def validate_module_id(module_id: str) -> str:
    mod = module_id.lower().strip()
    if mod not in ALLOWED_MODULES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid module_id '{module_id}'. Must be one of {sorted(ALLOWED_MODULES)}.",
        )
    return "assignments" if mod == "academics" else mod


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
# Schemas
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
# Domain record queries
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


def get_productivity_summary_dict(log_date_str: str) -> dict:
    connection = db()
    try:
        totals = connection.execute(
            """SELECT COALESCE(SUM(duration_minutes),0) minutes,
                      COALESCE(SUM(tasks_completed),0) tasks,
                      COUNT(*) entries
               FROM activity_logs WHERE log_date=?""", (log_date_str,)
        ).fetchone()
        groups = connection.execute(
            """SELECT activity, category, SUM(duration_minutes) minutes,
                      SUM(tasks_completed) tasks
               FROM activity_logs WHERE log_date=?
               GROUP BY activity, category ORDER BY minutes DESC""", (log_date_str,)
        ).fetchall()
        return {
            "date": log_date_str,
            "has_data": int(totals["entries"]) > 0,
            "entry_count": int(totals["entries"]),
            "total_minutes": int(totals["minutes"]),
            "total_hours": round(int(totals["minutes"]) / 60, 2),
            "tasks_completed": int(totals["tasks"]),
            "activities": [dict(r) for r in groups],
        }
    finally:
        connection.close()


def get_overview_metrics_dict() -> dict:
    today_str = date.today().isoformat()
    current_month = today_str[:7]
    connection = db()
    try:
        b_totals = connection.execute(
            """SELECT
                 COALESCE(SUM(CASE WHEN transaction_type='income' THEN amount_paise ELSE 0 END),0) income,
                 COALESCE(SUM(CASE WHEN transaction_type='expense' THEN amount_paise ELSE 0 END),0) expenses
               FROM budget_transactions WHERE substr(transaction_date,1,7)=?""",
            (current_month,),
        ).fetchone()
        balance = money_from_paise(int(b_totals["income"]) - int(b_totals["expenses"]))

        a_count = connection.execute(
            "SELECT COUNT(*) FROM assignments WHERE status != 'completed'"
        ).fetchone()[0]

        e_count = connection.execute(
            "SELECT COUNT(*) FROM events WHERE event_date >= ?", (today_str,)
        ).fetchone()[0]

        r_count = connection.execute(
            "SELECT COUNT(*) FROM recovery_logs WHERE log_date = ?", (today_str,)
        ).fetchone()[0]

        act_totals = connection.execute(
            "SELECT COALESCE(SUM(duration_minutes),0) FROM activity_logs WHERE log_date = ?", (today_str,)
        ).fetchone()[0]
        focus_hours = round(int(act_totals) / 60, 2)

        return {
            "current_month": current_month,
            "today": today_str,
            "monthly_balance": balance,
            "pending_assignments": int(a_count),
            "upcoming_events": int(e_count),
            "today_recovery_checkins": int(r_count),
            "today_focus_hours": focus_hours,
        }
    finally:
        connection.close()


# ============================================================
# Memory: strictly module-isolated turn buffer in SQLite
# ============================================================

def get_recent_messages(module_id: str, limit: int = 12) -> list[dict[str, str]]:
    connection = db()
    try:
        rows = connection.execute(
            """SELECT role, content FROM chat_messages
               WHERE module_id = ?
               ORDER BY id DESC LIMIT ?""",
            (module_id, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    finally:
        connection.close()


def save_chat_turn(module_id: str, user_msg: str, assistant_msg: str) -> tuple[int, str]:
    connection = db()
    try:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        connection.execute(
            "INSERT INTO chat_messages (module_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
            (module_id, user_msg, now_iso),
        )
        cursor = connection.execute(
            "INSERT INTO chat_messages (module_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
            (module_id, assistant_msg, now_iso),
        )
        connection.execute(
            "UPDATE chat_threads SET updated_at = CURRENT_TIMESTAMP WHERE module_id = ?",
            (module_id,),
        )
        connection.commit()
        return int(cursor.lastrowid or 0), now_iso
    finally:
        connection.close()


def fetch_module_records_slice(module_id: str) -> dict:
    """Load ONLY the active module's domain records to prevent cross-module injection."""
    connection = db()
    try:
        if module_id == "budget":
            month = date.today().strftime("%Y-%m")
            summary = budget_summary(month)
            if not summary["has_data"]:
                return {}
            return {
                f"Summary for {month}": [
                    f"Total Income: ₹{summary['total_income']:,.2f}",
                    f"Total Expenses: ₹{summary['total_expenses']:,.2f}",
                    f"Remaining Balance: ₹{summary['remaining_balance']:,.2f}",
                ],
                "Expense Categories": [
                    f"{c['category']}: ₹{c['total']:,.2f}" for c in summary["expense_by_category"]
                ],
            }
        elif module_id in ("assignments", "academics"):
            rows = connection.execute(
                "SELECT title, subject, due_date, priority, status FROM assignments WHERE status != 'completed' ORDER BY due_date IS NULL, due_date ASC LIMIT 15"
            ).fetchall()
            if not rows:
                return {}
            return {
                "Pending Assignments": [
                    f"{r['title']} ({r['subject'] or 'General'}) - Priority: {r['priority']} - Due: {r['due_date'] or 'None'} - Status: {r['status']}"
                    for r in rows
                ]
            }
        elif module_id == "events":
            rows = connection.execute(
                "SELECT title, event_date, event_time, details FROM events WHERE event_date >= ? ORDER BY event_date ASC, event_time ASC LIMIT 10",
                (date.today().isoformat(),),
            ).fetchall()
            if not rows:
                return {}
            return {
                "Upcoming Events": [
                    f"{r['title']} on {r['event_date']}" + (f" at {r['event_time']}" if r['event_time'] else "") + (f" ({r['details']})" if r['details'] else "")
                    for r in rows
                ]
            }
        elif module_id == "recovery":
            rows = connection.execute(
                "SELECT habit, status, intensity, trigger, log_date FROM recovery_logs ORDER BY log_date DESC, id DESC LIMIT 10"
            ).fetchall()
            if not rows:
                return {}
            return {
                "Recent Recovery Logs": [
                    f"{r['log_date']}: {r['habit']} - Status: {r['status']}" + (f" (Intensity: {r['intensity']}/10)" if r['intensity'] is not None else "") + (f" Trigger: {r['trigger']}" if r['trigger'] else "")
                    for r in rows
                ]
            }
        elif module_id == "behaviour":
            today_str = date.today().isoformat()
            summary = get_productivity_summary_dict(today_str)
            if not summary["has_data"]:
                return {}
            return {
                f"Today's Activity ({today_str})": [
                    f"Total Hours: {summary['total_hours']}h ({summary['total_minutes']} mins)",
                    f"Tasks Completed: {summary['tasks_completed']}",
                ],
                "Activity Breakdown": [
                    f"{a['activity']} ({a['category']}): {round(a['minutes']/60, 2)}h" for a in summary["activities"]
                ],
            }
        elif module_id == "overview":
            metrics = get_overview_metrics_dict()
            return {
                "Executive Snapshot": [
                    f"Monthly Net Balance: ₹{metrics['monthly_balance']:,.2f}",
                    f"Pending Assignments: {metrics['pending_assignments']}",
                    f"Upcoming Events: {metrics['upcoming_events']}",
                    f"Today's Recovery Check-ins: {metrics['today_recovery_checkins']}",
                    f"Today's Focus Hours: {metrics['today_focus_hours']}h",
                ]
            }
        elif module_id == "assistant":
            # Assistant module has its own clean private memory; can optionally include saved profile name
            name_row = connection.execute("SELECT value FROM preferences WHERE key='name'").fetchone()
            if name_row:
                return {"Profile": [f"User Name: {name_row[0]}"]}
            return {}
        return {}
    finally:
        connection.close()


def is_record_query(module_id: str, message: str) -> bool:
    """Return True only when the user clearly asks to retrieve saved records for this module."""
    text = message.lower().strip()
    patterns = {
        "budget": (
            "audit my monthly budget", "audit my budget", "budget summary",
            "show my budget", "show budget", "monthly expenses", "my expenses",
            "my income", "list transactions", "show transactions",
            "how much have i spent", "how much did i spend", "spending summary",
            "budget records", "what is my balance", "balance",
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
            "check my assignments", "assignment list", "check my pending assignments",
        ),
        "academics": (
            "show my assignments", "show all assignments", "list assignments",
            "pending assignments", "what assignments", "which assignments",
            "my assignments", "due assignments", "upcoming deadlines",
            "check my assignments", "assignment list", "check my pending assignments",
        ),
        "behaviour": (
            "analyse my daily productivity", "analyze my daily productivity",
            "my daily productivity", "daily productivity", "productivity summary",
            "activity logs", "activity summary", "time logged", "my activities",
            "review my productivity", "show my activity", "how much time did i spend",
        ),
        "recovery": (
            "show my recovery", "list recovery", "recent recovery",
            "recovery records", "recovery check-ins", "recovery check ins",
            "recovery logs", "recovery history", "my recovery records", "track my recovery",
        ),
        "overview": (
            "status", "overview", "executive summary", "dashboard summary", "how am i doing",
            "summary of all areas", "what's pending", "briefing",
        ),
        "assistant": (
            "who are you", "what can you do", "help me",
        ),
    }
    return any(phrase in text for phrase in patterns.get(module_id, ()))


# ============================================================
# API Endpoints: Isolated Chat & Memory per Sidebar Option
# ============================================================

@app.get("/")
def home():
    return {
        "assistant": APP_NAME,
        "status": "online",
        "architecture": "isolated-multi-module",
        "modules": sorted(ALLOWED_MODULES),
    }


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
        "modules": sorted(ALLOWED_MODULES),
        "isolation": "enforced",
    }


# Common chat execution logic
async def execute_isolated_chat(module_id: str, message: str) -> dict:
    mod_id = validate_module_id(module_id)
    message = message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Step 1: Precheck guards (crisis, identity, offtopic)
    pre = precheck(message)
    if pre is not None:
        reply, keep = pre
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        msg_id = 0
        if keep:
            msg_id, created_at = save_chat_turn(mod_id, message, reply)
        return {
            "id": msg_id,
            "module_id": mod_id,
            "assistant": APP_NAME,
            "allowed": True,
            "reply": reply,
            "created_at": created_at,
            "role": "assistant",
            "source": "guard",
        }

    # Step 2: Deterministic record responses (100% accurate, zero hallucination)
    if is_record_query(mod_id, message):
        if mod_id == "budget":
            summary = budget_summary(date.today().strftime("%Y-%m"))
            if not summary["has_data"]:
                reply = f"There are no budget transactions saved for {summary['month']}. Add real income and expense records before asking for an audit."
            else:
                lines = [
                    f"Income: ₹{summary['total_income']:,.2f}",
                    f"Expenses: ₹{summary['total_expenses']:,.2f}",
                    f"Balance: ₹{summary['remaining_balance']:,.2f}",
                ]
                if summary["expense_by_category"]:
                    lines.append("Spending by category:")
                    lines.extend(f"• {r['category']}: ₹{r['total']:,.2f}" for r in summary["expense_by_category"])
                lines.append("Calculated only from records saved in your JARVIS database.")
                reply = "\n".join(lines)
            msg_id, created_at = save_chat_turn(mod_id, message, reply)
            return {
                "id": msg_id,
                "module_id": mod_id,
                "assistant": APP_NAME,
                "allowed": True,
                "reply": reply,
                "created_at": created_at,
                "role": "assistant",
                "budget": summary,
            }

        elif mod_id in ("assignments", "academics"):
            connection = db()
            try:
                assignments = [dict(r) for r in connection.execute(
                    "SELECT * FROM assignments WHERE status != 'completed' ORDER BY due_date IS NULL, due_date ASC, id DESC"
                ).fetchall()]
            finally:
                connection.close()
            if assignments:
                lines = [f"• {a['title']} ({a.get('subject') or 'General'}) — {a['status']} — due {a['due_date'] or 'no deadline set'}" for a in assignments]
                reply = "Your saved pending assignments:\n" + "\n".join(lines)
            else:
                reply = "There are no pending assignments saved in your database. Add your coursework and deadlines in Assignments."
            msg_id, created_at = save_chat_turn(mod_id, message, reply)
            return {
                "id": msg_id,
                "module_id": mod_id,
                "assistant": APP_NAME,
                "allowed": True,
                "reply": reply,
                "created_at": created_at,
                "role": "assistant",
                "assignments": assignments,
            }

        elif mod_id == "events":
            connection = db()
            try:
                events = [dict(r) for r in connection.execute(
                    "SELECT * FROM events ORDER BY event_date ASC, event_time ASC, id ASC"
                ).fetchall()]
            finally:
                connection.close()
            if events:
                lines = [f"• {e['title']} — {e['event_date']}" + (f" at {e['event_time']}" if e['event_time'] else "") for e in events]
                reply = "Saved events:\n" + "\n".join(lines)
            else:
                reply = "There are no events saved in your database yet. I won't invent any."
            msg_id, created_at = save_chat_turn(mod_id, message, reply)
            return {
                "id": msg_id,
                "module_id": mod_id,
                "assistant": APP_NAME,
                "allowed": True,
                "reply": reply,
                "created_at": created_at,
                "role": "assistant",
                "events": events,
            }

        elif mod_id == "recovery":
            connection = db()
            try:
                logs = [dict(r) for r in connection.execute(
                    "SELECT * FROM recovery_logs ORDER BY log_date DESC, id DESC LIMIT 10"
                ).fetchall()]
            finally:
                connection.close()
            if not logs:
                reply = "I don't have any recovery records saved yet. You can record a check-in in the Recovery workspace."
            else:
                counts: dict[str, int] = {}
                for item in logs:
                    counts[item["status"]] = counts.get(item["status"], 0) + 1
                reply = "Your recent saved check-ins: " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) + ". This is a record summary, not a clinical assessment."
            msg_id, created_at = save_chat_turn(mod_id, message, reply)
            return {
                "id": msg_id,
                "module_id": mod_id,
                "assistant": APP_NAME,
                "allowed": True,
                "reply": reply,
                "created_at": created_at,
                "role": "assistant",
                "recovery_logs": logs,
            }

        elif mod_id == "behaviour":
            summary = get_productivity_summary_dict(date.today().isoformat())
            if not summary["has_data"]:
                reply = "I don't have activity records for today yet. Add your actual activities and durations in Behaviour Insights before I analyse your day."
            else:
                reply = (
                    f"Today's saved activity: {summary['total_hours']} hours across {summary['entry_count']} records; "
                    f"{summary['tasks_completed']} tasks marked completed."
                )
                for item in summary["activities"]:
                    reply += f"\n• {item['activity']}: {round(item['minutes']/60, 2)} hours"
            msg_id, created_at = save_chat_turn(mod_id, message, reply)
            return {
                "id": msg_id,
                "module_id": mod_id,
                "assistant": APP_NAME,
                "allowed": True,
                "reply": reply,
                "created_at": created_at,
                "role": "assistant",
                "productivity": summary,
            }

        elif mod_id == "overview":
            metrics = get_overview_metrics_dict()
            reply = (
                f"Executive Briefing ({metrics['today']}):\n"
                f"• Monthly Net Balance: ₹{metrics['monthly_balance']:,.2f}\n"
                f"• Pending Assignments: {metrics['pending_assignments']}\n"
                f"• Upcoming Events: {metrics['upcoming_events']}\n"
                f"• Today's Recovery Check-ins: {metrics['today_recovery_checkins']}\n"
                f"• Today's Focus Hours: {metrics['today_focus_hours']}h\n"
                f"All metrics are sourced directly from your isolated JARVIS workspace records."
            )
            msg_id, created_at = save_chat_turn(mod_id, message, reply)
            return {
                "id": msg_id,
                "module_id": mod_id,
                "assistant": APP_NAME,
                "allowed": True,
                "reply": reply,
                "created_at": created_at,
                "role": "assistant",
                "overview": metrics,
            }

        elif mod_id == "assistant":
            reply = "I am JARVIS 1B, your private personal assistant. This is your general conversation tab with its own isolated memory."
            msg_id, created_at = save_chat_turn(mod_id, message, reply)
            return {
                "id": msg_id,
                "module_id": mod_id,
                "assistant": APP_NAME,
                "allowed": True,
                "reply": reply,
                "created_at": created_at,
                "role": "assistant",
            }

    # Step 3: Local Ollama AI Runtime (Single Shared Runtime with Isolated Payload)
    records_slice = fetch_module_records_slice(mod_id)
    records_block = format_module_records(mod_id, records_slice)
    module_history = get_recent_messages(mod_id, limit=12)

    prompt_content = MODULE_SYSTEM_PROMPTS.get(mod_id, MODULE_SYSTEM_PROMPTS["overview"])
    messages = [
        {"role": "system", "content": prompt_content},
        {"role": "system", "content": records_block},
        *module_history,
        {"role": "user", "content": message},
    ]

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                OLLAMA_CHAT_URL,
                json={
                    "model": MODEL,
                    "messages": messages,
                    "stream": False,
                    "keep_alive": "10m",
                    "options": {"num_predict": 220, "temperature": 0.25},
                },
            )
            response.raise_for_status()
            result = response.json()
            raw_reply = result.get("message", {}).get("content", "I couldn't form a response. Please try again.")
            reply, keep = scrub(raw_reply)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Local AI timed out for module '{mod_id}'. Please retry.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Local Ollama service offline or unreachable ({exc}). Ensure Ollama is running.")

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    msg_id = 0
    if keep:
        msg_id, created_at = save_chat_turn(mod_id, message, reply)

    return {
        "id": msg_id,
        "module_id": mod_id,
        "assistant": APP_NAME,
        "allowed": True,
        "reply": reply,
        "created_at": created_at,
        "role": "assistant",
    }


# ============================================================
# SSE streaming chat helpers
# ============================================================

async def stream_isolated_chat(module_id: str, message: str):
    """
    Async generator that yields Server-Sent Events (SSE) for a chat turn.

    Protocol:
      data: {"delta": "<token>"}     — partial token from Ollama
      data: {"done": true, "id": N, "created_at": "<iso>"}  — final metadata
      data: [DONE]                   — sentinel (matches OpenAI convention)
    """
    mod_id = validate_module_id(module_id)
    message = message.strip()
    if not message:
        yield "data: " + json.dumps({"error": "Message cannot be empty."}) + "\n\n"
        return

    # --- guard / deterministic paths: delegate to non-streaming logic, then emit as single chunk ---
    pre = precheck(message)
    if pre is not None or is_record_query(mod_id, message):
        result = await execute_isolated_chat(mod_id, message)
        reply = result.get("reply", "")
        yield "data: " + json.dumps({"delta": reply}) + "\n\n"
        yield "data: " + json.dumps({
            "done": True,
            "id": result.get("id", 0),
            "created_at": result.get("created_at", ""),
        }) + "\n\n"
        yield "data: [DONE]\n\n"
        return

    # --- Ollama streaming path ---
    records_slice = fetch_module_records_slice(mod_id)
    records_block = format_module_records(mod_id, records_slice)
    module_history = get_recent_messages(mod_id, limit=12)

    prompt_content = MODULE_SYSTEM_PROMPTS.get(mod_id, MODULE_SYSTEM_PROMPTS["overview"])
    ollama_messages = [
        {"role": "system", "content": prompt_content},
        {"role": "system", "content": records_block},
        *module_history,
        {"role": "user", "content": message},
    ]

    full_reply_parts: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                OLLAMA_CHAT_URL,
                json={
                    "model": MODEL,
                    "messages": ollama_messages,
                    "stream": True,
                    "keep_alive": "10m",
                    "options": {"num_predict": 220, "temperature": 0.25},
                },
            ) as resp:
                resp.raise_for_status()
                async for raw_line in resp.aiter_lines():
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        chunk = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_reply_parts.append(token)
                        yield "data: " + json.dumps({"delta": token}) + "\n\n"
                    if chunk.get("done"):
                        break
    except httpx.TimeoutException:
        yield "data: " + json.dumps({"error": f"Local AI timed out for '{mod_id}'. Please retry."}) + "\n\n"
        yield "data: [DONE]\n\n"
        return
    except httpx.HTTPError as exc:
        yield "data: " + json.dumps({"error": f"Ollama unreachable: {exc}. Ensure Ollama is running."}) + "\n\n"
        yield "data: [DONE]\n\n"
        return

    # --- persist full turn ---
    raw_reply = "".join(full_reply_parts)
    reply, keep = scrub(raw_reply)

    msg_id = 0
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if keep and reply:
        msg_id, created_at = save_chat_turn(mod_id, message, reply)

    yield "data: " + json.dumps({"done": True, "id": msg_id, "created_at": created_at}) + "\n\n"
    yield "data: [DONE]\n\n"


# Standard /chat/{module_id} endpoints
@app.post("/chat/{module_id}")
async def chat_module(payload: ChatRequest, module_id: str = FastPath(...)):
    return await execute_isolated_chat(module_id, payload.message)


# SSE streaming endpoint: GET /chat/{module_id}/stream?message=…
@app.get("/chat/{module_id}/stream")
async def chat_module_stream(module_id: str = FastPath(...), message: str = Query(..., min_length=1, max_length=4000)):
    return StreamingResponse(
        stream_isolated_chat(module_id, message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        },
    )


# SSE streaming for the RESTful /api/modules path: GET /api/modules/{id}/threads/{t}/stream?message=…
@app.get("/api/modules/{module_id}/threads/{thread_id}/stream")
async def api_thread_stream(
    module_id: str,
    thread_id: str = "main",
    message: str = Query(..., min_length=1, max_length=4000),
):
    return StreamingResponse(
        stream_isolated_chat(module_id, message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        },
    )


# ============================================================
# WebSocket Real-Time Chat & Streaming Endpoints
# ============================================================

@app.websocket("/ws")
@app.websocket("/ws/{module_id}")
async def websocket_chat_endpoint(websocket: WebSocket, module_id: str = "overview"):
    await websocket.accept()
    client_host = websocket.client.host if websocket.client else "unknown"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WS] Client {client_host} connected (module: {module_id})", flush=True)
    try:
        await websocket.send_json({
            "type": "connected",
            "status": "online",
            "module_id": module_id,
            "assistant": APP_NAME,
        })
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
            except Exception:
                data = {"message": raw_text}

            msg_type = data.get("type", "chat")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            target_module = data.get("module_id", module_id)
            user_msg = data.get("message", "").strip()
            if not user_msg:
                await websocket.send_json({"type": "error", "error": "Message cannot be empty."})
                continue

            # Stream tokens to WebSocket client in real-time
            async for sse_chunk in stream_isolated_chat(target_module, user_msg):
                if sse_chunk.startswith("data: "):
                    body = sse_chunk[6:].strip()
                    if body == "[DONE]":
                        await websocket.send_json({"type": "done"})
                    else:
                        try:
                            parsed = json.loads(body)
                            if "delta" in parsed:
                                await websocket.send_json({"type": "delta", "token": parsed["delta"]})
                            elif "done" in parsed:
                                await websocket.send_json({"type": "meta", **parsed})
                            elif "error" in parsed:
                                await websocket.send_json({"type": "error", "error": parsed["error"]})
                        except Exception:
                            pass
    except WebSocketDisconnect:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WS] Client {client_host} disconnected", flush=True)
    except Exception as exc:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WS-ERROR] {client_host}: {exc}", flush=True)


def fetch_module_chat_messages(module_id: str, limit: int = 100) -> dict:
    mod_id = validate_module_id(module_id)
    connection = db()
    try:
        rows = connection.execute(
            """SELECT id, module_id, role, content, created_at
               FROM chat_messages
               WHERE module_id = ?
               ORDER BY id ASC LIMIT ?""",
            (mod_id, int(limit)),
        ).fetchall()
        return {"module_id": mod_id, "messages": [dict(r) for r in rows]}
    finally:
        connection.close()


def do_reset_module_chat(module_id: str) -> dict:
    mod_id = validate_module_id(module_id)
    connection = db()
    try:
        cursor = connection.execute("DELETE FROM chat_messages WHERE module_id = ?", (mod_id,))
        connection.execute(
            "UPDATE chat_threads SET updated_at = CURRENT_TIMESTAMP WHERE module_id = ?",
            (mod_id,),
        )
        connection.commit()
        return {
            "status": "success",
            "module_id": mod_id,
            "deleted_count": cursor.rowcount,
            "message": f"Isolated conversation memory for '{mod_id}' cleared.",
        }
    finally:
        connection.close()


@app.get("/chat/{module_id}/messages")
def get_module_chat_messages(module_id: str = FastPath(...), limit: int = Query(default=100, ge=1, le=500)):
    return fetch_module_chat_messages(module_id=module_id, limit=limit)


@app.post("/chat/{module_id}/reset")
def reset_module_chat(module_id: str = FastPath(...)):
    return do_reset_module_chat(module_id=module_id)


# RESTful /api/modules/{apiId}/threads/{threadId}/... endpoints
@app.get("/api/modules/{module_id}/threads/{thread_id}/messages")
def get_thread_messages(module_id: str, thread_id: str = "main", limit: int = 100):
    return fetch_module_chat_messages(module_id=module_id, limit=limit)


@app.post("/api/modules/{module_id}/threads/{thread_id}/chat")
async def post_thread_chat(payload: ChatRequest, module_id: str, thread_id: str = "main"):
    return await execute_isolated_chat(module_id, payload.message)


@app.delete("/api/modules/{module_id}/threads/{thread_id}")
def delete_thread(module_id: str, thread_id: str = "main"):
    return do_reset_module_chat(module_id=module_id)


# Backwards compatible /chat endpoint (maps to overview or keyword-detected module)
@app.post("/chat")
async def chat_legacy(payload: ChatRequest):
    message = payload.message.strip()
    detected = "overview"
    text = message.lower()
    for domain, kws in DOMAIN_KEYWORDS.items():
        if any(kw in text for kw in kws):
            detected = domain
            break
    return await chat_module(payload=payload, module_id=detected)


@app.post("/reset")
def reset_all_chats():
    connection = db()
    try:
        connection.execute("DELETE FROM chat_messages")
        connection.commit()
        return {"status": "success", "message": "All module chat histories cleared."}
    finally:
        connection.close()


# ============================================================
# Domain records API: Module-scoped endpoints
# ============================================================

@app.get("/modules/{module_id}/records")
def get_module_records(module_id: str = FastPath(...)):
    mod_id = validate_module_id(module_id)
    connection = db()
    try:
        if mod_id == "budget":
            month = date.today().strftime("%Y-%m")
            summary = budget_summary(month)
            txs = [budget_record(r) for r in connection.execute(
                "SELECT * FROM budget_transactions ORDER BY transaction_date DESC, id DESC LIMIT 50"
            ).fetchall()]
            return {"module_id": mod_id, "summary": summary, "transactions": txs}

        elif mod_id in ("assignments", "academics"):
            rows = connection.execute(
                "SELECT * FROM assignments ORDER BY due_date IS NULL, due_date ASC, id DESC"
            ).fetchall()
            return {"module_id": mod_id, "assignments": [dict(r) for r in rows]}

        elif mod_id == "events":
            rows = connection.execute(
                "SELECT * FROM events ORDER BY event_date ASC, event_time ASC, id ASC"
            ).fetchall()
            return {"module_id": mod_id, "events": [dict(r) for r in rows]}

        elif mod_id == "recovery":
            rows = connection.execute(
                "SELECT * FROM recovery_logs ORDER BY log_date DESC, id DESC LIMIT 50"
            ).fetchall()
            return {"module_id": mod_id, "logs": [dict(r) for r in rows]}

        elif mod_id == "behaviour":
            summary = get_productivity_summary_dict(date.today().isoformat())
            logs = [dict(r) for r in connection.execute(
                "SELECT * FROM activity_logs ORDER BY log_date DESC, id DESC LIMIT 50"
            ).fetchall()]
            return {"module_id": mod_id, "summary": summary, "logs": logs}

        elif mod_id == "overview":
            return {"module_id": mod_id, "metrics": get_overview_metrics_dict()}

        elif mod_id == "assistant":
            return {"module_id": mod_id, "status": "active"}

        raise HTTPException(status_code=400, detail="Unhandled module")
    finally:
        connection.close()


# Dedicated Domain Endpoints
@app.get("/overview/summary")
def get_overview_summary():
    return {"metrics": get_overview_metrics_dict()}


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
                   ORDER BY transaction_date DESC, id DESC""", (selected,)
            ).fetchall()
        else:
            selected = None
            rows = connection.execute(
                "SELECT * FROM budget_transactions ORDER BY transaction_date DESC, id DESC"
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
               (transaction_type, amount_paise, category, description, transaction_date)
               VALUES (?, ?, ?, ?, ?)""",
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


@app.get("/events")
def get_events():
    connection = db()
    try:
        rows = connection.execute(
            "SELECT * FROM events ORDER BY event_date ASC, event_time ASC, id ASC"
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
            "INSERT INTO events(title, event_date, event_time, details) VALUES(?, ?, ?, ?)",
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


@app.get("/assignments")
def get_assignments(status: str | None = Query(default=None)):
    allowed = {"pending", "in_progress", "completed"}
    if status and status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid assignment status.")
    connection = db()
    try:
        if status:
            rows = connection.execute(
                "SELECT * FROM assignments WHERE status=? ORDER BY due_date IS NULL, due_date ASC, id DESC",
                (status,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM assignments ORDER BY due_date IS NULL, due_date ASC, id DESC"
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
            """INSERT INTO assignments(title, subject, due_date, priority, description)
               VALUES(?, ?, ?, ?, ?)""",
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
            "UPDATE assignments SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
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


@app.get("/productivity/summary")
def get_productivity_summary(log_date: date | None = Query(default=None)):
    selected_date = date_value(log_date or date.today())
    return get_productivity_summary_dict(selected_date)


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
                "SELECT * FROM activity_logs ORDER BY log_date DESC, id DESC LIMIT 100"
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
            """INSERT INTO activity_logs(activity, category, duration_minutes, tasks_completed, log_date, notes)
               VALUES(?, ?, ?, ?, ?, ?)""",
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
                "SELECT * FROM recovery_logs ORDER BY log_date DESC, id DESC LIMIT 100"
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
            """INSERT INTO recovery_logs(habit, status, intensity, trigger, notes, log_date)
               VALUES(?, ?, ?, ?, ?, ?)""",
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


@app.get("/profile")
def get_profile():
    connection = db()
    try:
        rows = connection.execute("SELECT key, value FROM preferences ORDER BY key").fetchall()
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
            """INSERT INTO preferences(key, value) VALUES(?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
            (key, value),
        )
        connection.commit()
        return {"status": "saved", "key": key, "value": value}
    finally:
        connection.close()
