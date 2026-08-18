import type { Persona } from "@/lib/types";

import { ContactListItem } from "./ContactListItem";

interface SidebarProps {
  personas: Persona[];
  activePersonaId: string;
  onSelectPersona: (id: string) => void;
}

export function Sidebar({ personas, activePersonaId, onSelectPersona }: SidebarProps) {
  return (
    <aside className="flex w-80 shrink-0 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex h-16 shrink-0 items-center border-b border-zinc-200 px-4 dark:border-zinc-800">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Chats</h1>
      </div>
      <nav className="flex-1 overflow-y-auto">
        {personas.map((persona) => (
          <ContactListItem
            key={persona.id}
            persona={persona}
            isActive={persona.id === activePersonaId}
            onSelect={() => onSelectPersona(persona.id)}
          />
        ))}
      </nav>
    </aside>
  );
}
