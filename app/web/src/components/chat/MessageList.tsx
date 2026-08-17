"use client";

import { useEffect, useRef } from "react";

import type { ChatMessage } from "@/lib/types";

import { MessageBubble } from "./MessageBubble";

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 space-y-2 overflow-y-auto px-4 py-4">
      {messages.length === 0 ? (
        <p className="mt-8 text-center text-sm text-zinc-400">Say hello to start the conversation.</p>
      ) : (
        messages.map((message) => <MessageBubble key={message.id} message={message} />)
      )}
      <div ref={bottomRef} />
    </div>
  );
}
