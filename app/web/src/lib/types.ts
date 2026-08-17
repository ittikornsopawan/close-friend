export type MessageRole = "user" | "assistant";
export type MessageStatus = "pending" | "complete" | "failed";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  status: MessageStatus;
  created_at: string;
}
