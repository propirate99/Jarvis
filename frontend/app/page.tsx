"use client";

import { useEffect, useRef, useState } from "react";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type Section =
  | "overview"
  | "assistant"
  | "budget"
  | "academics"
  | "events"
  | "recovery"
  | "behaviour";

type IconName =
  | "grid"
  | "message"
  | "wallet"
  | "book"
  | "calendar"
  | "heart"
  | "brain"
  | "arrow"
  | "spark"
  | "plus"
  | "check"
  | "shield"
  | "activity"
  | "send"
  | "refresh"
  | "clock"
  | "chevron"
  | "command";

const navItems: { id: Section; label: string; icon: IconName }[] = [
  { id: "overview", label: "Overview", icon: "grid" },
  { id: "assistant", label: "Assistant", icon: "message" },
  { id: "budget", label: "Budget audit", icon: "wallet" },
  { id: "academics", label: "Assignments", icon: "book" },
  { id: "events", label: "Event planner", icon: "calendar" },
  { id: "recovery", label: "Recovery", icon: "heart" },
  { id: "behaviour", label: "Behaviour insights", icon: "brain" },
];

const moduleCards: {
  id: Exclude<Section, "overview" | "assistant">;
  title: string;
  eyebrow: string;
  description: string;
  icon: IconName;
  accent: string;
  prompt: string;
  action: string;
}[] = [
  {
    id: "budget",
    title: "Budget audit",
    eyebrow: "01 / FINANCES",
    description: "Understand income, expenses and spending patterns using the figures you provide.",
    icon: "wallet",
    accent: "mint",
    prompt: "Audit my monthly budget",
    action: "Start an audit",
  },
  {
    id: "academics",
    title: "Assignments",
    eyebrow: "02 / ACADEMICS",
    description: "Keep coursework, submission dates and study priorities organised.",
    icon: "book",
    accent: "blue",
    prompt: "Check my pending assignments",
    action: "Review assignments",
  },
  {
    id: "events",
    title: "Event planner",
    eyebrow: "03 / PLANNING",
    description: "Create and retrieve event records, then work through the details and logistics.",
    icon: "calendar",
    accent: "violet",
    prompt: "Show all events in the database",
    action: "View saved events",
  },
  {
    id: "recovery",
    title: "Recovery support",
    eyebrow: "04 / WELLBEING",
    description: "Reflect on triggers, urges and progress with practical, non-judgemental support.",
    icon: "heart",
    accent: "rose",
    prompt: "Help me track my recovery progress",
    action: "Open recovery support",
  },
  {
    id: "behaviour",
    title: "Behaviour insights",
    eyebrow: "05 / PERSONAL PATTERNS",
    description: "Review routines and productivity from real activity logs—not guessed statistics.",
    icon: "brain",
    accent: "amber",
    prompt: "Analyse my daily productivity",
    action: "Review my patterns",
  },
];

const quickPrompts = [
  "Audit my monthly budget",
  "Check my pending assignments",
  "Show all events in the database",
  "Analyse my daily productivity",
];

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };

  switch (name) {
    case "grid":
      return <svg {...common}><rect x="3.5" y="3.5" width="7" height="7" rx="2" /><rect x="13.5" y="3.5" width="7" height="7" rx="2" /><rect x="3.5" y="13.5" width="7" height="7" rx="2" /><rect x="13.5" y="13.5" width="7" height="7" rx="2" /></svg>;
    case "message":
      return <svg {...common}><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H6l-2.5 2v-5.2A7.5 7.5 0 1 1 20 11.5Z" /><path d="M8 11.5h8M8 8.5h5" /></svg>;
    case "wallet":
      return <svg {...common}><rect x="3" y="5" width="18" height="15" rx="3" /><path d="M3 9h18M16 14h2" /><path d="M6 5V4a1 1 0 0 1 1-1h11" /></svg>;
    case "book":
      return <svg {...common}><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 1 4 17.5Z" /><path d="M4 17.5A2.5 2.5 0 0 1 6.5 15H20M8 7h8M8 10h6" /></svg>;
    case "calendar":
      return <svg {...common}><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4M17 3v4M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 17h.01M12 17h.01" /></svg>;
    case "heart":
      return <svg {...common}><path d="M20.4 5.8a5 5 0 0 0-7.1 0L12 7.1l-1.3-1.3a5 5 0 0 0-7.1 7.1l1.3 1.3L12 21l7.1-6.8 1.3-1.3a5 5 0 0 0 0-7.1Z" /></svg>;
    case "brain":
      return <svg {...common}><path d="M12 4.2a3.2 3.2 0 0 0-5.8 1.9 3.5 3.5 0 0 0-1.1 6.5 3.4 3.4 0 0 0 3.2 5.2A3.2 3.2 0 0 0 12 20Z" /><path d="M12 4.2a3.2 3.2 0 0 1 5.8 1.9 3.5 3.5 0 0 1 1.1 6.5 3.4 3.4 0 0 1-3.2 5.2A3.2 3.2 0 0 1 12 20ZM8 9.2c1.7 0 2.2 1.2 2.2 2.5M16 9.2c-1.7 0-2.2 1.2-2.2 2.5M12 12v8" /></svg>;
    case "arrow":
      return <svg {...common}><path d="M5 12h13M13 6l6 6-6 6" /></svg>;
    case "spark":
      return <svg {...common}><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" /><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z" /></svg>;
    case "plus":
      return <svg {...common}><path d="M12 5v14M5 12h14" /></svg>;
    case "check":
      return <svg {...common}><path d="m5 12 4 4L19 6" /></svg>;
    case "shield":
      return <svg {...common}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /><path d="m9 12 2 2 4-4" /></svg>;
    case "activity":
      return <svg {...common}><path d="M3 12h4l3-8 4 16 3-8h4" /></svg>;
    case "send":
      return <svg {...common}><path d="m21 3-7.2 18-3.8-7-7-3.8L21 3Z" /><path d="M10 14 21 3" /></svg>;
    case "refresh":
      return <svg {...common}><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.6 9A7 7 0 0 1 18 6l2 1M4 17l2 1a7 7 0 0 0 12.4-3" /></svg>;
    case "clock":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.5 2" /></svg>;
    case "chevron":
      return <svg {...common}><path d="m9 18 6-6-6-6" /></svg>;
    case "command":
      return <svg {...common}><path d="M9 7V5a2 2 0 1 0-2 2h10a2 2 0 1 0-2-2v14a2 2 0 1 0 2-2H7a2 2 0 1 0 2 2V7Z" /></svg>;
    default:
      return null;
  }
}

