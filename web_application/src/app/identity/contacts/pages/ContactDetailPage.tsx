import { useCallback, useEffect, useState, type FormEvent } from "react"
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

import "../css/ContactDetailPage.css"

interface ContactDetailPageProps {
  accessToken: string
  contactId: number
  onBack: () => void
  onChanged: () => void
}

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
  const [message, setMessage] = useState("")
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

    setIsLoading(true)
    setErrorMessage("")

    void getContact(contactId, accessToken)
      .then((response) => {
        if (!cancelled) {
          setContact(response.data ?? null)
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
          <h1>{contact.saved_name}</h1>
        </div>

        <nav className="contact-detail-actions" aria-label="Contact actions">
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
        {message ? <p className="contact-message">{message}</p> : null}
        {errorMessage ? (
          <p className="contact-error" role="alert">
            {errorMessage}
          </p>
        ) : null}
      </div>

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
