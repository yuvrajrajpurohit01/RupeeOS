"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoMark, Wordmark } from "./Logo";
import { useStore } from "@/lib/store";

const STEPS = [
  { href: "/commerce", label: "Commerce", n: 1 },
  { href: "/risk", label: "Risk & Payment", n: 2 },
  { href: "/recovery", label: "Recovery", n: 3 },
  { href: "/finance", label: "Reconciliation", n: 4 },
  { href: "/command-center", label: "Command Center", n: 5 },
];

export function TopNav() {
  const pathname = usePathname();
  const { systemStatus, backendConnected } = useStore();

  return (
    <header className="sticky top-0 z-40 bg-white border-b" style={{ borderColor: "var(--rzp-border)" }}>
      <div className="max-w-[1400px] mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/commerce" className="flex items-center gap-2.5">
          <LogoMark />
          <Wordmark />
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {STEPS.map((step) => {
            const active = pathname === step.href;
            return (
              <Link
                key={step.href}
                href={step.href}
                className="flex items-center gap-2 px-3 py-2 rounded-[4px] text-sm font-medium transition-colors"
                style={{
                  color: active ? "var(--rzp-blue-dark)" : "var(--rzp-muted)",
                  background: active ? "var(--rzp-blue-tint)" : "transparent",
                }}
              >
                <span
                  className="flex items-center justify-center h-5 w-5 rounded-full text-[11px] font-bold"
                  style={{
                    background: active ? "var(--rzp-blue)" : "#e9edf2",
                    color: active ? "white" : "var(--rzp-muted)",
                  }}
                >
                  {step.n}
                </span>
                {step.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <span
            className="hidden sm:flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 rounded-[4px]"
            style={{
              background: !backendConnected || systemStatus.circuit_breaker_tripped ? "var(--rzp-danger-tint)" : "var(--rzp-success-tint)",
              color: !backendConnected || systemStatus.circuit_breaker_tripped ? "var(--rzp-danger)" : "var(--rzp-success)",
            }}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${backendConnected && !systemStatus.circuit_breaker_tripped ? "pulse-dot" : ""}`}
              style={{ background: "currentColor" }}
            />
            {!backendConnected ? "Backend Offline" : systemStatus.circuit_breaker_tripped ? "Circuit Breaker Tripped" : "System Normal"}
          </span>
        </div>
      </div>
    </header>
  );
}