function getPageHeading(section: Section) {
  const headings: Record<Section, { eyebrow: string; title: string; description: string }> = {
    overview: {
      eyebrow: "PERSONAL COMMAND CENTRE",
      title: "Make room for what matters.",
      description: "Your personal workspace for staying organised, intentional and in control.",
    },
    assistant: {
      eyebrow: "JARVIS 1B / CONVERSATION",
      title: "Your assistant, in focus.",
      description: "A specialised assistant for the areas you choose to manage.",
    },
    budget: {
      eyebrow: "01 / FINANCES",
      title: "Budget audit",
      description: "Review real income and spending figures. No estimates or invented transactions.",
    },
    academics: {
      eyebrow: "02 / ACADEMICS",
      title: "Assignment workspace",
      description: "Bring your coursework, submission dates and study priorities into one place.",
    },
    events: {
      eyebrow: "03 / PLANNING",
      title: "Event planner",
      description: "Keep event details organised and retrieve only the events actually saved.",
    },
    recovery: {
      eyebrow: "04 / WELLBEING",
      title: "Recovery support",
      description: "A private, supportive space to reflect on habits, triggers and progress.",
    },
    behaviour: {
      eyebrow: "05 / PERSONAL PATTERNS",
      title: "Behaviour insights",
      description: "Understand your routines from information you provide—not assumptions.",
    },
  };
  return headings[section];
}

