"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";
import Image from "next/image";

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
  | "shield"
  | "send"
  | "refresh"
  | "chevron";

type Accent = "yellow" | "gold" | "orange" | "peach" | "champagne";

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
  description: string;
  icon: IconName;
  accent: Accent;
  prompt: string;
  action: string;
}[] = [
  {
    id: "budget",
    title: "Budget audit",
    description: "Understand income, expenses and spending patterns using the figures you provide.",
    icon: "wallet",
    accent: "yellow",
    prompt: "Audit my monthly budget",
    action: "Start an audit",
  },
  {
    id: "academics",
    title: "Assignments",
    description: "Keep coursework, submission dates and study priorities organised.",
    icon: "book",
    accent: "gold",
    prompt: "Check my pending assignments",
    action: "Review assignments",
  },
  {
    id: "events",
    title: "Event planner",
    description: "Create and retrieve event records, then work through the details and logistics.",
    icon: "calendar",
    accent: "orange",
    prompt: "Show all events in the database",
    action: "View saved events",
  },
  {
    id: "recovery",
    title: "Recovery support",
    description: "Reflect on triggers, urges and progress with practical, non-judgemental support.",
    icon: "heart",
    accent: "peach",
    prompt: "Help me track my recovery progress",
    action: "Open recovery support",
  },
  {
    id: "behaviour",
    title: "Behaviour insights",
    description: "Review routines and productivity from real activity logs, not guessed statistics.",
    icon: "brain",
    accent: "champagne",
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
    case "shield":
      return <svg {...common}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /><path d="m9 12 2 2 4-4" /></svg>;
    case "send":
      return <svg {...common}><path d="m21 3-7.2 18-3.8-7-7-3.8L21 3Z" /><path d="M10 14 21 3" /></svg>;
    case "refresh":
      return <svg {...common}><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.6 9A7 7 0 0 1 18 6l2 1M4 17l2 1a7 7 0 0 0 12.4-3" /></svg>;
    case "chevron":
      return <svg {...common}><path d="m9 18 6-6-6-6" /></svg>;
    default:
      return null;
  }
}

function getPageHeading(section: Section) {
  const headings: Record<Section, { title: string; description: string }> = {
    overview: {
      title: "Make room for what matters.",
      description: "Your personal workspace for staying organised, intentional and in control.",
    },
    assistant: {
      title: "Your assistant, in focus.",
      description: "A specialised assistant for the areas you choose to manage.",
    },
    budget: {
      title: "Budget audit",
      description: "Review real income and spending figures. No estimates or invented transactions.",
    },
    academics: {
      title: "Assignment workspace",
      description: "Bring your coursework, submission dates and study priorities into one place.",
    },
    events: {
      title: "Event planner",
      description: "Keep event details organised and retrieve only the events actually saved.",
    },
    recovery: {
      title: "Recovery support",
      description: "A private, supportive space to reflect on habits, triggers and progress.",
    },
    behaviour: {
      title: "Behaviour insights",
      description: "Understand your routines from information you provide, not assumptions.",
    },
  };
  return headings[section];
}

/* ---------------------------------------------------------------------
   Specular highlight: feeds the pointer position to CSS so a soft light
   follows the cursor across glass controls and cards.
   --------------------------------------------------------------------- */
function trackPointer(event: ReactPointerEvent<HTMLElement>) {
  const rect = event.currentTarget.getBoundingClientRect();
  event.currentTarget.style.setProperty("--mx", `${event.clientX - rect.left}px`);
  event.currentTarget.style.setProperty("--my", `${event.clientY - rect.top}px`);
}

/* ---------------------------------------------------------------------
   Real refraction (Chromium only, progressive enhancement).
   Generates a displacement map from the element's own rounded shape and
   feeds it to an SVG feDisplacementMap used as a backdrop-filter, so
   content scrolling underneath bends at the glass edge like a lens.
   Safari, Firefox and "reduce transparency" keep the plain frosted glass.
   --------------------------------------------------------------------- */
type LensMap = { src: string; width: number; height: number; scale: number };

function canRefract() {
  if (typeof window === "undefined") return false;
  const isChromium = /Chrome\//.test(navigator.userAgent);
  const reduced = window.matchMedia("(prefers-reduced-transparency: reduce)").matches;
  return isChromium && !reduced && CSS.supports("backdrop-filter", "url(#lens) blur(1px)");
}

