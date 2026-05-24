import type { Metadata, Viewport } from "next";
import { Syne, DM_Sans, JetBrains_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { Toaster } from "sonner";
import { Providers } from "@/components/layout/providers";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  display: "swap",
  weight: ["400", "500", "600", "700", "800"],
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
  weight: ["300", "400", "500", "600"],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: {
    default: "MeetingMind AI",
    template: "%s · MeetingMind",
  },
  description:
    "AI-powered meeting transcription, speaker analysis, MoM generation and smart meeting assistant.",
  keywords: ["meeting", "transcription", "AI", "minutes", "diarization", "summary"],
  authors: [{ name: "MeetingMind" }],
  creator: "MeetingMind AI",
  openGraph: {
    type: "website",
    title: "MeetingMind AI",
    description: "Turn every meeting into actionable intelligence.",
    siteName: "MeetingMind AI",
  },
};

export const viewport: Viewport = {
  themeColor: "#0d0d26",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <html
        lang="en"
        suppressHydrationWarning
        className={`${syne.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}
      >
        <body className="min-h-screen bg-background font-body antialiased">
          <Providers>{children}</Providers>
          <Toaster
            theme="dark"
            position="top-right"
            toastOptions={{
              style: {
                background: "hsl(225 28% 9%)",
                border: "1px solid hsl(224 22% 16%)",
                color: "hsl(220 20% 92%)",
              },
            }}
          />
        </body>
      </html>
    </ClerkProvider>
  );
}
