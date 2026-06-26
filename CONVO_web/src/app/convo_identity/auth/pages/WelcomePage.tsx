import { useEffect, useState, type FormEvent } from "react"
import { Eye, EyeOff } from "lucide-react"
import { useNavigate } from "react-router"

import { ApiClientError } from "@/api/client"
import SeoMeta from "@/app/seo/SeoMeta"
import { login, registerAccount } from "@/app/convo_identity/auth/auth.api"
import { userHomePath } from "@/app/convo_identity/auth/auth-routes"
import {
  getAuthSession,
  saveAuthSession,
} from "@/app/convo_identity/auth/auth-session"
import type { LoginMethod } from "@/app/convo_identity/auth/auth.types"
import convoLogo from "@/assets/convo/CONVO.png"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"

import "../css/WelcomePage.css"

type AuthTab = "register" | "login"

interface Notice {
  type: "success" | "error"
  title: string
  message: string
  details?: string[]
}

const loginPlaceholders: Record<LoginMethod, string> = {
  username: "your_username",
  email: "you@convo.app",
  contact_number: "10-digit contact number",
}

const loginMethods: { id: LoginMethod; label: string }[] = [
  { id: "username", label: "Username" },
  { id: "email", label: "Email" },
  { id: "contact_number", label: "Contact" },
]

function fieldErrors(errors: unknown): string[] {
  if (!errors || typeof errors !== "object") {
    return []
  }

  return Object.values(errors).flatMap((value) => {
    if (Array.isArray(value)) {
      return value.filter((item): item is string => typeof item === "string")
    }

    return typeof value === "string" ? [value] : []
  })
}

function apiErrorNotice(error: unknown): Notice {
  if (error instanceof ApiClientError) {
    return {
      type: "error",
      title: error.status === 0 ? "Connection failed" : "Request failed",
      message: error.message,
      details: fieldErrors(error.errors),
    }
  }

  return {
    type: "error",
    title: "Request failed",
    message: "Something went wrong. Please try again.",
  }
}

interface WelcomePageProps {
  initialTab?: AuthTab
}

