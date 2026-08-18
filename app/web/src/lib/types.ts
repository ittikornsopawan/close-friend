export type MessageRole = "user" | "assistant";
export type MessageStatus = "pending" | "complete" | "failed";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  status: MessageStatus;
  created_at: string;
}

// Narrow read-model — matches GET /personas exactly. The API deliberately
// never sends character/emotion_rules/boundaries to the client.
export interface Persona {
  id: string;
  name: string;
  tagline: string;
  avatar_initials: string;
  tags: string[];
}
