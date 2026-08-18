"use client";

import { Avatar } from "@/components/ui/Avatar";
import { useConversation } from "@/hooks/useConversation";
import type { Persona } from "@/lib/types";

import { MessageInput } from "./MessageInput";
import { MessageList } from "./MessageList";

interface ChatWindowProps {
  persona: Persona;
}

export function ChatWindow({ persona }: ChatWindowProps) {
  const { messages, sendMessage, isSending, error } = useConversation(persona.id);

  return (
    <div className="flex min-w-0 flex-1 flex-col bg-zinc-50 dark:bg-black">
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-zinc-200 bg-white px-4 dark:border-zinc-800 dark:bg-zinc-950">
        <Avatar initials={persona.avatar_initials} size="sm" />
        <span className="font-semibold text-zinc-900 dark:text-zinc-50">{persona.name}</span>
      </div>
      <MessageList messages={messages} />
      {error && <p className="px-4 py-1 text-sm text-red-600 dark:text-red-400">{error}</p>}
      <MessageInput onSend={sendMessage} disabled={isSending} />
    </div>
  );
}