function WelcomePage({ initialTab = "login" }: WelcomePageProps) {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<AuthTab>(initialTab)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [loginMethod, setLoginMethod] = useState<LoginMethod>("username")
  const [loginIdentifier, setLoginIdentifier] = useState("")
  const [visiblePasswords, setVisiblePasswords] = useState({
    register: false,
    confirm: false,
    login: false,
  })
  const [notice, setNotice] = useState<Notice | null>(null)

  useEffect(() => {
    setActiveTab(initialTab)
    setNotice(null)
  }, [initialTab])

  useEffect(() => {
    const session = getAuthSession()

    if (session) {
      navigate(userHomePath(session), { replace: true })
    }
  }, [navigate])

  const handleRegister = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const formData = new FormData(form)

    setIsSubmitting(true)
    setNotice(null)

    try {
      const response = await registerAccount({
        full_name: String(formData.get("full_name") ?? "").trim(),
        username: String(formData.get("username") ?? "").trim(),
        password: String(formData.get("password") ?? ""),
        confirm_password: String(formData.get("confirm_password") ?? ""),
      })

      if (!response.data) {
        throw new Error("Registration response did not contain account data.")
      }

      form.reset()
      setLoginMethod("username")
      setLoginIdentifier(response.data.username)
      setActiveTab("login")
      navigate("/login")
      setNotice({
        type: "success",
        title: "Account created",
        message: response.message,
        details: [
          `CONVO email: ${response.data.email}`,
          `Contact number: ${response.data.contact_number}`,
        ],
      })
    } catch (error) {
      setNotice(apiErrorNotice(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)

    setIsSubmitting(true)
    setNotice(null)

    try {
      const response = await login({
        method: loginMethod,
        identifier: loginIdentifier.trim(),
        password: String(formData.get("password") ?? ""),
      })

      if (!response.data) {
        throw new Error("Login response did not contain session data.")
      }

      saveAuthSession(response.data)
      navigate(userHomePath(getAuthSession()), { replace: true })
    } catch (error) {
      setNotice(apiErrorNotice(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  const changeTab = (value: string) => {
    const nextTab = value as AuthTab

    setActiveTab(nextTab)
    setNotice(null)
    navigate(nextTab === "login" ? "/login" : "/register")
  }

  const togglePassword = (field: keyof typeof visiblePasswords) => {
    setVisiblePasswords((current) => ({
      ...current,
      [field]: !current[field],
    }))
  }

  return (
    <Tabs
      className="welcome-tabs"
      value={activeTab}
      onValueChange={changeTab}
    >
      <SeoMeta
        canonicalPath={initialTab === "register" ? "/register" : "/login"}
        description="Sign in to CONVO or create an account to access private messaging, contacts, profile, and account tools."
        robots="noindex, nofollow"
        title={initialTab === "register" ? "Create a CONVO Account" : "Sign in to CONVO"}
      />
      <div className="welcome-page">
        <header className="welcome-header">
          <div className="welcome-container welcome-header-content">
            <button
              className="welcome-brand"
              type="button"
              onClick={() => navigate("/")}
              aria-label="Show CONVO features"
            >
              <img
                className="welcome-logo"
                src={convoLogo}
                alt="CONVO logo"
                width="42"
                height="42"
              />
              <span>CONVO</span>
            </button>

            <TabsList className="auth-tabs-list" variant="line">
              <TabsTrigger value="login">Sign in</TabsTrigger>
              <TabsTrigger value="register">Create account</TabsTrigger>
            </TabsList>
          </div>
        </header>

        <main className="welcome-container welcome-main">
          <section className="auth-shell" aria-label="CONVO authentication">
            {notice && (
              <Alert
                className="auth-notice"
                variant={notice.type === "error" ? "destructive" : "default"}
              >
                <AlertTitle>{notice.title}</AlertTitle>
                <AlertDescription>
                  <p>{notice.message}</p>
                  {notice.details?.map((detail) => (
                    <p key={detail}>{detail}</p>
                  ))}
                </AlertDescription>
              </Alert>
            )}

            <TabsContent className="auth-view" value="register">
              <section className="auth-panel">
              <button
                className="auth-close"
                type="button"
                onClick={() => navigate("/")}
                aria-label="Close registration"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6 6L18 18" />
                  <path d="M18 6L6 18" />
                </svg>
              </button>
              <div className="auth-heading">
                <p>Join CONVO</p>
                <h1>Create your identity</h1>
              </div>
              <form className="auth-form" onSubmit={handleRegister}>
                <div className="auth-field">
                  <Label htmlFor="full_name">Full name</Label>
                  <Input
                    id="full_name"
                    name="full_name"
                    autoComplete="name"
                    minLength={2}
                    maxLength={100}
                    required
                  />
                </div>

                <div className="auth-field">
                  <Label htmlFor="register_username">Username</Label>
                  <Input
                    id="register_username"
                    name="username"
                    autoComplete="username"
                    minLength={3}
                    maxLength={30}
                    pattern="@?[a-z0-9_]+"
                    placeholder="your_username"
                    required
                  />
                  <p className="auth-hint">
                    Lowercase letters, numbers, and underscores only.
                  </p>
                </div>

                <div className="auth-password-grid">
                  <div className="auth-field">
                    <Label htmlFor="register_password">Password</Label>
                    <span className="auth-password-control">
                      <Input
                        id="register_password"
                        name="password"
                        type={visiblePasswords.register ? "text" : "password"}
                        autoComplete="new-password"
                        minLength={8}
                        maxLength={128}
                        required
                      />
                      <button
                        type="button"
                        aria-label={
                          visiblePasswords.register
                            ? "Hide password"
                            : "Show password"
                        }
                        onClick={() => togglePassword("register")}
                      >
                        {visiblePasswords.register ? (
                          <EyeOff aria-hidden="true" />
                        ) : (
                          <Eye aria-hidden="true" />
                        )}
                      </button>
                    </span>
                  </div>
                  <div className="auth-field">
                    <Label htmlFor="confirm_password">Confirm password</Label>
                    <span className="auth-password-control">
                      <Input
                        id="confirm_password"
                        name="confirm_password"
                        type={visiblePasswords.confirm ? "text" : "password"}
                        autoComplete="new-password"
                        maxLength={128}
                        required
                      />
                      <button
                        type="button"
                        aria-label={
                          visiblePasswords.confirm
                            ? "Hide confirm password"
                            : "Show confirm password"
                        }
                        onClick={() => togglePassword("confirm")}
                      >
                        {visiblePasswords.confirm ? (
                          <EyeOff aria-hidden="true" />
                        ) : (
                          <Eye aria-hidden="true" />
                        )}
                      </button>
                    </span>
                  </div>
                </div>

                <Button className="auth-submit" disabled={isSubmitting}>
                  {isSubmitting ? "Creating account..." : "Create account"}
                </Button>
              </form>
              <p className="auth-switch">
                Already have an account?{" "}
                <button type="button" onClick={() => changeTab("login")}>
                  Sign in
                </button>
              </p>
              </section>
            </TabsContent>

            <TabsContent className="auth-view" value="login">
              <section className="auth-panel">
              <button
                className="auth-close"
                type="button"
                onClick={() => navigate("/")}
                aria-label="Close login"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6 6L18 18" />
                  <path d="M18 6L6 18" />
                </svg>
              </button>
              <div className="auth-heading">
                <p>Welcome back</p>
                <h1>Sign in to CONVO</h1>
              </div>
              <form className="auth-form" onSubmit={handleLogin}>
                <div className="auth-field">
                  <span className="auth-field-label" id="loginMethodLabel">
                    Sign in with
                  </span>
                  <div
                    className="auth-method-segment"
                    aria-labelledby="loginMethodLabel"
                    role="group"
                  >
                    {loginMethods.map((method) => (
                      <button
                        className={loginMethod === method.id ? "active" : ""}
                        key={method.id}
                        type="button"
                        aria-pressed={loginMethod === method.id}
                        onClick={() => {
                          setLoginMethod(method.id)
                          setLoginIdentifier("")
                        }}
                      >
                        {method.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="auth-field">
                  <Label htmlFor="login_identifier">Identifier</Label>
                  <Input
                    id="login_identifier"
                    name="identifier"
                    type={loginMethod === "email" ? "email" : "text"}
                    autoComplete="username"
                    inputMode={
                      loginMethod === "contact_number" ? "numeric" : "text"
                    }
                    pattern={
                      loginMethod === "contact_number" ? "[0-9]{10}" : undefined
                    }
                    placeholder={loginPlaceholders[loginMethod]}
                    value={loginIdentifier}
                    onChange={(event) => setLoginIdentifier(event.target.value)}
                    required
                  />
                </div>

                <div className="auth-field">
                  <Label htmlFor="login_password">Password</Label>
                  <span className="auth-password-control">
                    <Input
                      id="login_password"
                      name="password"
                      type={visiblePasswords.login ? "text" : "password"}
                      autoComplete="current-password"
                      maxLength={128}
                      required
                    />
                    <button
                      type="button"
                      aria-label={
                        visiblePasswords.login ? "Hide password" : "Show password"
                      }
                      onClick={() => togglePassword("login")}
                    >
                      {visiblePasswords.login ? (
                        <EyeOff aria-hidden="true" />
                      ) : (
                        <Eye aria-hidden="true" />
                      )}
                    </button>
                  </span>
                </div>

                <Button className="auth-submit" disabled={isSubmitting}>
                  {isSubmitting ? "Signing in..." : "Sign in"}
                </Button>
              </form>
              <p className="auth-switch">
                New to CONVO?{" "}
                <button type="button" onClick={() => changeTab("register")}>
                  Create account
                </button>
              </p>
              </section>
            </TabsContent>
          </section>
        </main>
      </div>
    </Tabs>
  )
}

export default WelcomePage
