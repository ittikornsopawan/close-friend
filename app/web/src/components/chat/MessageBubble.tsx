import type { ChatMessage } from "@/lib/types";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-sm rounded-2xl px-4 py-2 text-sm ${
          isUser ? "bg-blue-600 text-white" : "bg-white text-zinc-900 dark:bg-zinc-800 dark:text-zinc-50"
        } ${message.status === "failed" ? "border border-red-400" : ""}`}
      >
        {message.status === "pending" ? (
          <span className="italic text-zinc-400">typing…</span>
        ) : (
          message.content
        )}
      </div>
    </div>
  );
}
