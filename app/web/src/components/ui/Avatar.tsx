interface AvatarProps {
  initials: string;
  size?: "sm" | "md";
  active?: boolean;
}

export function Avatar({ initials, size = "md", active = false }: AvatarProps) {
  const sizeClasses = size === "sm" ? "h-8 w-8 text-xs" : "h-10 w-10 text-sm";

  return (
    <span className="relative inline-flex shrink-0">
      <span
        className={`flex ${sizeClasses} shrink-0 items-center justify-center rounded-full bg-blue-600 font-semibold text-white`}
      >
        {initials}
      </span>
      {active && (
        <span className="absolute -bottom-0.5 -right-0.5 flex h-3 w-3">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex h-3 w-3 rounded-full border-2 border-white bg-emerald-500 dark:border-zinc-950" />
        </span>
      )}
    </span>
  );
}
