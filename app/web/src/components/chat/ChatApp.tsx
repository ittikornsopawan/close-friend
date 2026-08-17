"use client";

import { useState } from "react";

import { CONTACTS } from "@/lib/contacts";

import { ChatWindow } from "./ChatWindow";
import { Sidebar } from "./Sidebar";

export function ChatApp() {
  const [activeContactId, setActiveContactId] = useState(CONTACTS[0].id);
  const activeContact = CONTACTS.find((contact) => contact.id === activeContactId) ?? CONTACTS[0];

  return (
    <div className="flex h-full w-full overflow-hidden">
      <Sidebar activeContactId={activeContactId} onSelectContact={setActiveContactId} />
      <ChatWindow contact={activeContact} />
    </div>
  );
}
