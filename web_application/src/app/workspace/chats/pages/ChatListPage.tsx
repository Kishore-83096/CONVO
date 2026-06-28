import { RefreshCcw, Search } from "lucide-react"

import type { ChatSummary } from "@/app/workspace/chats/chats.api"

interface ChatListPageProps {
  chats: ChatSummary[]
  errorMessage: string
  isLoading: boolean
  selectedChatId: string | null
  onOpenChat: (chat: ChatSummary) => void
  onRefresh: () => void
}

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
}

function ChatListPage({
  chats,
  errorMessage,
  isLoading,
  selectedChatId,
  onOpenChat,
  onRefresh,
}: ChatListPageProps) {
  return (
    <section className="sidebar-view active" aria-label="Chats tab">
      <div className="sidebar-view-heading">
        <div>
          <span className="section-kicker">Messages</span>
        </div>
        <button
          className="sidebar-action-button chat-refresh-button"
          type="button"
          aria-label="Refresh chats"
          title="Refresh chats"
          disabled={isLoading}
          onClick={onRefresh}
        >
          <RefreshCcw aria-hidden="true" />
        </button>
      </div>

      <label className="search-bar" htmlFor="chatSearch">
        <Search aria-hidden="true" />
        <input id="chatSearch" type="search" placeholder="Search chats" />
      </label>

      <div className="sidebar-list">
        {isLoading ? (
          <p className="sidebar-state">Loading chats...</p>
        ) : errorMessage ? (
          <p className="sidebar-state" role="alert">{errorMessage}</p>
        ) : chats.length === 0 ? (
          <p className="sidebar-state">No conversations yet.</p>
        ) : chats.map((chat) => (
          <button
            className={`conversation-item ${
              selectedChatId === chat.id ? "selected" : ""
            }`}
            key={chat.id}
            type="button"
            onClick={() => onOpenChat(chat)}
          >
            {chat.profilePicture ? (
              <img
                className="list-avatar"
                src={chat.profilePicture.url}
                alt=""
                loading="lazy"
              />
            ) : (
              <span className="list-avatar">{initials(chat.name)}</span>
            )}
            <span className="list-content">
              <span className="list-top-row">
                <strong>{chat.name}</strong>
                <small>{chat.time}</small>
              </span>
              <span className="list-bottom-row">
                <span>{chat.lastMessage}</span>
              </span>
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}

export default ChatListPage
