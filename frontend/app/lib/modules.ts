// Single source of truth for every sidebar module.
// Each module gets its own chat instance, draft, loading state, error state and
// backend thread. Nothing in the UI is shared between modules except this list.

export type ModuleId =
  | "overview"
  | "assistant"
  | "budget"
  | "academics"
  | "events"
  | "recovery"
  | "behaviour";

export type IconName =
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

export type Accent = "yellow" | "gold" | "orange" | "peach" | "champagne";

export type ModuleDef = {
  id: ModuleId;
  /** id the backend uses for this module (change if your API calls it something else) */
  apiId: string;
  /** sidebar + top bar label */
  label: string;
  /** big page heading */
  title: string;
  /** sentence under the heading */
  description: string;
  /** short text on the Overview focus card */
  cardText: string;
  icon: IconName;
  accent: Accent;
  /** composer placeholder */
  placeholder: string;
  /** empty-chat state */
  welcome: { heading: string; body: string };
  /** quick prompt chips on the empty chat */
  prompts: string[];
};

export const MODULES: ModuleDef[] = [
  {
    id: "overview",
    apiId: "overview",
    label: "Overview",
    title: "Make room for what matters.",
    description: "Your personal workspace for staying organised, intentional and in control.",
    cardText: "",
    icon: "grid",
    accent: "gold",
    placeholder: "Ask about your day, pending deadlines, or an executive summary…",
    welcome: {
      heading: "How can I help today?",
      body: "Ask for a briefing on your day. This conversation only uses your overview data.",
    },
    prompts: ["Give me an executive briefing", "What needs my attention today?"],
  },
  {
    id: "assistant",
    apiId: "assistant",
    label: "Assistant",
    title: "Your assistant, in focus.",
    description: "A specialised assistant for the areas you choose to manage.",
    cardText: "",
    icon: "message",
    accent: "gold",
    placeholder: "Message JARVIS…",
    welcome: {
      heading: "How can I help today?",
      body: "A general conversation with its own private memory. It does not see your other tabs.",
    },
    prompts: ["What can you help me with?", "Help me plan my day"],
  },
  {
    id: "budget",
    apiId: "budget",
    label: "Budget audit",
    title: "Budget audit",
    description: "Review real income and spending figures. No estimates or invented transactions.",
    cardText: "Income, expenses and monthly audits.",
    icon: "wallet",
    accent: "yellow",
    placeholder: "Ask about income, expenses or your monthly audit…",
    welcome: {
      heading: "Start with your figures",
      body: "This chat only sees your budget records and its own conversation.",
    },
    prompts: ["Audit my monthly budget", "Where did I spend the most?"],
  },
  {
    id: "academics",
    apiId: "academics",
    label: "Assignments",
    title: "Assignment workspace",
    description: "Bring your coursework, submission dates and study priorities into one place.",
    cardText: "Coursework, due dates and study priorities.",
    icon: "book",
    accent: "gold",
    placeholder: "Ask about assignments, deadlines or study priorities…",
    welcome: {
      heading: "Start with your coursework",
      body: "This chat only sees your assignment records and its own conversation.",
    },
    prompts: ["Check my pending assignments", "What is due this week?"],
  },
  {
    id: "events",
    apiId: "events",
    label: "Event planner",
    title: "Event planner",
    description: "Keep event details organised and retrieve only the events actually saved.",
    cardText: "Saved events, dates and logistics.",
    icon: "calendar",
    accent: "orange",
    placeholder: "Ask about saved events, dates or logistics…",
    welcome: {
      heading: "Start with your events",
      body: "This chat only sees your event records and its own conversation.",
    },
    prompts: ["Show all events in the database", "What is coming up next?"],
  },
  {
    id: "recovery",
    apiId: "recovery",
    label: "Recovery",
    title: "Recovery support",
    description: "A private, supportive space to reflect on habits, triggers and progress.",
    cardText: "Habit check-ins, urge logging, and reflections.",
    icon: "heart",
    accent: "peach",
    placeholder: "Share a check-in, an urge, or how today is going…",
    welcome: {
      heading: "A private space to reflect",
      body: "This chat only sees your recovery check-ins and its own conversation.",
    },
    prompts: ["Help me track my recovery progress", "Summarise my recent check-ins"],
  },
  {
    id: "behaviour",
    apiId: "behaviour",
    label: "Behaviour insights",
    title: "Behaviour insights",
    description: "Understand your routines from information you provide, not assumptions.",
    cardText: "Activity records, focus hours, and routines.",
    icon: "brain",
    accent: "champagne",
    placeholder: "Ask about your routines, focus hours or productivity…",
    welcome: {
      heading: "Start with your activity",
      body: "This chat only sees your activity logs and its own conversation.",
    },
    prompts: ["Analyse my daily productivity", "How many focus hours did I log?"],
  },
];

export const MODULE_BY_ID = Object.fromEntries(
  MODULES.map((module) => [module.id, module])
) as Record<ModuleId, ModuleDef>;

/** The five focus areas shown as cards on Overview. */
export const FOCUS_MODULES = MODULES.filter(
  (module) => module.id !== "overview" && module.id !== "assistant"
);
