"use client";

import { useEffect, useRef } from "react";
import { Icon } from "./Icon";
import { trackPointer, useLiquidLens } from "../lib/glass";
import type { ChatMessage } from "../lib/jarvis-chat";
import type { ModuleDef } from "../lib/modules";

const clock = new Intl.DateTimeFormat("en-IN", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

function formatTime(iso: string) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : clock.format(date);
}

/* The text bar. It floats at the bottom of ITS OWN chat panel (.chat is
   position: relative), so it can never spill over the sidebar. */
function Composer({
  value,
  placeholder,
  loading,
  onChange,
  onSubmit,
}: {
  value: string;
  placeholder: string;
  loading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
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
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        autoComplete="off"
        enterKeyHint="send"
        disabled={loading}
      />
      <button type="submit" disabled={loading || !value.trim()} aria-label="Send message">
        <Icon name="send" size={17} />
      </button>
    </form>
  );
}

export function ModuleChat({
  module,
  messages,
  draft,
  loading,
  error,
  onDraftChange,
  onSend,
}: {
  module: ModuleDef;
  messages: ChatMessage[];
  draft: string;
  loading: boolean;
  error: string;
  onDraftChange: (value: string) => void;
  onSend: (text?: string) => void;
}) {
  const threadRef = useRef<HTMLDivElement>(null);

  // Scroll the thread itself, never the page.
  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTo({ top: thread.scrollHeight, behavior: "smooth" });
  }, [messages.length, loading]);

  return (
    <div className="chat surface" data-module={module.id}>
      {messages.length === 0 ? (
        <div className="welcome">
          <span className="orb big"><Icon name="spark" size={26} /></span>
          <h2>{module.welcome.heading}</h2>
          <p>{module.welcome.body}</p>
          <div className="chips center">
            {module.prompts.map((prompt) => (
              <button key={prompt} type="button" onClick={() => onSend(prompt)} disabled={loading}>
                {prompt}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="thread" ref={threadRef} role="log" aria-live="polite" aria-label={`${module.label} conversation`}>
          {messages.map((message) => {
            const time = formatTime(message.createdAt);
            return (
              <div className={`row ${message.role}`} key={message.id}>
                {message.role === "assistant" && <span className="mini-avatar"><Icon name="spark" size={14} /></span>}
                <div className="bubble">
                  <p className="bubble-text">{message.content}</p>
                  {time && <time className="bubble-time" dateTime={message.createdAt}>{time}</time>}
                </div>
                {message.role === "user" && <span className="mini-avatar user">P</span>}
              </div>
            );
          })}
          {loading && messages[messages.length - 1]?.role !== "assistant" && (
            <div className="row assistant">
              <span className="mini-avatar"><Icon name="spark" size={14} /></span>
              <div className="bubble typing"><i /><i /><i /><span>Thinking locally</span></div>
            </div>
          )}
        </div>
      )}

      <span className="scroll-edge" aria-hidden="true" />
      {error && <div className="chat-error" role="alert">{error}</div>}
      <Composer
        value={draft}
        placeholder={module.placeholder}
        loading={loading}
        onChange={onDraftChange}
        onSubmit={() => onSend()}
      />
    </div>
  );
}
