import { useCallback, useEffect, useState, type FormEvent } from "react"
import { useNavigate } from "react-router"

import { ApiClientError } from "@/api/client"
import { clearAuthSession } from "@/app/parrot_identity/auth/auth-session"
import {
  addContact,
  listContacts,
  searchContact,
} from "@/app/parrot_identity/contacts/contacts.api"
import type {
  ContactSearchResult,
  ContactSummary,
  ProfilePicture,
} from "@/app/parrot_identity/contacts/contacts.types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

import "../css/ContactsSidebar.css"

interface ContactsSidebarProps {
  accessToken: string
  onSelectContact: (contactId: number) => void
  refreshKey: number
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

function ContactsSidebar({
  accessToken,
  onSelectContact,
  refreshKey,
}: ContactsSidebarProps) {
  const navigate = useNavigate()
  const [contacts, setContacts] = useState<ContactSummary[]>([])
  const [searchState, setSearchState] = useState<SearchState | null>(null)
  const [isLoadingContacts, setIsLoadingContacts] = useState(true)
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

  const refreshContacts = useCallback(async () => {
    setIsLoadingContacts(true)
    setErrorMessage("")

    try {
      const response = await listContacts(accessToken)
      setContacts(response.data ?? [])
    } catch (error) {
      setErrorMessage(apiError(error))
    } finally {
      setIsLoadingContacts(false)
    }
  }, [accessToken, apiError])

  useEffect(() => {
    let cancelled = false

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
      await refreshContacts()
    } catch (error) {
      setErrorMessage(apiError(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="contacts-sidebar-content">
      <section className="contacts-panel contacts-search-section">
        <div className="contacts-heading">
          <p>Contacts</p>
          <h2>Search</h2>
        </div>

        <form className="contact-form" onSubmit={handleSearch}>
          <div>
            <Label htmlFor="search_contact_number">Contact number</Label>
            <Input
              id="search_contact_number"
              name="contact_number"
              inputMode="numeric"
              pattern="[0-9]{10}"
              placeholder="10-digit number"
              required
            />
          </div>
          <Button disabled={isSubmitting}>Search</Button>
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
                <Button disabled={isSubmitting}>Add contact</Button>
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

      <section className="contacts-panel contacts-saved-section">
        <div className="contacts-heading contacts-heading--row">
          <div>
            <p>Your list</p>
            <h2>Saved contacts</h2>
          </div>
          <button
            type="button"
            onClick={() => void refreshContacts()}
            disabled={isLoadingContacts}
          >
            Refresh
          </button>
        </div>

        {isLoadingContacts ? (
          <p className="contacts-state">Loading contacts…</p>
        ) : contacts.length === 0 ? (
          <p className="contacts-state">No saved contacts yet.</p>
        ) : (
          <ul className="saved-contact-list">
            {contacts.map((contact) => (
              <li key={contact.id}>
                <button
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
                      <small>Saved contact</small>
                    </span>
                  </span>
                  <span className="saved-contact-arrow" aria-hidden="true">
                    ›
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

export default ContactsSidebar
