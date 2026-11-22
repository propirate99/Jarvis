"use client";

import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import Image from "next/image";
import { Icon } from "./components/Icon";
import { ModuleChat } from "./components/ModuleChat";
import { trackPointer, useLiquidLens } from "./lib/glass";
import { checkHealth, useModuleChat } from "./lib/jarvis-chat";
import { FOCUS_MODULES, MODULES } from "./lib/modules";
import type { ModuleDef, ModuleId } from "./lib/modules";

/* One page per sidebar module. Each instance owns its own chat state through
   useModuleChat, so drafts, spinners, errors and resets never cross tabs.
   Pages stay mounted once opened (just hidden), so a reply that arrives while
   you are on another tab lands in the right place. */
function ModulePage({
  module,
  active,
  onOpen,
}: {
  module: ModuleDef;
  active: boolean;
  onOpen: (id: ModuleId) => void;
}) {
  const chat = useModuleChat(module.id, active);

  return (
    <section className="module-view" hidden={!active} aria-label={module.label}>
      <div className="heading">
        <div>
          <h1>{module.title}</h1>
          <p>{module.description}</p>
        </div>
        {chat.messages.length > 0 && (
          <button type="button" className="soft-button" onClick={() => void chat.reset()} disabled={chat.loading}>
            <Icon name="refresh" size={15} /> New conversation
          </button>
        )}
      </div>

      {chat.notice && <div className="notice" role="status">{chat.notice}</div>}

      {module.id === "overview" && (
        <>
          <h2 className="section-title">Focus areas</h2>
          <section className="cards">
            {FOCUS_MODULES.map((focus) => (
              <button
                type="button"
                className={`card surface accent-${focus.accent}`}
                key={focus.id}
                onClick={() => onOpen(focus.id)}
                onPointerMove={trackPointer}
              >
                <span className="card-icon"><Icon name={focus.icon} size={21} /></span>
                <h3>{focus.label}</h3>
                <p>{focus.cardText}</p>
                <span className="card-open">Open <Icon name="chevron" size={14} /></span>
              </button>
            ))}
          </section>
          <h2 className="section-title">Ask JARVIS</h2>
        </>
      )}

      <ModuleChat
        module={module}
        messages={chat.messages}
        draft={chat.draft}
        loading={chat.loading}
        error={chat.error}
        onDraftChange={chat.setDraft}
        onSend={(text) => void chat.send(text)}
      />

      <p className="principle">
        <Icon name="shield" size={15} />
        Your records are the source of truth. Each tab keeps its own conversation memory, so nothing carries over between them.
      </p>
    </section>
  );
}

export default function Home() {
  console.log("=== HOME COMPONENT EXECUTING ===");
  const [activeId, setActiveId] = useState<ModuleId>("overview");
  const [visited, setVisited] = useState<ModuleId[]>(["overview"]);
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");
  const [currentDate, setCurrentDate] = useState("");

  const sidebarLens = useLiquidLens<HTMLElement>(22, 14);
  const topbarLens = useLiquidLens<HTMLElement>(18, 10);

  // Read the current date only in the browser. Next.js prerenders Client
  // Components on the server, so Date must not be read during render.
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setCurrentDate(
        new Intl.DateTimeFormat("en-IN", { weekday: "long", day: "numeric", month: "long" }).format(new Date())
      );
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    let mounted = true;

    async function verify() {
      try {
        await checkHealth();
        if (mounted) setBackendStatus("online");
      } catch {
        if (mounted) setBackendStatus("offline");
      }
    }

    verify();
    const interval = setInterval(verify, 8000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  function handleRetryConnection() {
    setBackendStatus("checking");
    checkHealth()
      .then(() => setBackendStatus("online"))
      .catch(() => setBackendStatus("offline"));
  }

  function open(id: ModuleId) {
    setActiveId(id);
    setVisited((previous) => (previous.includes(id) ? previous : [...previous, id]));
    window.scrollTo({ top: 0 });
  }

  const activeIndex = Math.max(0, MODULES.findIndex((module) => module.id === activeId));
  const statusText = backendStatus === "online" ? "Local AI ready" : backendStatus === "checking" ? "Connecting" : "Offline";

  return (
    <main className="app">
      <div className="backdrop" aria-hidden="true">
        <div className="blob blob-a" />
        <div className="blob blob-b" />
        <div className="blob blob-c" />
      </div>

      {/* Glass: navigation (sidebar on desktop, floating dock on phones) */}
      <aside ref={sidebarLens.ref} className="sidebar glass" style={sidebarLens.style} onPointerMove={trackPointer}>
        {sidebarLens.defs}
        <button type="button" className="brand" onClick={() => open("overview")} aria-label="JARVIS overview">
          <span className="brand-mark"><Image src="/app-logo.png" alt="" width={42} height={42} /></span>
          <span className="brand-name">JARVIS<small>1B</small></span>
        </button>
        <nav className="nav" aria-label="Main navigation" style={{ "--i": activeIndex, "--n": MODULES.length } as CSSProperties}>
          <span className="nav-lens" aria-hidden="true" />
          {MODULES.map((module) => (
            <button
              type="button"
              key={module.id}
              className={`nav-item ${activeId === module.id ? "active" : ""}`}
              onClick={() => open(module.id)}
              aria-current={activeId === module.id ? "page" : undefined}
              aria-label={module.label}
              title={module.label}
            >
              <Icon name={module.icon} size={19} />
              <span className="nav-label">{module.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <div className="main">
        {/* Glass: top bar that page content scrolls underneath */}
        <header ref={topbarLens.ref} className="topbar glass" style={topbarLens.style} onPointerMove={trackPointer}>
          {topbarLens.defs}
          <div className="topbar-left">
            <span className="topbar-title">{MODULES[activeIndex].label}</span>
            <span className="topbar-date">{currentDate || "Your workspace"}</span>
          </div>
          <div className="topbar-right">
            <button
              type="button"
              className="pill"
              onClick={handleRetryConnection}
              title="Click to refresh connection status"
              aria-label={`Server status: ${statusText}. Click to refresh.`}
            >
              <span className={`dot ${backendStatus}`} />{statusText}
            </button>
            <span className="avatar" aria-label="Local workspace">P</span>
          </div>
        </header>

        <section className="content">
          {MODULES.filter((module) => visited.includes(module.id)).map((module) => (
            <ModulePage key={module.id} module={module} active={module.id === activeId} onOpen={open} />
          ))}
        </section>
      </div>
    </main>
  );
}
