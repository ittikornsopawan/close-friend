"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getMessages, postMessage } from "@/lib/api-client";
import type { ChatMessage } from "@/lib/types";

const POLL_INTERVAL_MS = 1000;
// The persona graph makes 2 sequential LLM calls (assess + respond), each
// with its own 120s budget worst-case — up to ~4 minutes total. 150 * 1s
// covers that with room to spare (was 60, sized for the old single-call MVP).
const MAX_POLL_ATTEMPTS = 150;

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useConversation(conversationId: string) {
  const [trackedConversationId, setTrackedConversationId] = useState(conversationId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Always holds the *current* conversationId (updated in an effect, not
  // during render — React refs can't be written mid-render) so in-flight
  // async work (an initial load, a poll loop) started for a conversation
  // the user has since navigated away from can notice and stop writing
  // state, instead of a shared timer being cleared out from under an
  // unrelated poll loop, which previously could leave a message stuck
  // showing "typing…" forever.
  const conversationIdRef = useRef(conversationId);
  useEffect(() => {
    conversationIdRef.current = conversationId;
  });

  // Reset conversation-scoped state during render when the prop changes,
  // rather than in an effect — avoids a synchronous setState-in-effect and
  // the extra render it would otherwise cause.
  if (conversationId !== trackedConversationId) {
    setTrackedConversationId(conversationId);
    setMessages([]);
    setError(null);
  }

  const loadMessages = useCallback(async (forId: string): Promise<ChatMessage[]> => {
    try {
      const loaded = await getMessages(forId);
      if (conversationIdRef.current === forId) {
        setMessages(loaded);
        setError(null);
      }
      return loaded;
    } catch {
      if (conversationIdRef.current === forId) {
        setError("Couldn't load messages.");
      }
      return [];
    }
  }, []);

  const pollUntilResolved = useCallback(
    async (forId: string) => {
      for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt++) {
        await wait(POLL_INTERVAL_MS);
        if (conversationIdRef.current !== forId) return;
        const loaded = await loadMessages(forId);
        if (conversationIdRef.current !== forId) return;
        const stillPending = loaded.some((message) => message.status === "pending");
        if (!stillPending) return;
      }
    },
    [loadMessages],
  );

  // Inline fetch (not routed through the loadMessages/pollUntilResolved
  // helpers) so the effect body itself never calls a function that sets
  // state — keeps this a plain "fetch on dependency change" effect.
  useEffect(() => {
    let cancelled = false;
    getMessages(conversationId)
      .then((loaded) => {
        if (cancelled) return;
        setMessages(loaded);
        setError(null);
        if (loaded.some((message) => message.status === "pending")) {
          pollUntilResolved(conversationId);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Couldn't load messages.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [conversationId, pollUntilResolved]);

  const sendMessage = useCallback(
    async (content: string) => {
      const forId = conversationId;
      setIsSending(true);
      setError(null);
      try {
        const { user_message, assistant_message } = await postMessage(forId, content);
        if (conversationIdRef.current === forId) {
          setMessages((prev) => [...prev, user_message, assistant_message]);
        }
        pollUntilResolved(forId);
      } catch {
        if (conversationIdRef.current === forId) {
          setError("Couldn't send message.");
        }
      } finally {
        if (conversationIdRef.current === forId) {
          setIsSending(false);
        }
      }
    },
    [conversationId, pollUntilResolved],
  );

  return { messages, sendMessage, isSending, error };
}
