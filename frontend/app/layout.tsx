import "./globals.css";

import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";
import { AppNavTabs } from "@/components/navigation/AppNavTabs";
import { PWARegister } from "@/components/pwa/PWARegister";
import { cn } from "@/lib/utils/cn";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const manrope = Manrope({ subsets: ["latin"], variable: "--font-display" });

export const metadata: Metadata = {
  title: "Assistive Mirror",
  description: "Accessible smart mirror companion with AR guidance, CV, and coaching HUD.",
  manifest: "/manifest.webmanifest",
  themeColor: "#0F172A",
  icons: {
    icon: "/icons/icon-192.svg",
    apple: "/icons/icon-192.svg"
  }
};

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" suppressHydrationWarning className={cn(inter.variable, manrope.variable)}>
      <body className="min-h-screen bg-background text-foreground">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 rounded-md bg-accent px-4 py-2 text-accent-foreground"
        >
          Skip to content
        </a>
        <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-xl">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-6 py-6">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">Assistive Mirror</p>
                <h1 className="font-display text-3xl font-semibold md:text-4xl">Healthcare Coaching Companion</h1>
              </div>
              <p className="max-w-sm text-sm text-muted-foreground md:text-right">
                Browser-first backup experience for the smart mirror — optimized for patients, clinicians, and
                accessible coaching workflows.
              </p>
            </div>
            <AppNavTabs />
          </div>
        </header>
        <main id="main-content" className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-10 px-6 py-10">
          {children}
        </main>
        <PWARegister />
      </body>
    </html>
  );
}
