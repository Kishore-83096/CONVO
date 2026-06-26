import { useEffect, useState, type FormEvent } from "react"
import { X } from "lucide-react"
import { useNavigate } from "react-router"

import { ApiClientError } from "@/api/client"
import ConfirmActionModal from "@/app/convo/layout/components/ConfirmActionModal"
import type { CompleteProfile } from "@/app/convo/profile/profile.types"
import {
  deleteAccount,
  resetPassword,
} from "@/app/convo_identity/auth/auth.api"
import {
  clearAuthSession,
  type AuthSession,
} from "@/app/convo_identity/auth/auth-session"
import type {
  AccountCredentialsRequest,
  ResetPasswordRequest,
} from "@/app/convo_identity/auth/auth.types"

interface AccountSettingsPageProps {
  accessToken: string
  profile: CompleteProfile | null
  session: AuthSession
  onClose: () => void
  storageKey: string
}

type AccountTab = "details" | "password" | "delete"

const accountTabs: { id: AccountTab; label: string }[] = [
  { id: "details", label: "Account" },
  { id: "password", label: "Change Password" },
  { id: "delete", label: "Delete Account" },
]

function savedAccountTab(storageKey: string): AccountTab {
  const tab = localStorage.getItem(storageKey)
  const validTabs = accountTabs.map((accountTab) => accountTab.id)

  return validTabs.includes(tab as AccountTab)
    ? (tab as AccountTab)
    : "details"
}

function fieldText(formData: FormData, name: string) {
  return String(formData.get(name) ?? "").trim()
}

function accountError(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Account request failed. Please try again."
}

