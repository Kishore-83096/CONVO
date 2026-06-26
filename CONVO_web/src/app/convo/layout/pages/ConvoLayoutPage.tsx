import { useCallback, useEffect, useState } from "react"
import { Menu, MessageCircle, Sparkles, UsersRound } from "lucide-react"
import { useNavigate, useParams } from "react-router"

import { ApiClientError } from "@/api/client"
import AccountSettingsPage from "@/app/convo/account/pages/AccountSettingsPage"
import { demoChats, type ChatSummary } from "@/app/convo/chats/chats.api"
import ChatListPage from "@/app/convo/chats/pages/ChatListPage"
import ConversationPage from "@/app/convo/chats/pages/ConversationPage"
import AddContactPage from "@/app/convo/contacts/pages/AddContactPage"
import ConfirmActionModal from "@/app/convo/layout/components/ConfirmActionModal"
import ProfileMenu from "@/app/convo/layout/components/ProfileMenu"
import AppearancePage from "@/app/convo/layout/pages/AppearancePage"
import EmptyPage from "@/app/convo/layout/pages/EmptyPage"
import { getProfile } from "@/app/convo/profile/profile.api"
import type { CompleteProfile } from "@/app/convo/profile/profile.types"
import ProfileWorkspacePage from "@/app/convo/profile/pages/ProfileWorkspacePage"
import StoriesPage from "@/app/convo/stories/pages/StoriesPage"
import { logout } from "@/app/convo_identity/auth/auth.api"
import { userHomePath } from "@/app/convo_identity/auth/auth-routes"
import {
  clearAuthSession,
  getAuthSession,
} from "@/app/convo_identity/auth/auth-session"
import {
  ContactDetailPage,
  ContactsSidebar,
} from "@/app/convo_identity/contacts"
import convoLogo from "@/assets/convo/CONVO.png"
import SeoMeta from "@/app/seo/SeoMeta"

import "../css/ConvoLayout.css"

type SidebarView = "chats" | "stories" | "contacts" | "addContact" | "profileMenu"
type MainView = "empty" | "chat" | "profile" | "account" | "appearance" | "contact"
type MobilePanel = "sidebar" | "main"

const themes = ["light", "dark", "blue", "pink", "lavender", "mint", "sunset", "aurora"]
const themeOptions = [
  { id: "light", name: "Light", colors: ["#fbfcff", "#e8edf5", "#2563eb"] },
  { id: "dark", name: "Dark", colors: ["#10141c", "#1f2937", "#8ab4ff"] },
  { id: "blue", name: "Blue", colors: ["#edf7ff", "#c5ddff", "#2563eb"] },
  { id: "pink", name: "Pink", colors: ["#fff1f6", "#f8c7dc", "#d94683"] },
  { id: "lavender", name: "Lavender", colors: ["#f7f2ff", "#d8c7ff", "#7c3aed"] },
  { id: "mint", name: "Mint", colors: ["#edfbf6", "#b9ead9", "#059669"] },
  { id: "sunset", name: "Sunset", colors: ["#fff7ed", "#fed7aa", "#ea580c"] },
  { id: "aurora", name: "Aurora", colors: ["#ecfeff", "#bbf7d0", "#0891b2"] },
]

function userStoragePrefix(session: ReturnType<typeof getAuthSession>) {
  if (!session) {
    return "convo.guest"
  }

  return `convo.user.${session.user.email}.${session.user.contact_number}`
}

function storageKey(prefix: string, name: string) {
  return `${prefix}.${name}`
}

function savedTheme(prefix: string) {
  const theme = localStorage.getItem(storageKey(prefix, "theme"))
    ?? localStorage.getItem("convo.theme")
  return theme && themes.includes(theme) ? theme : "light"
}

function savedSidebarView(prefix: string): SidebarView {
  const view = localStorage.getItem(storageKey(prefix, "sidebarView"))
  const validViews: SidebarView[] = [
    "chats",
    "stories",
    "contacts",
    "addContact",
    "profileMenu",
  ]

  return validViews.includes(view as SidebarView)
    ? (view as SidebarView)
    : "chats"
}

function savedMainView(prefix: string): MainView {
  const view = localStorage.getItem(storageKey(prefix, "mainView"))
  const validViews: MainView[] = ["empty", "profile", "account", "appearance", "contact"]

  if (view === "contact" && !savedSelectedContactId(prefix)) {
    return "empty"
  }

  return validViews.includes(view as MainView) ? (view as MainView) : "empty"
}

function savedSelectedContactId(prefix: string) {
  const contactId = Number(localStorage.getItem(storageKey(prefix, "selectedContactId")))

  return Number.isInteger(contactId) && contactId > 0 ? contactId : null
}