function buildLensMap(width: number, height: number, radius: number, bezel: number, depth: number): LensMap | null {
  const w = Math.round(width);
  const h = Math.round(height);
  const k = w * h > 120_000 ? 0.5 : 1; // lower-resolution map for big elements
  const cw = Math.max(1, Math.round(w * k));
  const ch = Math.max(1, Math.round(h * k));

  const canvas = document.createElement("canvas");
  canvas.width = cw;
  canvas.height = ch;
  const context = canvas.getContext("2d");
  if (!context) return null;

  const image = context.createImageData(cw, ch);
  const halfW = w / 2;
  const halfH = h / 2;
  const r = Math.min(radius, halfW, halfH);
  const band = Math.min(bezel, halfW, halfH);

  for (let y = 0; y < ch; y++) {
    for (let x = 0; x < cw; x++) {
      const cx = (x + 0.5) / k - halfW;
      const cy = (y + 0.5) / k - halfH;
      const qx = Math.abs(cx) - (halfW - r);
      const qy = Math.abs(cy) - (halfH - r);
      const ox = Math.max(qx, 0);
      const oy = Math.max(qy, 0);
      const outside = Math.hypot(ox, oy);
      const inset = r - (outside + Math.min(Math.max(qx, qy), 0)); // distance in from the edge

      let dx = 0;
      let dy = 0;
      if (inset < band) {
        const strength = (1 - Math.max(inset, 0) / band) ** 2; // strongest at the very edge
        let nx = 0;
        let ny = 0;
        if (outside > 0) {
          nx = (Math.sign(cx) * ox) / outside;
          ny = (Math.sign(cy) * oy) / outside;
        } else if (qx > qy) {
          nx = Math.sign(cx);
        } else {
          ny = Math.sign(cy);
        }
        dx = -nx * strength; // sample from further inside the glass
        dy = -ny * strength;
      }

      const i = (y * cw + x) * 4;
      image.data[i] = Math.round(127.5 + dx * 127.5);
      image.data[i + 1] = Math.round(127.5 + dy * 127.5);
      image.data[i + 2] = 128;
      image.data[i + 3] = 255;
    }
  }

  context.putImageData(image, 0, 0);
  return { src: canvas.toDataURL(), width: w, height: h, scale: depth * 2 };
}

function useLiquidLens<T extends HTMLElement>(bezel: number, depth: number) {
  const ref = useRef<T>(null);
  const rawId = useId();
  const id = `lens${rawId.replace(/[^a-zA-Z0-9]/g, "")}`;
  const [map, setMap] = useState<LensMap | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element || !canRefract()) return;

    let frame = 0;
    const rebuild = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const { width, height } = element.getBoundingClientRect();
        if (width < 8 || height < 8) return;
        const radius = parseFloat(getComputedStyle(element).borderTopLeftRadius) || 0;
        setMap(buildLensMap(width, height, radius, bezel, depth));
      });
    };

    const observer = new ResizeObserver(rebuild);
    observer.observe(element);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [bezel, depth]);

  const style: CSSProperties | undefined = map
    ? { backdropFilter: `url(#${id}) blur(6px) saturate(190%) brightness(1.08)` }
    : undefined;

  const defs = map ? (
    <svg className="lens-defs" width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <filter id={id} filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB" x={0} y={0} width={map.width} height={map.height}>
          <feImage href={map.src} x={0} y={0} width={map.width} height={map.height} preserveAspectRatio="none" result="map" />
          <feDisplacementMap in="SourceGraphic" in2="map" scale={map.scale} xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </defs>
    </svg>
  ) : null;

  return { ref, style, defs };
}

