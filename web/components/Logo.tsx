export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <circle cx="16" cy="16" r="13" fill="none" stroke="var(--ink)" strokeWidth="1" opacity="0.35" />
      <circle cx="16" cy="16" r="9.5" fill="none" stroke="var(--s1)" strokeWidth="2.5" />
      <circle cx="16" cy="16" r="5.5" fill="var(--signal)" />
      <circle cx="16" cy="16" r="2" fill="var(--surface)" />
      <path d="M16 1v4M16 27v4M1 16h4M27 16h4" stroke="var(--ink)" strokeWidth="1" opacity="0.5" />
    </svg>
  );
}
