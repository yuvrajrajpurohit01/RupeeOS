import type { Metadata } from "next";
import "./globals.css";
import { StoreProvider } from "@/lib/store";
import { TopNav } from "@/components/TopNav";

export const metadata: Metadata = {
  title: "RupeeOS — Autonomous Money Lifecycle",
  description: "AI recommends. Rules approve. Actions are logged.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full flex flex-col" style={{ background: "var(--rzp-canvas)" }}>
        <StoreProvider>
          <TopNav />
          <main className="flex-1">{children}</main>
        </StoreProvider>
      </body>
    </html>
  );
}
