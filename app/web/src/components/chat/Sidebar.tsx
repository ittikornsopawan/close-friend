import { CONTACTS } from "@/lib/contacts";

import { ContactListItem } from "./ContactListItem";

interface SidebarProps {
  activeContactId: string;
  onSelectContact: (id: string) => void;
}

export function Sidebar({ activeContactId, onSelectContact }: SidebarProps) {
  return (
    <aside className="flex w-80 shrink-0 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex h-16 shrink-0 items-center border-b border-zinc-200 px-4 dark:border-zinc-800">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Chats</h1>
      </div>
      <nav className="flex-1 overflow-y-auto">
        {CONTACTS.map((contact) => (
          <ContactListItem
            key={contact.id}
            contact={contact}
            isActive={contact.id === activeContactId}
            onSelect={() => onSelectContact(contact.id)}
          />
        ))}
      </nav>
    </aside>
  );
}
