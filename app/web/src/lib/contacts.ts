export interface Contact {
  id: string;
  name: string;
  initials: string;
}

// Hardcoded for now — no persona system exists yet, so every contact talks to
// the same generic assistant. `id` doubles as the Redis conversation_id, so
// each contact still gets its own separate message history.
export const CONTACTS: Contact[] = [
  { id: "general", name: "Assistant", initials: "A" },
  { id: "nova", name: "Nova", initials: "N" },
  { id: "kai", name: "Kai", initials: "K" },
];
