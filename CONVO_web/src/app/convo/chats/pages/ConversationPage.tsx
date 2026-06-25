import type { ChatSummary } from "@/app/convo/chats/chats.api"

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
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="5" r="1" />
              <circle cx="12" cy="12" r="1" />
              <circle cx="12" cy="19" r="1" />
            </svg>
          </button>
          <button
            className="main-icon-button close-conversation-button"
            type="button"
            aria-label="Close conversation"
            onClick={onClose}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6L18 18" />
              <path d="M18 6L6 18" />
            </svg>
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
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 5V19" />
            <path d="M5 12H19" />
          </svg>
        </button>
        <label className="message-input-area" htmlFor="messageInput">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 5H20V16H9L4 20V5Z" />
          </svg>
          <input id="messageInput" type="text" placeholder="Type a message" />
        </label>
        <button className="composer-icon-button send-button" type="button" aria-label="Send">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3 4L21 12L3 20L6 12L3 4Z" />
            <path d="M6 12H21" />
          </svg>
        </button>
      </footer>
    </section>
  )
}

export default ConversationPage
