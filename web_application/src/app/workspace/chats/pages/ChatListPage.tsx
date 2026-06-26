import { Search } from "lucide-react"

import type { ChatSummary } from "@/app/workspace/chats/chats.api"

interface ChatListPageProps {
  chats: ChatSummary[]
  selectedChatId: string | null
  onOpenChat: (chat: ChatSummary) => void
}

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
}

function ChatListPage({ chats, selectedChatId, onOpenChat }: ChatListPageProps) {
  return (
    <section className="sidebar-view active" aria-label="Chats tab">
      <div className="sidebar-view-heading">
        <div>
          <span className="section-kicker">Chat API</span>
          <h2>Chats</h2>
        </div>
      </div>

      <label className="search-bar" htmlFor="chatSearch">
        <Search aria-hidden="true" />
        <input id="chatSearch" type="search" placeholder="Search chats" />
      </label>

      <div className="sidebar-list">
        {chats.map((chat) => (
          <button
            className={`conversation-item ${
              selectedChatId === chat.id ? "selected" : ""
            }`}
            key={chat.id}
            type="button"
            onClick={() => onOpenChat(chat)}
          >
            <span className="list-avatar">{initials(chat.name)}</span>
            <span className="list-content">
              <span className="list-top-row">
                <strong>{chat.name}</strong>
                <small>{chat.time}</small>
              </span>
              <span className="list-bottom-row">
                <span>{chat.lastMessage}</span>
                {chat.unreadCount ? (
                  <span className="unread-count">{chat.unreadCount}</span>
                ) : null}
              </span>
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}

export default ChatListPage
