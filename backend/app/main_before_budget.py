import re
import sqlite3
from datetime import date
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .jarvis_core import (
    IDENTITY_REPLY,
    OUT_OF_SCOPE_REPLY,
    SYSTEM_PROMPT,
    build_scope_check,
    format_records,
    is_blocked,
    precheck,
    scrub,
)

app = FastAPI(
    title="JARVIS 1B",
    description="Your Personal Specialised Assistant",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"  # check the exact tag with: ollama list
ASSISTANT_NAME = "JARVIS 1B"

# Whole-word matching: "event" no longer matches "prevent", "urge" no longer matches "urgent".
_DOMAIN_KEYWORDS = {
    "budget audit": [
        "budget", "expense", "expenses", "spending",
        "spent", "income", "savings", "transactions",
        "monthly allowance", "bills", "money audit",
        "financial audit", "save money", "purchase tracking",
    ],
    "assignment management": [
        "assignment", "assignments", "homework",
        "coursework", "submission", "deadline",
        "lab record", "exam schedule", "study schedule",
        "syllabus", "academic task", "college work",
    ],
    "event planning": [
        "event", "event plan", "event planning",
        "college fest", "workshop", "meetup",
        "guest list", "invitation", "venue",
        "party planning", "event budget",
        "party", "farewell", "celebration", "function",
        "birthday", "wedding", "fest", "seminar",
    ],
    "addiction recovery": [
        "addiction", "recovery", "craving", "relapse",
        "urge", "trigger", "screen time", "doomscrolling",
        "scrolling addiction", "social media addiction",
        "gaming addiction", "quit smoking",
        "compulsive habit", "recovery progress",
    ],
    "behaviour learning": [
        "behaviour", "behavior", "routine",
        "productivity", "procrastination", "focus",
        "daily habits", "time management",
        "my patterns", "learn my behaviour",
        "learn my behavior", "productivity pattern",
    ],
}
DOMAIN_PATTERNS = {
    domain: [re.compile(r"\b" + re.escape(k) + r"(?:s|es)?\b") for k in keywords]
    for domain, keywords in _DOMAIN_KEYWORDS.items()
}

conversation_history = []
last_domain = None

# =====================================
# JARVIS EVENT DATABASE
# =====================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "jarvis.db"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def get_db_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def initialise_database():
    connection = get_db_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_time TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()
    finally:
        connection.close()

def get_saved_events():
    connection = get_db_connection()

    try:
        rows = connection.execute("""
            SELECT id, title, event_date, event_time, details
            FROM events
            ORDER BY event_date ASC, event_time ASC
        """).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()

def save_event(title, event_date, event_time=None, details=None):
    connection = get_db_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO events (title, event_date, event_time, details)
            VALUES (?, ?, ?, ?)
        """, (title, event_date, event_time, details))

        connection.commit()
        event_id = cursor.lastrowid

        row = connection.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,)
        ).fetchone()

        return dict(row)
    finally:
        connection.close()

initialise_database()

def describe_event(event):
    line = f"{event['id']}. {event['title']} - {event['event_date']}"

    if event["event_time"]:
        line += f" at {event['event_time']}"

    if event["details"]:
        line += f"\n   Details: {event['details']}"

    return line

# =====================================
# DATA CHECKS
# =====================================

def get_user_context(current_message):
    previous_messages = [
        item["content"]
        for item in conversation_history
        if item["role"] == "user"
    ]

    return "\n".join(previous_messages + [current_message])

def has_budget_data(text):
    text = text.lower()

    has_amount = bool(re.search(
        r"(?:₹|rs\.?|inr)\s*\d[\d,]*(?:\.\d+)?"
        r"|\b\d[\d,]*(?:\.\d+)?\s*(?:rupees|rs)\b"
        r"|\b(?:income|salary|allowance|rent|groceries|food|"
        r"transport|expense|expenses|spent|savings|bills)"
        r"\D{0,20}\d[\d,]*(?:\.\d+)?",
        text
    ))

    has_category = any(term in text for term in [
        "income", "salary", "allowance", "rent",
        "groceries", "food", "transport", "expense",
        "expenses", "spent", "savings", "bills", "purchase"
    ])

    return has_amount and has_category

def has_productivity_data(text):
    text = text.lower()

    has_measurement = bool(re.search(
        r"\b\d+(?:\.\d+)?\s*"
        r"(?:hours?|hrs?|hr|h|minutes?|mins?|min|tasks?)\b",
        text
    ))

    has_activity = any(term in text for term in [
        "study", "studied", "studying", "coding",
        "class", "work", "break", "exercise",
        "sleep", "scrolling", "completed",
        "tasks", "social media", "screen time"
    ])

    return has_measurement and has_activity

def has_event_details(text):
    # A date, a budget or a headcount: at least one number in the conversation.
    return bool(re.search(r"\d", text))

# =====================================
# EVENT DATABASE: DETERMINISTIC HANDLING
# (this block used to sit unreachable inside has_productivity_data)
# =====================================

def handle_event_request(message, user_context):
    """Returns a response dict, or None when the model may help plan the event."""
    lower_message = message.lower().strip()

    # A. User asks to see saved events
    list_phrases = [
        "list events",
        "show events",
        "all events",
        "what events",
        "upcoming events",
        "events in database",
        "events in the database",
        "tell me what all events",
    ]

    if any(phrase in lower_message for phrase in list_phrases):
        events = get_saved_events()

        if not events:
            return {
                "assistant": ASSISTANT_NAME,
                "allowed": True,
                "category": "event planning",
                "events": [],
                "reply": (
                    "There are currently no events saved "
                    "in my database. I will only show events "
                    "that you actually provide and save."
                ),
            }

        return {
            "assistant": ASSISTANT_NAME,
            "allowed": True,
            "category": "event planning",
            "events": events,
            "reply": (
                "Here are the events actually saved "
                "in your database:\n\n"
                + "\n".join(describe_event(event) for event in events)
            ),
        }

    # B. Save an event only when the user supplies details
    if lower_message.startswith("add event:"):
        event_input = message[len("add event:"):].strip()
        parts = [part.strip() for part in event_input.split("|")]

        if len(parts) < 2 or not parts[0] or not parts[1]:
            return {
                "assistant": ASSISTANT_NAME,
                "allowed": True,
                "reply": (
                    "Please provide an event title and exact date.\n\n"
                    "Format:\n"
                    "Add event: Event Name | YYYY-MM-DD | Time | Details"
                ),
            }

        title = parts[0]
        event_date = parts[1]
        event_time = parts[2] if len(parts) > 2 and parts[2] else None
        details = parts[3] if len(parts) > 3 and parts[3] else None

        try:
            date.fromisoformat(event_date)
        except ValueError:
            return {
                "assistant": ASSISTANT_NAME,
                "allowed": True,
                "reply": (
                    "Please enter the date in YYYY-MM-DD format, "
                    "for example 2026-11-25."
                ),
            }

        saved = save_event(title, event_date, event_time, details)

        return {
            "assistant": ASSISTANT_NAME,
            "allowed": True,
            "category": "event planning",
            "event": saved,
            "reply": (
                f"I've saved '{title}' in your event database "
                f"for {event_date}."
            ),
        }

    # C. Do not invent events when the request has no details at all
    if not has_event_details(user_context):
        return {
            "assistant": ASSISTANT_NAME,
            "allowed": True,
            "category": "event planning",
            "reply": (
                "I can help organise your events, but I don't "
                "have enough information to create or plan one yet. "
                "Tell me the event name, date, purpose and any "
                "budget or venue details. I won't assume or invent them."
                "\n\nTo save an event, use:\n"
                "Add event: Event Name | YYYY-MM-DD | Time | Details"
            ),
        }

    return None

# =====================================
# SCOPE CONTROL
# =====================================

def detect_domain(message):
    text = message.lower().strip()

    # Check the authorised topics first. The topic with the most keyword matches wins,
    # so "farewell party ... budget 8000" is event planning, not a budget audit.
    scores = {
        domain: sum(1 for pattern in patterns if pattern.search(text))
        for domain, patterns in DOMAIN_PATTERNS.items()
    }
    best = max(scores, key=scores.get)

    if scores[best] > 0:
        return best

    # Basic personal identity interactions
    if (
        "my name is" in text
        or "call me" in text
        or "my name" in text
    ):
        return "personal profile"

    # Basic assistant interactions
    greetings = [
        "hi", "hello", "hey", "good morning",
        "good evening", "good afternoon",
    ]

    if text in greetings:
        return "greeting"

    if any(phrase in text for phrase in [
        "what can you do",
        "your capabilities",
        "what are your features",
        "who are you",
    ]):
        return "assistant information"

    # Allow short follow-up questions in the
    # previously established authorised topic
    words = text.split()

    follow_up_phrases = [
        "what next", "next step", "continue",
        "tell me more", "explain more",
        "and then", "why", "how about that",
    ]

    follow_up_words = [
        "it", "that", "this", "those",
        "them", "same", "more", "again",
    ]

    is_follow_up = (
        len(words) <= 8
        and (
            any(phrase in text for phrase in follow_up_phrases)
            or any(word in words for word in follow_up_words)
        )
    )

    if last_domain and is_follow_up:
        return last_domain

    return None

def remember(message, reply):
    conversation_history.extend([
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ])

    # Retain only the latest 20 messages
    del conversation_history[:-20]

def refusal():
    return {
        "assistant": ASSISTANT_NAME,
        "reply": OUT_OF_SCOPE_REPLY,
        "allowed": False,
    }

async def ask_model(messages, temperature=0.3, num_predict=400):
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "num_predict": num_predict,
            "temperature": temperature,
            "num_ctx": 4096,  # the system prompt is long; the default window can cut it off
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        return response.json()["message"]["content"].strip()

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def home():
    return {
        "assistant": ASSISTANT_NAME,
        "status": "online",
        "mode": "specialised",
    }

@app.get("/health")
def health():
    # The model name is deliberately not exposed here.
    return {
        "status": "healthy",
        "assistant": ASSISTANT_NAME,
        "memory": "enabled",
        "scope_control": "enabled",
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    global last_domain

    message = request.message.strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty"
        )

    # Step 1: safety, identity questions and obvious off-topic requests.
    # This runs before the topic check so a crisis message is never refused as "off topic".
    early = precheck(message)

    if early:
        reply, keep = early

        if keep:
            remember(message, reply)

        return {
            "assistant": ASSISTANT_NAME,
            "reply": reply,
            "allowed": reply != OUT_OF_SCOPE_REPLY,
        }

    # Step 2: check whether the question is authorised
    domain = detect_domain(message)

    if domain is None:
        return refusal()

    # Handle greetings and "who are you" without asking the model
    if domain == "greeting":
        return {
            "assistant": ASSISTANT_NAME,
            "reply": (
                "Hello! I'm JARVIS 1B. "
                "What would you like to organise today?"
            ),
            "allowed": True,
        }

    if domain == "assistant information":
        return {
            "assistant": ASSISTANT_NAME,
            "reply": IDENTITY_REPLY,
            "allowed": True,
        }

    # Step 3: verify that actual user data exists before analysis
    user_context = get_user_context(message)

    if domain == "event planning":
        # Earlier numbers from other topics (a budget, say) must not count as event details.
        event_context = user_context if last_domain == "event planning" else message
        event_response = handle_event_request(message, event_context)

        if event_response is not None:
            return event_response

    if domain == "budget audit" and not has_budget_data(user_context):
        return {
            "assistant": ASSISTANT_NAME,
            "allowed": True,
            "category": domain,
            "reply": (
                "I don't have your actual budget records yet. "
                "I cannot audit or estimate your income and expenses "
                "without real figures.\n\n"
                "Please provide your monthly income and actual "
                "expenses, such as rent, food, transport and other "
                "spending. I do not have access to your bank account."
            ),
        }

    if domain == "behaviour learning" and not has_productivity_data(user_context):
        return {
            "assistant": ASSISTANT_NAME,
            "allowed": True,
            "category": domain,
            "reply": (
                "I don't have your daily activity records yet. "
                "I cannot calculate your productivity, activity "
                "hours or screen time without actual data.\n\n"
                "Please share your activities and their durations. "
                "For example: studying 3 hours, coding 1 hour, "
                "scrolling 45 minutes and completing 2 tasks."
            ),
        }

    # Step 4: prepare context for an authorised question.
    # Saved events are passed in as RECORDS so the model cannot invent or deny them.
    records = None

    if domain == "event planning":
        records = {"Saved events": [describe_event(e) for e in get_saved_events()]}

    messages = [
        {
            "role": "system",
            "content": (
                SYSTEM_PROMPT
                + "\n\n" + format_records(records)
                + f"\n\nThe current authorised topic is: {domain}. "
                "Stay strictly within this topic. Do not answer unrelated requests."
            ),
        },
        *conversation_history[-20:],
        {"role": "user", "content": message},
    ]

    try:
        # Step 5: a quick yes/no topic check by the model. It catches things like
        # "explain recursion for my assignment", which pass the keyword check above.
        if domain != "personal profile":
            verdict = await ask_model(
                build_scope_check(message, conversation_history[-4:], domain),
                temperature=0.0,
                num_predict=4,
            )

            if is_blocked(verdict):
                return refusal()

        reply, keep = scrub(await ask_model(messages))

        # Step 6: save successful authorised conversations
        if keep:
            remember(message, reply)
            last_domain = domain

        return {
            "assistant": ASSISTANT_NAME,
            "reply": reply,
            "allowed": True,
            "category": domain,
        }

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="AI response timed out"
        )

    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail="The AI engine is unavailable."
        )

@app.post("/reset")
def reset_memory():
    global last_domain

    conversation_history.clear()
    last_domain = None

    return {
        "status": "success",
        "message": "Conversation memory cleared",
    }
