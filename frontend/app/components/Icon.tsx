import type { IconName } from "../lib/modules";

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
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