function AccountSettingsPage({
  accessToken,
  profile,
  session,
  onClose,
  storageKey,
}: AccountSettingsPageProps) {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<AccountTab>(() =>
    savedAccountTab(storageKey),
  )
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [deleteCredentials, setDeleteCredentials] =
    useState<AccountCredentialsRequest | null>(null)
  const identity = profile?.identity
  const username = identity?.username ?? ""
  const email = identity?.email ?? session.user.email
  const contactNumber = identity?.contact_number ?? session.user.contact_number

  useEffect(() => {
    localStorage.setItem(storageKey, activeTab)
  }, [activeTab, storageKey])

  const credentialsFromForm = (
    formData: FormData,
  ): AccountCredentialsRequest => ({
    username: fieldText(formData, "username"),
    email: fieldText(formData, "email"),
    contact_number: fieldText(formData, "contact_number"),
    current_password: fieldText(formData, "current_password"),
  })

  const handleSessionRevoked = () => {
    clearAuthSession()
    navigate("/", { replace: true })
  }

  const handlePasswordChange = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const request: ResetPasswordRequest = {
      ...credentialsFromForm(formData),
      new_password: fieldText(formData, "new_password"),
      confirm_new_password: fieldText(formData, "confirm_new_password"),
    }

    setIsSubmitting(true)
    setMessage("")
    setError("")

    try {
      await resetPassword(request, accessToken)
      handleSessionRevoked()
    } catch (submitError) {
      setError(accountError(submitError))
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDeleteAccount = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)

    setDeleteCredentials(credentialsFromForm(formData))
    setMessage("")
    setError("")
  }

  const confirmDeleteAccount = async () => {
    if (!deleteCredentials) {
      return
    }

    setIsSubmitting(true)
    setMessage("")
    setError("")

    try {
      await deleteAccount(deleteCredentials, accessToken)
      handleSessionRevoked()
    } catch (submitError) {
      setError(accountError(submitError))
    } finally {
      setIsSubmitting(false)
      setDeleteCredentials(null)
    }
  }

  return (
    <section className="main-view workspace-view active">
      <header className="workspace-header">
        <div className="workspace-title-row">
          <div>
            <h2>Account Settings</h2>
          </div>
          <button
            className="main-close-button"
            type="button"
            aria-label="Close"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </button>
        </div>

        <nav className="workspace-tabs" aria-label="Account tabs">
          {accountTabs.map((tab) => (
            <button
              className={`workspace-tab ${activeTab === tab.id ? "active" : ""}`}
              key={tab.id}
              type="button"
              onClick={() => {
                setActiveTab(tab.id)
                setMessage("")
                setError("")
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="workspace-content">
        {activeTab === "details" ? (
          <section className="workspace-panel active">
            <dl className="profile-detail-grid">
              <div>
                <dt>Full name</dt>
                <dd>{identity?.full_name ?? session.user.full_name}</dd>
              </div>
              <div>
                <dt>Username</dt>
                <dd>{username ? `@${username}` : "Loaded after profile API"}</dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>{email}</dd>
              </div>
              <div>
                <dt>Contact number</dt>
                <dd>{contactNumber}</dd>
              </div>
              <div>
                <dt>Session expires</dt>
                <dd>{new Date(session.expiresAt).toLocaleString()}</dd>
              </div>
            </dl>
          </section>
        ) : null}

        {activeTab === "password" ? (
          <section className="workspace-panel active">
            <form className="flat-form" onSubmit={handlePasswordChange}>
              <AccountCredentialFields
                contactNumber={contactNumber}
                email={email}
                username={username}
                prefill={false}
              />
              <div className="form-field">
                <label htmlFor="new_password">New password</label>
                <input id="new_password" name="new_password" type="password" required />
              </div>
              <div className="form-field">
                <label htmlFor="confirm_new_password">Confirm new password</label>
                <input
                  id="confirm_new_password"
                  name="confirm_new_password"
                  type="password"
                  required
                />
              </div>
              <div className="form-actions form-field-wide">
                <button
                  className="primary-action-button"
                  type="submit"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Changing..." : "Change Password"}
                </button>
              </div>
            </form>
          </section>
        ) : null}

        {activeTab === "delete" ? (
          <section className="workspace-panel active">
            <form className="flat-form" onSubmit={handleDeleteAccount}>
              <AccountCredentialFields
                contactNumber={contactNumber}
                email={email}
                username={username}
                prefill={false}
              />
              <div className="form-actions form-field-wide">
                <button
                  className="danger-action-button"
                  type="submit"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Deleting..." : "Delete Account"}
                </button>
              </div>
            </form>
          </section>
        ) : null}

        {message ? <p className="convo-profile-message">{message}</p> : null}
        {error ? (
          <p className="convo-profile-error" role="alert">
            {error}
          </p>
        ) : null}
      </div>

      <ConfirmActionModal
        confirmLabel="Delete account"
        description="This will permanently delete your account and sign you out. This action cannot be undone."
        isBusy={isSubmitting}
        isOpen={deleteCredentials !== null}
        title="Delete your CONVO account?"
        tone="danger"
        onCancel={() => setDeleteCredentials(null)}
        onConfirm={() => void confirmDeleteAccount()}
      />
    </section>
  )
}

interface AccountCredentialFieldsProps {
  username: string
  email: string
  contactNumber: string | number
  prefill?: boolean
}

function AccountCredentialFields({
  username,
  email,
  contactNumber,
  prefill = false,
}: AccountCredentialFieldsProps) {
  return (
    <>
      <div className="form-field">
        <label htmlFor="username">Username</label>
        <input
          id="username"
          name="username"
          defaultValue={prefill ? username : ""}
          required
        />
      </div>
      <div className="form-field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          name="email"
          type="email"
          defaultValue={prefill ? email : ""}
          required
        />
      </div>
      <div className="form-field">
        <label htmlFor="contact_number">Contact number</label>
        <input
          id="contact_number"
          name="contact_number"
          defaultValue={prefill ? contactNumber : ""}
          inputMode="numeric"
          required
        />
      </div>
      <div className="form-field">
        <label htmlFor="current_password">Current password</label>
        <input id="current_password" name="current_password" type="password" required />
      </div>
    </>
  )
}

export default AccountSettingsPage
