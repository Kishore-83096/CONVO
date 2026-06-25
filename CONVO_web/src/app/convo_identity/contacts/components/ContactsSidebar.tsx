import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router"

import { ApiClientError } from "@/api/client"
import { clearAuthSession } from "@/app/convo_identity/auth/auth-session"
import { listContacts } from "@/app/convo_identity/contacts/contacts.api"
import type {
  ContactSummary,
  ProfilePicture,
} from "@/app/convo_identity/contacts/contacts.types"

import "../css/ContactsSidebar.css"

interface ContactsSidebarProps {
  accessToken: string
  onAddContact?: () => void
  onSelectContact: (contactId: number) => void
  refreshKey: number
  selectedContactId?: number | null
}

interface ContactAvatarProps {
  name: string
  picture: ProfilePicture | null
}

function ContactAvatar({ name, picture }: ContactAvatarProps) {
  return picture ? (
    <img className="contact-avatar" src={picture.url} alt="" loading="lazy" />
  ) : (
    <span className="contact-avatar contact-avatar--fallback" aria-hidden="true">
      {name.charAt(0).toUpperCase()}
    </span>
  )
}

function ContactsSidebar({
  accessToken,
  onAddContact,
  onSelectContact,
  refreshKey,
  selectedContactId = null,
}: ContactsSidebarProps) {
  const navigate = useNavigate()
  const [contacts, setContacts] = useState<ContactSummary[]>([])
  const [isLoadingContacts, setIsLoadingContacts] = useState(true)
  const [errorMessage, setErrorMessage] = useState("")

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

    setIsLoadingContacts(true)

    void listContacts(accessToken)
      .then((response) => {
        if (!cancelled) {
          setContacts(response.data ?? [])
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setErrorMessage(apiError(error))
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingContacts(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [accessToken, apiError, refreshKey])

  return (
    <div className="contacts-sidebar-content">
      <section className="contacts-panel contacts-saved-section contacts-saved-section--top">
        {onAddContact ? (
          <button
            className="contacts-add-entry-button"
            type="button"
            onClick={onAddContact}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 5V19" />
              <path d="M5 12H19" />
            </svg>
            <span>Add Contact</span>
          </button>
        ) : null}

        {isLoadingContacts ? (
          <p className="contacts-state">Loading contacts...</p>
        ) : contacts.length === 0 ? (
          <p className="contacts-state">No saved contacts yet.</p>
        ) : (
          <ul className="saved-contact-list">
            {contacts.map((contact) => (
              <li key={contact.id}>
                <button
                  className={`saved-contact-item ${
                    selectedContactId === contact.id ? "selected" : ""
                  }`}
                  type="button"
                  onClick={() => onSelectContact(contact.id)}
                >
                  <span className="saved-contact-identity">
                    <ContactAvatar
                      name={contact.saved_name}
                      picture={contact.profile_picture}
                    />
                    <span>
                      <strong>{contact.saved_name}</strong>
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {errorMessage && (
          <p className="contact-error" role="alert">
            {errorMessage}
          </p>
        )}
      </section>
    </div>
  )
}

export default ContactsSidebar