/* Floating chat composer: a glass control that messages scroll underneath. */
function ChatComposer({
  value,
  onChange,
  onSubmit,
  loading,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
}) {
  const lens = useLiquidLens<HTMLFormElement>(16, 10);

  return (
    <form
      ref={lens.ref}
      className="composer floating glass"
      style={lens.style}
      onPointerMove={trackPointer}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      {lens.defs}
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder="Message JARVIS…" aria-label="Message JARVIS" disabled={loading} />
      <button type="submit" disabled={loading || !value.trim()} aria-label="Send message"><Icon name="send" size={17} /></button>
    </form>
  );
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

  const sidebarLens = useLiquidLens<HTMLElement>(22, 14);
  const topbarLens = useLiquidLens<HTMLElement>(18, 10);

  // Read the current date only in the browser. Next.js 16 prerenders
  // Client Components on the server, so Date must not be read during render.
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setCurrentDate(
        new Intl.DateTimeFormat("en-IN", {
          weekday: "long",
          day: "numeric",
          month: "long",
        }).format(new Date())
      );
    });

    return () => window.cancelAnimationFrame(frame);
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
  const activeIndex = Math.max(0, navItems.findIndex((item) => item.id === activeSection));

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
      <div className="backdrop" aria-hidden="true">
        <div className="blob blob-a" />
        <div className="blob blob-b" />
        <div className="blob blob-c" />
      </div>

      {/* Glass layer 1: navigation (sidebar on desktop, floating dock on phones) */}
      <aside ref={sidebarLens.ref} className="sidebar glass" style={sidebarLens.style} onPointerMove={trackPointer}>
        {sidebarLens.defs}
        <button className="brand" onClick={() => setActiveSection("overview")} aria-label="JARVIS overview">
          <span className="brand-mark"><Image src="/app-logo.png" alt="" width={42} height={42} /></span>
          <span className="brand-name">JARVIS<small>1B</small></span>
        </button>
        <nav className="nav" aria-label="Main navigation" style={{ "--i": activeIndex, "--n": navItems.length } as CSSProperties}>
          <span className="nav-lens" aria-hidden="true" />
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activeSection === item.id ? "active" : ""}`}
              onClick={() => { setActiveSection(item.id); setNotice(""); }}
              aria-current={activeSection === item.id ? "page" : undefined}
              aria-label={item.label}
              title={item.label}
            >
              <Icon name={item.icon} size={19} />
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <div className="main">
        {/* Glass layer 2: top bar that page content scrolls underneath */}
        <header ref={topbarLens.ref} className="topbar glass" style={topbarLens.style} onPointerMove={trackPointer}>
          {topbarLens.defs}
          <div className="topbar-left">
            <span className="topbar-title">{navItems[activeIndex].label}</span>
            <span className="topbar-date">{currentDate || "Your workspace"}</span>
          </div>
          <div className="topbar-right">
            <span className="pill"><span className={`dot ${backendStatus}`} />{statusText}</span>
            <span className="avatar" aria-label="Local workspace">P</span>
          </div>
        </header>

        <section className="content">
          <div className="heading">
            <div>
              <h1>{pageHeading.title}</h1>
              <p>{pageHeading.description}</p>
            </div>
            {activeSection === "assistant" && messages.length > 0 && (
              <button className="soft-button" onClick={() => void resetConversation()} disabled={loading}>
                <Icon name="refresh" size={15} /> New conversation
              </button>
            )}
          </div>

          {notice && <div className="notice" role="status">{notice}</div>}

          {activeSection === "overview" && (
            <>
              <section className="hero surface">
                <div className="hero-copy">
                  <h2>What would you like to organise?</h2>
                  <p>Ask in plain words. JARVIS only uses the details you share.</p>
                  <form className="field" onSubmit={(event) => { event.preventDefault(); void sendMessage(); }}>
                    <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask about budgets, assignments, events…" aria-label="Message JARVIS" />
                    <button type="submit" disabled={!input.trim() || loading} aria-label="Send message"><Icon name="send" size={17} /></button>
                  </form>
                  <div className="chips">
                    {quickPrompts.map((prompt) => (
                      <button key={prompt} onClick={() => startModulePrompt(prompt)}>{prompt}</button>
                    ))}
                  </div>
                </div>
                <div className="hero-art" aria-hidden="true">
                  <span className="hero-orb lg" />
                  <span className="hero-orb sm" />
                </div>
              </section>

              <h2 className="section-title">Focus areas</h2>
              <section className="cards">
                {moduleCards.map((module) => (
                  <button
                    className={`card surface accent-${module.accent}`}
                    key={module.id}
                    onClick={() => openModule(module.id)}
                    onPointerMove={trackPointer}
                  >
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
              <div className="chat surface">
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
                <span className="scroll-edge" aria-hidden="true" />
                {/* Glass layer 3: the composer floats over the messages */}
                <ChatComposer value={input} onChange={setInput} onSubmit={() => void sendMessage()} loading={loading} />
              </div>
            </section>
          )}

          {selectedModule && (
            <section className={`workspace surface accent-${selectedModule.accent}`}>
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