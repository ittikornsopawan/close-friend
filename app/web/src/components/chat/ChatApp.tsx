"use client";

import { useState } from "react";

import { usePersonas } from "@/hooks/usePersonas";

import { ChatWindow } from "./ChatWindow";
import { Sidebar } from "./Sidebar";

export function ChatApp() {
  const { personas, isLoading, error } = usePersonas();
  const [activePersonaId, setActivePersonaId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm text-zinc-400">
        Loading personas…
      </div>
    );
  }

  if (error || personas.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm text-zinc-400">
        {error ?? "No personas available."}
      </div>
    );
  }

  const activePersona = personas.find((persona) => persona.id === activePersonaId) ?? personas[0];

  return (
    <div className="flex h-full w-full overflow-hidden">
      <Sidebar
        personas={personas}
        activePersonaId={activePersona.id}
        onSelectPersona={setActivePersonaId}
      />
      <ChatWindow persona={activePersona} />
    </div>
  );
}
