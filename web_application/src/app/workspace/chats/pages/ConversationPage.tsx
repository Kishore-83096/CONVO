import { MessageCircle, MoreVertical, Plus, SendHorizontal, X } from "lucide-react"

import type { ChatSummary } from "@/app/workspace/chats/chats.api"

interface ConversationPageProps {
  chat: ChatSummary
  onClose: () => void
}

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
}

function ConversationPage({ chat, onClose }: ConversationPageProps) {
  return (
    <section className="main-view conversation-view active">
      <header className="conversation-header">
        <div className="conversation-user">
          <span className="conversation-avatar">{initials(chat.name)}</span>
          <div className="conversation-user-text">
            <h2>{chat.name}</h2>
            <p>{chat.status}</p>
          </div>
        </div>

        <nav className="conversation-header-actions">
          <button className="main-icon-button" type="button" aria-label="Contact actions">
            <MoreVertical aria-hidden="true" />
          </button>
          <button
            className="main-icon-button close-conversation-button"
            type="button"
            aria-label="Close conversation"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </button>
        </nav>
      </header>

      <div className="messages-area">
        <div className="message-row received-message-row">
          <div className="message-bubble received-message">
            <p>{chat.lastMessage}</p>
            <time>{chat.time}</time>
          </div>
        </div>
        <div className="message-row sent-message-row">
          <div className="message-bubble sent-message">
            <p>The layout is now a React shell. Message API wiring can plug in here.</p>
            <time>Now</time>
          </div>
        </div>
      </div>

      <footer className="message-composer">
        <button className="composer-icon-button" type="button" aria-label="Attach">
          <Plus aria-hidden="true" />
        </button>
        <label className="message-input-area" htmlFor="messageInput">
          <MessageCircle aria-hidden="true" />
          <input id="messageInput" type="text" placeholder="Type a message" />
        </label>
        <button className="composer-icon-button send-button" type="button" aria-label="Send">
          <SendHorizontal aria-hidden="true" />
        </button>
      </footer>
    </section>
  )
}

export default ConversationPage
