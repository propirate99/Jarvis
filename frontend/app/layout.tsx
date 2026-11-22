import type { Metadata, Viewport } from "next";
import { Instrument_Serif, Manrope } from "next/font/google";
import "./globals.css";

// UI text: clean geometric sans. Headlines: refined serif for the premium feel.
const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  title: "JARVIS",
  description: "Your personal JARVIS workspace",
  icons: {
    icon: "/app-logo.png",
  },
};

// Colours the browser bar / status bar to match the glass backdrop.
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0c0905" },
    { media: "(prefers-color-scheme: light)", color: "#fbf3e2" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${manrope.variable} ${instrumentSerif.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}