import { Avatar } from "@/components/ui/Avatar";
import type { Contact } from "@/lib/contacts";

interface ContactListItemProps {
  contact: Contact;
  isActive: boolean;
  onSelect: () => void;
}

export function ContactListItem({ contact, isActive, onSelect }: ContactListItemProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex w-full items-center gap-3 px-4 py-3 text-left transition-colors ${
        isActive ? "bg-blue-50 dark:bg-blue-950/40" : "hover:bg-zinc-50 dark:hover:bg-zinc-900"
      }`}
    >
      <Avatar initials={contact.initials} />
      <span className="truncate font-medium text-zinc-900 dark:text-zinc-50">{contact.name}</span>
    </button>
  );
}
