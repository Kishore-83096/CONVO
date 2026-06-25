import { useEffect, useState, type FormEvent } from "react"
import { useNavigate } from "react-router"

import { ApiClientError } from "@/api/client"
import { login, registerAccount } from "@/app/convo_identity/auth/auth.api"
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

type AuthTab = "features" | "register" | "login"

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

function WelcomePage() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<AuthTab>("features")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [loginMethod, setLoginMethod] = useState<LoginMethod>("username")
  const [loginIdentifier, setLoginIdentifier] = useState("")
  const [notice, setNotice] = useState<Notice | null>(null)

  useEffect(() => {
    if (getAuthSession()) {
      navigate("/userstart", { replace: true })
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
      navigate("/userstart", { replace: true })
    } catch (error) {
      setNotice(apiErrorNotice(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  const changeTab = (value: string) => {
    setActiveTab(value as AuthTab)
    setNotice(null)
  }

  return (
    <Tabs
      className="welcome-tabs"
      value={activeTab}
      onValueChange={changeTab}
    >
      <div className="welcome-page">
        <header className="welcome-header">
          <div className="welcome-container welcome-header-content">
            <button
              className="welcome-brand"
              type="button"
              onClick={() => changeTab("features")}
              aria-label="Show CONVO features"
            >
              <img className="welcome-logo" src={convoLogo} alt="" />
              <span>CONVO</span>
            </button>

            <TabsList className="auth-tabs-list" variant="line">
              <TabsTrigger value="register">Join us</TabsTrigger>
              <TabsTrigger value="login">Login</TabsTrigger>
            </TabsList>
          </div>
        </header>

        <main className="welcome-container welcome-main">
          <TabsContent className="features-view" value="features">
            <section className="welcome-intro">
              <p className="welcome-eyebrow">Welcome to CONVO</p>
              <h1 className="welcome-title">
                One quiet place for your conversations.
              </h1>
              <p className="welcome-description">
                Create your identity, shape your profile, and keep the people
                important to you close inside one clean workspace.
              </p>
            </section>

            <section className="features-grid" aria-label="CONVO features">
              <article>
                <span>01</span>
                <h2>Your identity</h2>
                <p>
                  Get your CONVO identity and contact number when you create
                  an account.
                </p>
              </article>
              <article>
                <span>02</span>
                <h2>Your profile</h2>
                <p>
                  Keep your bio, picture, address, and important events in one
                  profile.
                </p>
              </article>
              <article>
                <span>03</span>
                <h2>Your contacts</h2>
                <p>
                  Find CONVO users and manage the people you want to stay
                  connected with.
                </p>
              </article>
            </section>
          </TabsContent>

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
                onClick={() => changeTab("features")}
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
                    <Input
                      id="register_password"
                      name="password"
                      type="password"
                      autoComplete="new-password"
                      minLength={8}
                      maxLength={128}
                      required
                    />
                  </div>
                  <div className="auth-field">
                    <Label htmlFor="confirm_password">Confirm password</Label>
                    <Input
                      id="confirm_password"
                      name="confirm_password"
                      type="password"
                      autoComplete="new-password"
                      maxLength={128}
                      required
                    />
                  </div>
                </div>

                <Button className="auth-submit" disabled={isSubmitting}>
                  {isSubmitting ? "Creating account..." : "Create account"}
                </Button>
              </form>
              <p className="auth-switch">
                Already have an account?{" "}
                <button type="button" onClick={() => changeTab("login")}>
                  Login
                </button>
              </p>
            </section>
          </TabsContent>

          <TabsContent className="auth-view" value="login">
            <section className="auth-panel">
              <button
                className="auth-close"
                type="button"
                onClick={() => changeTab("features")}
                aria-label="Close login"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6 6L18 18" />
                  <path d="M18 6L6 18" />
                </svg>
              </button>
              <div className="auth-heading">
                <p>Welcome back</p>
                <h1>Login to CONVO</h1>
              </div>
              <form className="auth-form" onSubmit={handleLogin}>
                <div className="auth-field">
                  <Label htmlFor="login_method">Login with</Label>
                  <select
                    id="login_method"
                    className="auth-method-select"
                    value={loginMethod}
                    onChange={(event) => {
                      setLoginMethod(event.target.value as LoginMethod)
                      setLoginIdentifier("")
                    }}
                  >
                    <option value="username">Username</option>
                    <option value="email">CONVO email</option>
                    <option value="contact_number">Contact number</option>
                  </select>
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
                  <Input
                    id="login_password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    maxLength={128}
                    required
                  />
                </div>

                <Button className="auth-submit" disabled={isSubmitting}>
                  {isSubmitting ? "Signing in..." : "Login"}
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
        </main>
      </div>
    </Tabs>
  )
}

export default WelcomePage
