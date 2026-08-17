export function TypingIndicator() {
  return (
    <span className="flex items-center gap-1 py-0.5" aria-label="typing">
      {[0, 1, 2].map((dot) => (
        <span
          key={dot}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 dark:bg-zinc-500"
          style={{ animationDelay: `${dot * 150}ms`, animationDuration: "900ms" }}
        />
      ))}
    </span>
  );
}
