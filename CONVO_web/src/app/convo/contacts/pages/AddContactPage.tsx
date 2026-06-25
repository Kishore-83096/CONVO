import { useCallback, useState, type FormEvent } from "react"
import { useNavigate } from "react-router"

import { ApiClientError } from "@/api/client"
import { clearAuthSession } from "@/app/parrot_identity/auth/auth-session"
import {
  addContact,
  searchContact,
} from "@/app/parrot_identity/contacts/contacts.api"
import type {
  ContactSearchResult,
  ProfilePicture,
} from "@/app/parrot_identity/contacts/contacts.types"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

import "@/app/parrot_identity/contacts/css/ContactsSidebar.css"

interface AddContactPageProps {
  accessToken: string
  onAdded: () => void
  onViewContacts: () => void
}

interface SearchState {
  contactNumber: string
  message: string
  result: ContactSearchResult
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

function AddContactPage({
  accessToken,
  onAdded,
  onViewContacts,
}: AddContactPageProps) {
  const navigate = useNavigate()
  const [searchState, setSearchState] = useState<SearchState | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
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

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const contactNumber = String(formData.get("contact_number") ?? "").trim()

    setIsSubmitting(true)
    setSearchState(null)
    setMessage("")
    setErrorMessage("")

    try {
      const response = await searchContact(
        { contact_number: contactNumber },
        accessToken,
      )

      if (response.data) {
        setSearchState({
          contactNumber,
          message: response.message,
          result: response.data,
        })
      }
    } catch (error) {
      setErrorMessage(apiError(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleAdd = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!searchState || searchState.message !== "Contact found.") {
      return
    }

    const formData = new FormData(event.currentTarget)
    const savedName = String(formData.get("saved_name") ?? "").trim()

    setIsSubmitting(true)
    setMessage("")
    setErrorMessage("")

    try {
      const response = await addContact(
        {
          contact_number: searchState.contactNumber,
          saved_name: savedName,
        },
        accessToken,
      )

      setMessage(response.message)
      setSearchState(null)
      onAdded()
    } catch (error) {
      setErrorMessage(apiError(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="sidebar-view active" aria-label="Add contact tab">
      <div className="sidebar-view-heading contacts-back-heading">
        <button
          className="contacts-back-icon-button"
          type="button"
          aria-label="Back to saved contacts"
          onClick={onViewContacts}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M15 6L9 12L15 18" />
          </svg>
        </button>
      </div>

      <section className="contacts-panel contacts-search-section">
        <form className="contact-form" onSubmit={handleSearch}>
          <div className="contacts-search-inline">
            <Label htmlFor="search_contact_number">Contact number</Label>
            <span className="contacts-search-box">
              <Input
                id="search_contact_number"
                name="contact_number"
                inputMode="numeric"
                pattern="[0-9]{10}"
                placeholder="10-digit number"
                required
              />
              <button
                className="contacts-search-icon-button"
                type="submit"
                aria-label="Search contact"
                disabled={isSubmitting}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="11" cy="11" r="7" />
                  <path d="M16 16L21 21" />
                </svg>
              </button>
            </span>
          </div>
        </form>

        {searchState && (
          <div className="contact-search-result">
            <div className="contact-search-identity">
              <ContactAvatar
                name={searchState.result.full_name}
                picture={searchState.result.profile_picture}
              />
              <div>
                <h3>{searchState.result.full_name}</h3>
                <span>@{searchState.result.username}</span>
              </div>
            </div>
            <p>{searchState.message}</p>

            {searchState.message === "Contact found." && (
              <form className="contact-form" onSubmit={handleAdd}>
                <div>
                  <Label htmlFor="add_saved_name">Save as</Label>
                  <Input
                    id="add_saved_name"
                    name="saved_name"
                    defaultValue={searchState.result.full_name}
                    maxLength={100}
                    required
                  />
                </div>
                <button
                  className="primary-action-button"
                  type="submit"
                  disabled={isSubmitting}
                >
                  Add contact
                </button>
              </form>
            )}
          </div>
        )}

        {message && <p className="contact-message">{message}</p>}
        {errorMessage && (
          <p className="contact-error" role="alert">
            {errorMessage}
          </p>
        )}
      </section>
    </section>
  )
}

export default AddContactPage
