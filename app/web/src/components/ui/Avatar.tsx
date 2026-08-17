interface AvatarProps {
  initials: string;
  size?: "sm" | "md";
}

export function Avatar({ initials, size = "md" }: AvatarProps) {
  const sizeClasses = size === "sm" ? "h-8 w-8 text-xs" : "h-10 w-10 text-sm";

  return (
    <span
      className={`flex ${sizeClasses} shrink-0 items-center justify-center rounded-full bg-blue-600 font-semibold text-white`}
    >
      {initials}
    </span>
  );
}
