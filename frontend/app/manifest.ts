import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "JARVIS 1B — Personal Assistant",
    short_name: "JARVIS 1B",
    description: "Your private personal management assistant.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#070b14",
    theme_color: "#0a1020",
    categories: ["productivity", "utilities"],
    icons: [
      { src: "/jarvis-icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/jarvis-icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/jarvis-icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