export default function Home() {
  const [activeSection, setActiveSection] = useState<Section>("overview");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");
  const [notice, setNotice] = useState("");
  const [currentDate, setCurrentDate] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Read the current date only in the browser. Next.js 16 prerenders
  // Client Components on the server, so Date must not be read during render.
  useEffect(() => {
    setCurrentDate(
      new Intl.DateTimeFormat("en-IN", {
        weekday: "long",
        day: "numeric",
        month: "long",
      }).format(new Date())
    );
  }, []);

  useEffect(() => {
    let mounted = true;

    fetch("http://127.0.0.1:8000/health")
      .then((response) => {
        if (!response.ok) throw new Error("Backend unavailable");
        return response.json();
      })
      .then(() => {
        if (mounted) setBackendStatus("online");
      })
      .catch(() => {
        if (mounted) setBackendStatus("offline");
      });

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  const pageHeading = getPageHeading(activeSection);

  async function sendMessage(text = input) {
    const message = text.trim();
    if (!message || loading) return;

    setActiveSection("assistant");
    setNotice("");
    setMessages((previous) => [...previous, { role: "user", content: message }]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "JARVIS backend returned an error.");
      }

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: typeof data.reply === "string" ? data.reply : "JARVIS returned an unexpected response.",
        },
      ]);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Unknown connection error.";
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: `I couldn't reach the local JARVIS service. ${errorMessage} Check that the backend and Ollama are running on your Mac.`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function resetConversation() {
    if (loading) return;
    try {
      const response = await fetch("http://127.0.0.1:8000/reset", { method: "POST" });
      if (!response.ok) throw new Error("Reset endpoint unavailable");
      setMessages([]);
      setNotice("Conversation context cleared.");
    } catch {
      setNotice("Couldn't clear backend conversation memory. Your visible chat was kept.");
    }
  }

  function openModule(section: Exclude<Section, "overview" | "assistant">) {
    setActiveSection(section);
    setNotice("");
  }

  function startModulePrompt(prompt: string) {
    void sendMessage(prompt);
  }

  const selectedModule = moduleCards.find((module) => module.id === activeSection);

  const statusText = backendStatus === "online" ? "Local AI ready" : backendStatus === "checking" ? "Connecting" : "Offline";

  return (
    <main className="app">
      <div className="blob blob-a" />
      <div className="blob blob-b" />
      <div className="blob blob-c" />

      <aside className="sidebar glass">
        <button className="brand" onClick={() => setActiveSection("overview")} aria-label="JARVIS overview">
          <span className="brand-mark"><img src="/app-logo.png" alt="" /></span>
          <span className="brand-name">JARVIS<small>1B</small></span>
        </button>
        <nav className="nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activeSection === item.id ? "active" : ""}`}
              onClick={() => { setActiveSection(item.id); setNotice(""); }}
              aria-current={activeSection === item.id ? "page" : undefined}
              title={item.label}
            >
              <Icon name={item.icon} size={19} />
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <div className="main">
        <header className="topbar">
          <span className="topbar-date">{currentDate || "Your workspace"}</span>
          <div className="topbar-right">
            <span className="pill glass"><span className={`dot ${backendStatus}`} />{statusText}</span>
            <span className="avatar glass" aria-label="Local workspace">P</span>
          </div>
        </header>

        <section className="content">
          <div className="heading">
            <div>
              <h1>{pageHeading.title}</h1>
              <p>{pageHeading.description}</p>
            </div>
            {activeSection === "assistant" && messages.length > 0 && (
              <button className="soft-button glass" onClick={() => void resetConversation()} disabled={loading}>
                <Icon name="refresh" size={15} /> New conversation
              </button>
            )}
          </div>

          {notice && <div className="notice" role="status">{notice}</div>}

          {activeSection === "overview" && (
            <>
              <section className="ask glass">
                <div className="ask-head">
                  <span className="orb"><Icon name="spark" size={20} /></span>
                  <div>
                    <h2>What would you like to organise?</h2>
                    <p>Ask in plain words. JARVIS only uses the details you share.</p>
                  </div>
                </div>
                <form className="composer" onSubmit={(event) => { event.preventDefault(); void sendMessage(); }}>
                  <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask about budgets, assignments, events…" aria-label="Message JARVIS" />
                  <button type="submit" disabled={!input.trim() || loading} aria-label="Send message"><Icon name="send" size={17} /></button>
                </form>
                <div className="chips">
                  {quickPrompts.map((prompt) => (
                    <button key={prompt} onClick={() => startModulePrompt(prompt)}>{prompt}</button>
                  ))}
                </div>
              </section>

              <h2 className="section-title">Focus areas</h2>
              <section className="cards">
                {moduleCards.map((module) => (
                  <button className={`card panel accent-${module.accent}`} key={module.id} onClick={() => openModule(module.id)}>
                    <span className="card-icon"><Icon name={module.icon} size={21} /></span>
                    <h3>{module.title}</h3>
                    <p>{module.description}</p>
                    <span className="card-open">Open <Icon name="chevron" size={14} /></span>
                  </button>
                ))}
              </section>

              <p className="principle"><Icon name="shield" size={15} /> Your records are the source of truth. JARVIS asks when details are missing instead of inventing them.</p>
            </>
          )}

          {activeSection === "assistant" && (
            <section className="assistant">
              <div className="chat panel">
                {messages.length === 0 ? (
                  <div className="welcome">
                    <span className="orb big"><Icon name="spark" size={26} /></span>
                    <h2>How can I help today?</h2>
                    <p>Budget audits, assignments, event planning, recovery support and behaviour insights. I use the information you provide.</p>
                    <div className="chips center">
                      {quickPrompts.map((prompt) => (
                        <button key={prompt} onClick={() => void sendMessage(prompt)}>{prompt}</button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="thread" aria-live="polite">
                    {messages.map((message, index) => (
                      <div className={`row ${message.role}`} key={`${index}-${message.role}`}>
                        {message.role === "assistant" && <span className="mini-avatar"><Icon name="spark" size={14} /></span>}
                        <div className="bubble">{message.content}</div>
                        {message.role === "user" && <span className="mini-avatar user">P</span>}
                      </div>
                    ))}
                    {loading && (
                      <div className="row assistant">
                        <span className="mini-avatar"><Icon name="spark" size={14} /></span>
                        <div className="bubble typing"><i /><i /><i /><span>Thinking locally</span></div>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>
                )}
                <form className="composer glass floating" onSubmit={(event) => { event.preventDefault(); void sendMessage(); }}>
                  <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Message JARVIS…" aria-label="Message JARVIS" disabled={loading} />
                  <button type="submit" disabled={loading || !input.trim()} aria-label="Send message"><Icon name="send" size={17} /></button>
                </form>
              </div>
            </section>
          )}

          {selectedModule && (
            <section className={`workspace panel accent-${selectedModule.accent}`}>
              <span className="card-icon big"><Icon name={selectedModule.icon} size={24} /></span>
              <h2>Start with your information</h2>
              <p>This workspace shows only what you share or save. Tell JARVIS the real details to begin.</p>
              <button className="primary" onClick={() => startModulePrompt(selectedModule.prompt)}>
                {selectedModule.action} <Icon name="arrow" size={16} />
              </button>
            </section>
          )}
        </section>
      </div>
    </main>
  );
}
