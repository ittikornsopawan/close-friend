import type { ChatMessage, Persona } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getPersonas(): Promise<Persona[]> {
  const res = await fetch(`${API_URL}/personas`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to load personas (${res.status})`);
  }
  const data: { personas: Persona[] } = await res.json();
  return data.personas;
}

export async function getMessages(conversationId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${API_URL}/conversations/${conversationId}/messages`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to load messages (${res.status})`);
  }
  const data: { messages: ChatMessage[] } = await res.json();
  return data.messages;
}

export async function postMessage(
  conversationId: string,
  content: string,
): Promise<{ user_message: ChatMessage; assistant_message: ChatMessage }> {
  const res = await fetch(`${API_URL}/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) {
    throw new Error(`Failed to send message (${res.status})`);
  }
  return res.json();
}