function ConvoLayoutPage() {
  const navigate = useNavigate()
  const { username } = useParams()
  const [session] = useState(() => getAuthSession())
  const userStorage = userStoragePrefix(session)
  const [theme, setTheme] = useState(() => savedTheme(userStorage))
  const [sidebarView, setSidebarView] = useState<SidebarView>(() =>
    savedSidebarView(userStorage),
  )
  const [mainView, setMainView] = useState<MainView>(() =>
    savedMainView(userStorage),
  )
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>("sidebar")
  const [selectedChat, setSelectedChat] = useState<ChatSummary | null>(null)
  const [selectedContactId, setSelectedContactId] = useState<number | null>(() =>
    savedSelectedContactId(userStorage),
  )
  const [contactsRefreshKey, setContactsRefreshKey] = useState(0)
  const [completeProfile, setCompleteProfile] = useState<CompleteProfile | null>(null)
  const [isProfileLoading, setIsProfileLoading] = useState(true)
  const [profileError, setProfileError] = useState("")
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const [isLogoutConfirmOpen, setIsLogoutConfirmOpen] = useState(false)
  const [logoutError, setLogoutError] = useState("")

  useEffect(() => {
    if (!session) {
      navigate("/", { replace: true })
      return
    }

    if (username !== session.user.username) {
      navigate(userHomePath(session), { replace: true })
    }
  }, [navigate, session, username])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem(storageKey(userStorage, "theme"), theme)
  }, [theme, userStorage])

  useEffect(() => {
    localStorage.setItem(storageKey(userStorage, "sidebarView"), sidebarView)
  }, [sidebarView, userStorage])

  useEffect(() => {
    const restorableMainView: MainView[] = [
      "empty",
      "profile",
      "account",
      "appearance",
      "contact",
    ]

    localStorage.setItem(
      storageKey(userStorage, "mainView"),
      restorableMainView.includes(mainView) &&
        (mainView !== "contact" || selectedContactId)
        ? mainView
        : "empty",
    )
  }, [mainView, selectedContactId, userStorage])

  useEffect(() => {
    if (selectedContactId) {
      localStorage.setItem(
        storageKey(userStorage, "selectedContactId"),
        String(selectedContactId),
      )
      return
    }

    localStorage.removeItem(storageKey(userStorage, "selectedContactId"))
  }, [selectedContactId, userStorage])

  useEffect(() => {
    document.documentElement.dataset.mobilePanel = mobilePanel
  }, [mobilePanel])

  const loadMenuProfile = useCallback(async () => {
    if (!session) {
      return
    }

    setIsProfileLoading(true)
    setProfileError("")

    try {
      const response = await getProfile(session.accessToken)
      setCompleteProfile(response.data ?? null)
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 401) {
        clearAuthSession()
        navigate("/", { replace: true })
        return
      }

      setProfileError(
        error instanceof ApiClientError
          ? error.message
          : "Unable to load profile menu details.",
      )
    } finally {
      setIsProfileLoading(false)
    }
  }, [navigate, session])

  useEffect(() => {
    void loadMenuProfile()
  }, [loadMenuProfile])

  if (!session) {
    return null
  }

  const openSidebarView = (view: SidebarView) => {
    setSidebarView(view)
    setMobilePanel("sidebar")
  }

  const openChat = (chat: ChatSummary) => {
    setSelectedChat(chat)
    setSelectedContactId(null)
    setMainView("chat")
    setMobilePanel("main")
  }

  const openContact = (contactId: number) => {
    setSelectedContactId(contactId)
    setSelectedChat(null)
    setMainView("contact")
    setMobilePanel("main")
  }

  const openMainView = (view: MainView) => {
    setMainView(view)
    setSelectedChat(null)
    setSelectedContactId(null)
    setMobilePanel("main")
  }

  const closeMainView = () => {
    setMainView("empty")
    setSelectedChat(null)
    setSelectedContactId(null)
    setMobilePanel("sidebar")
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
      setIsLogoutConfirmOpen(false)
    }
  }

  return (
    <div className="desktop-layout" id="convoLayout">
      <SeoMeta
        canonicalPath={`/${session.user.username}`}
        description="Private CONVO messaging workspace."
        robots="noindex, nofollow"
        title="CONVO Private Workspace"
      />
      <aside className="sidebar" aria-label="CONVO sidebar">
        <header className="sidebar-header">
          <div className="brand-lockup">
            <img className="brand-icon" src={convoLogo} alt="CONVO logo" />
            <h1 className="brand-name">CONVO</h1>
          </div>

          <nav className="header-actions" aria-label="Sidebar actions">
            <button
              className={`header-icon-button ${
                sidebarView === "contacts" || sidebarView === "addContact"
                  ? "active"
                  : ""
              }`}
              type="button"
              aria-label="Open contacts"
              title="Contacts"
              onClick={() => openSidebarView("contacts")}
            >
              <UsersRound aria-hidden="true" />
            </button>

            <button
              className={`header-icon-button ${
                sidebarView === "profileMenu" ? "active" : ""
              }`}
              type="button"
              aria-label="Open profile menu"
              onClick={() => openSidebarView("profileMenu")}
            >
              <Menu aria-hidden="true" />
            </button>
          </nav>
        </header>

        <div className="sidebar-body">
          {sidebarView === "chats" ? (
            <ChatListPage
              chats={demoChats}
              selectedChatId={selectedChat?.id ?? null}
              onOpenChat={openChat}
            />
          ) : null}
          {sidebarView === "stories" ? <StoriesPage /> : null}
          {sidebarView === "contacts" ? (
            <section className="sidebar-view active" aria-label="Saved contacts tab">
              <ContactsSidebar
                accessToken={session.accessToken}
                onAddContact={() => openSidebarView("addContact")}
                onSelectContact={openContact}
                refreshKey={contactsRefreshKey}
                selectedContactId={selectedContactId}
              />
            </section>
          ) : null}
          {sidebarView === "addContact" ? (
            <AddContactPage
              accessToken={session.accessToken}
              onAdded={() => {
                setContactsRefreshKey((current) => current + 1)
                openSidebarView("contacts")
              }}
              onViewContacts={() => openSidebarView("contacts")}
            />
          ) : null}
          {sidebarView === "profileMenu" ? (
            <ProfileMenu
              activeMainView={mainView}
              currentTheme={theme}
              isLoggingOut={isLoggingOut}
              isProfileLoading={isProfileLoading}
              logoutError={logoutError}
              profile={completeProfile}
              profileError={profileError}
              session={session}
              onOpenAppearance={() => openMainView("appearance")}
              onOpenAccount={() => openMainView("account")}
              onOpenProfile={() => openMainView("profile")}
              onLogout={() => setIsLogoutConfirmOpen(true)}
            />
          ) : null}
        </div>

        <footer className="sidebar-footer">
          <button
            className={`footer-tab ${sidebarView === "chats" ? "active" : ""}`}
            type="button"
            onClick={() => openSidebarView("chats")}
          >
            <MessageCircle aria-hidden="true" />
            <span>Chats</span>
          </button>

          <button
            className={`footer-tab ${sidebarView === "stories" ? "active" : ""}`}
            type="button"
            onClick={() => openSidebarView("stories")}
          >
            <Sparkles aria-hidden="true" />
            <span>Stories</span>
          </button>
        </footer>
      </aside>

      <main className="main-body">
        {mainView === "empty" ? <EmptyPage /> : null}
        {mainView === "chat" && selectedChat ? (
          <ConversationPage chat={selectedChat} onClose={closeMainView} />
        ) : null}
        {mainView === "contact" && selectedContactId ? (
          <section className="main-view workspace-view active">
            <ContactDetailPage
              accessToken={session.accessToken}
              contactId={selectedContactId}
              onBack={closeMainView}
              onChanged={() => setContactsRefreshKey((current) => current + 1)}
            />
          </section>
        ) : null}
        {mainView === "profile" ? (
          <ProfileWorkspacePage
            accessToken={session.accessToken}
            initialProfile={completeProfile}
            onClose={closeMainView}
            onProfileLoaded={setCompleteProfile}
            storageKey={storageKey(userStorage, "profileTab")}
          />
        ) : null}
        {mainView === "account" ? (
          <AccountSettingsPage
            accessToken={session.accessToken}
            profile={completeProfile}
            session={session}
            onClose={closeMainView}
            storageKey={storageKey(userStorage, "accountTab")}
          />
        ) : null}
        {mainView === "appearance" ? (
          <AppearancePage
            currentTheme={theme}
            themes={themeOptions}
            onClose={closeMainView}
            onThemeChange={setTheme}
          />
        ) : null}
      </main>

      <ConfirmActionModal
        confirmLabel="Logout"
        description="You will be signed out of this CONVO session and returned to the welcome screen."
        isBusy={isLoggingOut}
        isOpen={isLogoutConfirmOpen}
        title="Logout from CONVO?"
        tone="warning"
        onCancel={() => setIsLogoutConfirmOpen(false)}
        onConfirm={() => void handleLogout()}
      />
    </div>
  )
}

export default ConvoLayoutPage
