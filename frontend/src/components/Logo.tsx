export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="7" fill="var(--rzp-blue)" />
      <path
        d="M11 8H19.5C22 8 24 10 24 12.5C24 14.6 22.6 16.3 20.7 16.8L24.5 24H20.8L17.3 17.2H14.4V24H11V8ZM14.4 11V14.2H19C20.1 14.2 21 13.3 21 12.1C21 10.9 20.1 11 19 11H14.4Z"
        fill="white"
      />
    </svg>
  );
}

export function Wordmark({ size = 18 }: { size?: number }) {
  return (
    <span
      style={{ fontSize: size, fontWeight: 800, letterSpacing: "-0.02em", color: "var(--rzp-navy)" }}
    >
      Rupee<span style={{ color: "var(--rzp-blue)" }}>OS</span>
    </span>
  );
}
