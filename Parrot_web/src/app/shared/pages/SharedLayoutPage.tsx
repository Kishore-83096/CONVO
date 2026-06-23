import { useEffect, useState } from "react"
import { useNavigate } from "react-router"

import { ApiClientError } from "@/api/client"
import { UserStartPage } from "@/app/parrot_identity/auth"
import { logout } from "@/app/parrot_identity/auth/auth.api"
import {
  clearAuthSession,
  getAuthSession,
} from "@/app/parrot_identity/auth/auth-session"
import {
  ContactDetailPage,
  ContactsSidebar,
} from "@/app/parrot_identity/contacts"
import parrotIcon from "@/assets/icons/ParrotIcon_3D_effect.svg"
import { Button } from "@/components/ui/button"

import "../css/SharedLayoutPage.css"

function SharedLayoutPage() {
  const navigate = useNavigate()
  const [showAccount, setShowAccount] = useState(false)
  const [selectedContactId, setSelectedContactId] = useState<number | null>(null)
  const [contactsRefreshKey, setContactsRefreshKey] = useState(0)
  const [session] = useState(() => getAuthSession())
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const [logoutError, setLogoutError] = useState("")

  useEffect(() => {
    if (!session) {
      navigate("/", { replace: true })
    }
  }, [navigate, session])

  if (!session) {
    return null
  }

  const handleLogout = async () => {
    setIsLoggingOut(true)
    setLogoutError("")

    try {
      await logout(session.accessToken)
      navigate("/", { replace: true })
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 401) {
        clearAuthSession()
        navigate("/", { replace: true })
        return
      }

      setLogoutError(
        error instanceof ApiClientError
          ? error.message
          : "Unable to log out. Please try again.",
      )
    } finally {
      setIsLoggingOut(false)
    }
  }

  return (
    <div className="shared-layout">
      <aside className="shared-sidebar">
        <header className="shared-sidebar-header">
          <div className="shared-layout-brand">
            <img src={parrotIcon} alt="" />
            <span>Parrot</span>
          </div>

          <button
            className="shared-sidebar-toggle"
            type="button"
            aria-expanded={showAccount}
            aria-label={showAccount ? "Show services" : "Show account details"}
            onClick={() => setShowAccount((current) => !current)}
          >
            <span />
            <span />
            <span />
          </button>
        </header>

        <div className="shared-sidebar-body">
          {showAccount ? (
            <section className="shared-account" aria-label="Account details">
              <p>Signed in account</p>
              <h2>{session.user.full_name}</h2>
              <dl>
                <div>
                  <dt>Parrot email</dt>
                  <dd>{session.user.email}</dd>
                </div>
                <div>
                  <dt>Contact number</dt>
                  <dd>{session.user.contact_number}</dd>
                </div>
                <div>
                  <dt>Session expires</dt>
                  <dd>{new Date(session.expiresAt).toLocaleString()}</dd>
                </div>
              </dl>

              {logoutError && (
                <p className="shared-account-error" role="alert">
                  {logoutError}
                </p>
              )}

              <Button
                className="shared-account-logout"
                variant="outline"
                onClick={() => void handleLogout()}
                disabled={isLoggingOut}
              >
                {isLoggingOut ? "Logging out…" : "Logout"}
              </Button>
            </section>
          ) : (
            <ContactsSidebar
              accessToken={session.accessToken}
              onSelectContact={setSelectedContactId}
              refreshKey={contactsRefreshKey}
            />
          )}
        </div>
      </aside>

      <main className="shared-layout-content">
        {selectedContactId ? (
          <ContactDetailPage
            accessToken={session.accessToken}
            contactId={selectedContactId}
            onBack={() => setSelectedContactId(null)}
            onChanged={() =>
              setContactsRefreshKey((current) => current + 1)
            }
          />
        ) : (
          <UserStartPage />
        )}
      </main>
    </div>
  )
}

export default SharedLayoutPage
