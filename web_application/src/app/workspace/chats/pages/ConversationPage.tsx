import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react"
import {
  MessageCircle,
  MoreVertical,
  RefreshCcw,
  SendHorizontal,
  X,
} from "lucide-react"

import type { ChatSummary } from "@/app/workspace/chats/chats.api"
import { getEncryptedHistory } from "@/messenger/api/history.api"
import { extractMissingEnvelopeDeviceIds } from "@/messenger/api/message-errors"
import { sendDirectMessage } from "@/messenger/api/messages.api"
import { MessengerApiError } from "@/messenger/api/messenger-client"
import { claimPreKeyBundles } from "@/messenger/api/prekey-bundles.api"
import {
  addDevDeviceSyncEnvelopes,
  createEncryptedDirectMessageRequest,
  createPublicDeviceRegistrationRequest,
  getStoredPublicDeviceRegistration,
  savePublicDeviceRegistration,
} from "@/messenger/crypto/device-registration"
import { registerMessengerDevice } from "@/messenger/api/devices.api"
import { decryptXChaCha20Poly1305History } from "@/messenger/e2ee/message-history"
import type { DecryptedHistoryMessage } from "@/messenger/e2ee/message-history"

interface ConversationPageProps {
  accessToken: string
  chat: ChatSummary
  onClose: () => void
  onMessageSent: () => void
}

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
}

function ConversationPage({
  accessToken,
  chat,
  onClose,
  onMessageSent,
}: ConversationPageProps) {
  const [messages, setMessages] = useState<DecryptedHistoryMessage[]>([])
  const [draft, setDraft] = useState("")
  const [statusMessage, setStatusMessage] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const messageEndRef = useRef<HTMLDivElement | null>(null)

  const ensureRegisteredMessengerDevice = useCallback(async () => {
    const deviceRequest =
      getStoredPublicDeviceRegistration()
      ?? await createPublicDeviceRegistrationRequest()
    const registrationResponse = await registerMessengerDevice(
      deviceRequest,
      accessToken,
    )
    savePublicDeviceRegistration(deviceRequest)

    return registrationResponse.data.device_id
  }, [accessToken])

  const loadHistory = useCallback(async () => {
    setIsLoadingHistory(true)
    setStatusMessage("")
    setErrorMessage("")

    try {
      const deviceId = await ensureRegisteredMessengerDevice()
      const historyResponse = await getEncryptedHistory(
        chat.roomId,
        deviceId,
        accessToken,
      )
      const decryptedHistory = await decryptXChaCha20Poly1305History(
        historyResponse.data.messages,
      )

      setMessages(decryptedHistory.reverse())
      setStatusMessage(
        `Decrypted here: ${decryptedHistory.length}/${historyResponse.data.messages.length}.`,
      )
    } catch (error) {
      setErrorMessage(
        error instanceof MessengerApiError
          ? error.message
          : "Unable to load this conversation.",
      )
    } finally {
      setIsLoadingHistory(false)
    }
  }, [accessToken, chat.roomId, ensureRegisteredMessengerDevice])

  useEffect(() => {
    setMessages([])
    setDraft("")
    void loadHistory()
  }, [loadHistory])

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ block: "end" })
  }, [messages.length])

  const handleSend = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!chat.recipientUserId || !draft.trim()) {
      return
    }

    setIsSending(true)
    setStatusMessage("")
    setErrorMessage("")

    try {
      const senderDeviceId = await ensureRegisteredMessengerDevice()
      const claimResponse = await claimPreKeyBundles(
        {
          recipient_user_id: chat.recipientUserId,
        },
        accessToken,
      )
      let directMessageRequest = await createEncryptedDirectMessageRequest({
        senderDeviceId,
        claim: claimResponse.data,
        body: draft.trim(),
      })

      try {
        await sendDirectMessage(directMessageRequest, accessToken)
      } catch (error) {
        const missingDeviceIds =
          error instanceof MessengerApiError
            ? extractMissingEnvelopeDeviceIds(error.message)
            : []

        if (!missingDeviceIds.length) {
          throw error
        }

        directMessageRequest = addDevDeviceSyncEnvelopes(
          directMessageRequest,
          missingDeviceIds,
        )
        await sendDirectMessage(directMessageRequest, accessToken)
      }

      setDraft("")
      await loadHistory()
      onMessageSent()
    } catch (error) {
      setErrorMessage(
        error instanceof MessengerApiError
          ? error.message
          : "Unable to send this message.",
      )
    } finally {
      setIsSending(false)
    }
  }

  return (
    <section className="main-view conversation-view active">
      <header className="conversation-header">
        <div className="conversation-user">
          {chat.profilePicture ? (
            <img
              className="conversation-avatar"
              src={chat.profilePicture.url}
              alt=""
            />
          ) : (
            <span className="conversation-avatar">{initials(chat.name)}</span>
          )}
          <div className="conversation-user-text">
            <h2>{chat.name}</h2>
            <p>{chat.status}</p>
          </div>
        </div>

        <nav className="conversation-header-actions">
          <button
            className="main-icon-button"
            type="button"
            aria-label="Refresh messages"
            disabled={isLoadingHistory || isSending}
            onClick={() => void loadHistory()}
          >
            <RefreshCcw aria-hidden="true" />
          </button>
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
        {messages.length ? (
          messages.map((message) => {
            const isIncoming =
              chat.recipientUserId !== null
              && message.senderUserId === chat.recipientUserId

            return (
              <div
                className={`message-row ${
                  isIncoming ? "received-message-row" : "sent-message-row"
                }`}
                key={message.messageId}
              >
                <div
                  className={`message-bubble ${
                    isIncoming ? "received-message" : "sent-message"
                  }`}
                >
                  <p>{message.content.body}</p>
                  <time>{new Date(message.createdAt).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}</time>
                </div>
              </div>
            )
          })
        ) : (
          <div className="conversation-empty-state">
            <MessageCircle aria-hidden="true" />
            <h2>{chat.name}</h2>
            <p>{isLoadingHistory ? "Loading messages..." : "No decrypted messages yet."}</p>
          </div>
        )}
        <div ref={messageEndRef} />
      </div>

      {statusMessage || errorMessage ? (
        <div className="conversation-status" aria-live="polite">
          {statusMessage ? <p>{statusMessage}</p> : null}
          {errorMessage ? <p role="alert">{errorMessage}</p> : null}
        </div>
      ) : null}

      <form className="message-composer" onSubmit={handleSend}>
        <label className="message-input-area" htmlFor="messageInput">
          <MessageCircle aria-hidden="true" />
          <input
            id="messageInput"
            type="text"
            value={draft}
            placeholder={`Message ${chat.name}`}
            disabled={isSending || !chat.recipientUserId}
            onChange={(event) => setDraft(event.target.value)}
          />
        </label>
        <button
          className="composer-icon-button send-button"
          type="submit"
          aria-label="Send"
          disabled={isSending || !draft.trim() || !chat.recipientUserId}
        >
          <SendHorizontal aria-hidden="true" />
        </button>
      </form>
    </section>
  )
}

export default ConversationPage
