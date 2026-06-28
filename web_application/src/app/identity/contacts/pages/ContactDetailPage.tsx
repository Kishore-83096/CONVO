import { useCallback, useEffect, useRef, useState, type FormEvent } from "react"
import { RefreshCcw, SendHorizontal } from "lucide-react"
import { useNavigate } from "react-router"

import { ApiClientError } from "@/api/client"
import ConfirmActionModal from "@/app/workspace/layout/components/ConfirmActionModal"
import { clearAuthSession } from "@/app/identity/auth/auth-session"
import {
  deleteContact,
  getContact,
  renameContact,
} from "@/app/identity/contacts/contacts.api"
import type { ContactDetail } from "@/app/identity/contacts/contacts.types"
import { registerMessengerDevice } from "@/messenger/api/devices.api"
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
import { decryptXChaCha20Poly1305History } from "@/messenger/e2ee/message-history"
import type { DecryptedHistoryMessage } from "@/messenger/e2ee/message-history"

import "../css/ContactDetailPage.css"

interface ContactDetailPageProps {
  accessToken: string
  contactId: number
  onBack: () => void
  onChanged: () => void
}

const contactRoomStorageKey = (contactUserId: number) =>
  `myna:messenger:contact-room:${contactUserId}`

function ContactDetailPage({
  accessToken,
  contactId,
  onBack,
  onChanged,
}: ContactDetailPageProps) {
  const navigate = useNavigate()
  const [contact, setContact] = useState<ContactDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isUpdating, setIsUpdating] = useState(false)
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false)
  const [messageDraft, setMessageDraft] = useState("")
  const [message, setMessage] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const [decryptedMessages, setDecryptedMessages] = useState<DecryptedHistoryMessage[]>([])
  const [isSendingMessage, setIsSendingMessage] = useState(false)
  const [isRefreshingMessages, setIsRefreshingMessages] = useState(false)
  const [lastRoomId, setLastRoomId] = useState<string | null>(null)
  const messageEndRef = useRef<HTMLDivElement | null>(null)

  const apiError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiClientError && error.status === 401) {
        clearAuthSession()
        navigate("/", { replace: true })
        return "Your session is no longer active."
      }

      return error instanceof ApiClientError
        ? error.message
        : "The contact request failed. Please try again."
    },
    [navigate],
  )

  useEffect(() => {
    let cancelled = false

    setIsLoading(true)
    setErrorMessage("")

    void getContact(contactId, accessToken)
      .then((response) => {
        if (!cancelled) {
          const nextContact = response.data ?? null
          setContact(nextContact)
          setLastRoomId(
            nextContact
              ? localStorage.getItem(contactRoomStorageKey(nextContact.contact_user_id))
              : null,
          )
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setErrorMessage(apiError(error))
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [accessToken, apiError, contactId])

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ block: "end" })
  }, [decryptedMessages.length])

  const handleRename = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!contact) {
      return
    }

    const formData = new FormData(event.currentTarget)
    const savedName = String(formData.get("saved_name") ?? "").trim()

    setIsUpdating(true)
    setMessage("")
    setErrorMessage("")

    try {
      const response = await renameContact(
        contact.id,
        { saved_name: savedName },
        accessToken,
      )

      if (response.data) {
        setContact(response.data)
      }

      setMessage(response.message)
      onChanged()
    } catch (error) {
      setErrorMessage(apiError(error))
    } finally {
      setIsUpdating(false)
      setIsDeleteConfirmOpen(false)
    }
  }

  const handleDelete = async () => {
    if (!contact) {
      return
    }

    setIsUpdating(true)
    setMessage("")
    setErrorMessage("")

    try {
      await deleteContact(contact.id, accessToken)
      onChanged()
      onBack()
    } catch (error) {
      setErrorMessage(apiError(error))
    } finally {
      setIsUpdating(false)
    }
  }

  const messengerError = useCallback(
    (error: unknown) => {
      if (error instanceof MessengerApiError && error.status === 401) {
        clearAuthSession()
        navigate("/", { replace: true })
        return "Your session is no longer active."
      }

      return error instanceof MessengerApiError
        ? error.message
        : "The message request failed. Please try again."
    },
    [navigate],
  )

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

  const loadMessageHistory = useCallback(
    async (roomId: string, deviceId: string) => {
      const historyResponse = await getEncryptedHistory(
        roomId,
        deviceId,
        accessToken,
      )
      const decryptedHistory = await decryptXChaCha20Poly1305History(
        historyResponse.data.messages,
      )

      setDecryptedMessages(decryptedHistory)

      return {
        decryptedCount: decryptedHistory.length,
        totalCount: historyResponse.data.messages.length,
      }
    },
    [accessToken],
  )

  const handleRefreshMessages = async () => {
    if (!contact) {
      return
    }

    const roomId =
      lastRoomId
      ?? localStorage.getItem(contactRoomStorageKey(contact.contact_user_id))

    if (!roomId) {
      setMessage("Send one message first, then refresh can load this conversation.")
      setErrorMessage("")
      return
    }

    setIsRefreshingMessages(true)
    setMessage("")
    setErrorMessage("")

    try {
      const deviceId = await ensureRegisteredMessengerDevice()
      const history = await loadMessageHistory(roomId, deviceId)
      setMessage(
        `History refreshed. Decrypted here: ${history.decryptedCount}/${history.totalCount}.`,
      )
    } catch (error) {
      setErrorMessage(messengerError(error))
    } finally {
      setIsRefreshingMessages(false)
    }
  }

  const handleSendMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!contact || !messageDraft.trim()) {
      return
    }

    setIsSendingMessage(true)
    setMessage("")
    setErrorMessage("")

    try {
      const senderDeviceId = await ensureRegisteredMessengerDevice()

      const claimResponse = await claimPreKeyBundles(
        {
          recipient_user_id: String(contact.contact_user_id),
        },
        accessToken,
      )
      let directMessageRequest = await createEncryptedDirectMessageRequest({
        senderDeviceId,
        claim: claimResponse.data,
        body: messageDraft.trim(),
      })
      let sendResponse

      try {
        sendResponse = await sendDirectMessage(
          directMessageRequest,
          accessToken,
        )
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
        sendResponse = await sendDirectMessage(
          directMessageRequest,
          accessToken,
        )
      }

      setMessageDraft("")
      localStorage.setItem(
        contactRoomStorageKey(contact.contact_user_id),
        sendResponse.data.room_id,
      )
      setLastRoomId(sendResponse.data.room_id)

      const history = await loadMessageHistory(sendResponse.data.room_id, senderDeviceId)
      setMessage(
        `Encrypted message sent. Decrypted here: ${history.decryptedCount}/${history.totalCount}.`,
      )
    } catch (error) {
      setErrorMessage(messengerError(error))
    } finally {
      setIsSendingMessage(false)
    }
  }

  if (isLoading) {
    return <p className="contact-detail-state">Loading contact...</p>
  }

  if (!contact) {
    return (
      <section className="contact-detail-page contact-detail-page--state">
        <button className="contact-detail-close" type="button" onClick={onBack}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 6L18 18" />
            <path d="M18 6L6 18" />
          </svg>
        </button>
        <p className="contact-error">{errorMessage || "Contact not found."}</p>
      </section>
    )
  }

  return (
    <section className="contact-detail-page">
      <header className="contact-detail-main-header">
        <div className="contact-detail-identity">
          {contact.profile_picture ? (
            <img src={contact.profile_picture.url} alt="" />
          ) : (
            <span aria-hidden="true">{contact.saved_name.charAt(0)}</span>
          )}
          <div className="contact-detail-title">
            <h1>{contact.saved_name}</h1>
            <p>@{contact.username}</p>
          </div>
        </div>

        <nav className="contact-detail-actions" aria-label="Contact actions">
          <button
            className="contact-detail-icon-button"
            type="button"
            aria-label="Refresh messages"
            disabled={isRefreshingMessages || isSendingMessage}
            onClick={() => void handleRefreshMessages()}
          >
            <RefreshCcw aria-hidden="true" />
          </button>

          <div className="contact-detail-menu-wrap">
            <button
              className="contact-detail-icon-button"
              type="button"
              aria-label="Open contact properties"
              aria-expanded={isMenuOpen}
              onClick={() => setIsMenuOpen((current) => !current)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="5" r="1" />
                <circle cx="12" cy="12" r="1" />
                <circle cx="12" cy="19" r="1" />
              </svg>
            </button>

            {isMenuOpen ? (
              <div className="contact-detail-dropdown" role="menu">
                <dl>
                  <div>
                    <dt>Full name</dt>
                    <dd>{contact.full_name}</dd>
                  </div>
                  <div>
                    <dt>Username</dt>
                    <dd>@{contact.username}</dd>
                  </div>
                  <div>
                    <dt>Contact number</dt>
                    <dd>{contact.contact_number}</dd>
                  </div>
                </dl>

                <form className="contact-detail-menu-form" onSubmit={handleRename}>
                  <label htmlFor="detail_saved_name">Saved name</label>
                  <input
                    id="detail_saved_name"
                    name="saved_name"
                    defaultValue={contact.saved_name}
                    maxLength={100}
                    required
                  />
                  <button type="submit" disabled={isUpdating}>
                    Rename
                  </button>
                </form>

                <button
                  className="contact-detail-menu-delete"
                  type="button"
                  disabled={isUpdating}
                  onClick={() => {
                    setIsMenuOpen(false)
                    setIsDeleteConfirmOpen(true)
                  }}
                >
                  Delete contact
                </button>
              </div>
            ) : null}
          </div>

          <button
            className="contact-detail-icon-button"
            type="button"
            aria-label="Close contact"
            onClick={onBack}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6L18 18" />
              <path d="M18 6L6 18" />
            </svg>
          </button>
        </nav>
      </header>

      <div className="contact-detail-body">
        <div className="contact-message-thread">
          {decryptedMessages.length ? (
            <div className="contact-message-history" aria-live="polite">
              {decryptedMessages.map((historyMessage) => {
                const isIncoming =
                  historyMessage.senderUserId === String(contact.contact_user_id)

                return (
                  <article
                    className={`contact-message-history-item ${
                      isIncoming
                        ? "contact-message-history-item--incoming"
                        : "contact-message-history-item--outgoing"
                    }`}
                    key={historyMessage.messageId}
                  >
                    <p>{historyMessage.content.body}</p>
                    <time>{new Date(historyMessage.createdAt).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}</time>
                  </article>
                )
              })}
              <div ref={messageEndRef} />
            </div>
          ) : (
            <div className="contact-message-empty">
              <div aria-hidden="true">
                {contact.saved_name.charAt(0)}
              </div>
              <h2>{contact.saved_name}</h2>
              <p>@{contact.username}</p>
            </div>
          )}
        </div>

        {message || errorMessage ? (
          <div className="contact-message-status" aria-live="polite">
            {message ? <p className="contact-message">{message}</p> : null}
            {errorMessage ? (
              <p className="contact-error" role="alert">
                {errorMessage}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      <form className="contact-message-composer" onSubmit={handleSendMessage}>
        <input
          type="text"
          value={messageDraft}
          placeholder={`Message ${contact.saved_name}`}
          disabled={isSendingMessage}
          onChange={(event) => setMessageDraft(event.target.value)}
        />
        <button
          type="submit"
          aria-label="Send message"
          disabled={isSendingMessage || !messageDraft.trim()}
        >
          <SendHorizontal aria-hidden="true" />
        </button>
      </form>

      <ConfirmActionModal
        confirmLabel="Delete contact"
        description={`This will remove ${contact.saved_name} from your saved contacts. You can add them again later if needed.`}
        isBusy={isUpdating}
        isOpen={isDeleteConfirmOpen}
        title="Delete this contact?"
        tone="danger"
        onCancel={() => setIsDeleteConfirmOpen(false)}
        onConfirm={() => void handleDelete()}
      />
    </section>
  )
}

export default ContactDetailPage
