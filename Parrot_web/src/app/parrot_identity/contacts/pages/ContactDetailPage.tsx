import { useCallback, useEffect, useState, type FormEvent } from "react"
import { useNavigate } from "react-router"

import { ApiClientError } from "@/api/client"
import { clearAuthSession } from "@/app/parrot_identity/auth/auth-session"
import {
  deleteContact,
  getContact,
  renameContact,
} from "@/app/parrot_identity/contacts/contacts.api"
import type { ContactDetail } from "@/app/parrot_identity/contacts/contacts.types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

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
    }
  }

  const handleDelete = async () => {
    if (!contact) {
      return
    }

    const shouldDelete = window.confirm(
      `Remove ${contact.saved_name} from your saved contacts?`,
    )

    if (!shouldDelete) {
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
    return <p className="contact-detail-state">Loading contact…</p>
  }

  if (!contact) {
    return (
      <section className="contact-detail-page">
        <button className="contact-detail-back" type="button" onClick={onBack}>
          ← Back
        </button>
        <p className="contact-error">{errorMessage || "Contact not found."}</p>
      </section>
    )
  }

  return (
    <section className="contact-detail-page">
      <button className="contact-detail-back" type="button" onClick={onBack}>
        ← Saved contacts
      </button>

      <header className="contact-detail-header">
        {contact.profile_picture ? (
          <img src={contact.profile_picture.url} alt="" />
        ) : (
          <span aria-hidden="true">{contact.saved_name.charAt(0)}</span>
        )}
        <div>
          <p>{contact.full_name}</p>
          <h1>{contact.saved_name}</h1>
          <small>@{contact.username}</small>
        </div>
      </header>

      <dl className="contact-detail-data">
        <div>
          <dt>Contact number</dt>
          <dd>{contact.contact_number}</dd>
        </div>
        <div>
          <dt>Contact ID</dt>
          <dd>{contact.id}</dd>
        </div>
      </dl>

      <form className="contact-detail-form" onSubmit={handleRename}>
        <div>
          <Label htmlFor="detail_saved_name">Saved name</Label>
          <Input
            id="detail_saved_name"
            name="saved_name"
            defaultValue={contact.saved_name}
            maxLength={100}
            required
          />
        </div>
        <Button disabled={isUpdating}>Rename contact</Button>
      </form>

      <Button
        className="contact-detail-delete"
        variant="destructive"
        onClick={() => void handleDelete()}
        disabled={isUpdating}
      >
        Delete contact
      </Button>

      {message && <p className="contact-message">{message}</p>}
      {errorMessage && (
        <p className="contact-error" role="alert">
          {errorMessage}
        </p>
      )}
    </section>
  )
}

export default ContactDetailPage
