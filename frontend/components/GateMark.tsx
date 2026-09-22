// A raised boom barrier — the literal mechanism a gatehouse operates. Static
// and monochrome by design: brand identity, not a status indicator, so it
// never competes with the four decision colors.
export function GateMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <rect x="3" y="10" width="3" height="11" rx="0.5" fill="currentColor" />
      <rect x="5.5" y="8.4" width="15" height="2.4" rx="1.2" transform="rotate(-24 5.5 8.4)" fill="currentColor" />
      <circle cx="19.2" cy="4.6" r="1.3" fill="currentColor" />
    </svg>
  );
}
