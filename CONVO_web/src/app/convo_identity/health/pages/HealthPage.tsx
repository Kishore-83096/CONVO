import { useCallback, useEffect, useRef, useState } from "react"

import { ApiClientError, apiRequest } from "@/api/client"
import SeoMeta from "@/app/seo/SeoMeta"
import parrotIcon from "@/assets/icons/ParrotIcon_3D_effect.svg"
import { env } from "@/config/env"

import "../css/HealthPage.css"

interface ComponentHealth {
  component: string
  status: "up" | "down"
  message: string
  latency_ms: number
  details?: {
    database_engine?: string
  }
}

interface CompleteHealth {
  service: string
  environment: string
  status: "healthy" | "degraded"
  checks: Record<string, ComponentHealth>
}

type RequestStatus = "loading" | "connected" | "error"

const componentLabels: Record<string, string> = {
  service: "Identity service",
  cloudinary: "Cloudinary",
}

function getComponentLabel(component: string, environment: string) {
  if (component === "database") {
    return environment === "production"
      ? "Production database"
      : "Development database"
  }

  return componentLabels[component] ?? component
}

function formatDatabaseEngine(engine: string) {
  return engine === "postgresql"
    ? "PostgreSQL"
    : engine.charAt(0).toUpperCase() + engine.slice(1)
}

function HealthPage() {
  const initialCheckStarted = useRef(false)
  const [requestStatus, setRequestStatus] = useState<RequestStatus>("loading")
  const [health, setHealth] = useState<CompleteHealth | null>(null)
  const [errorMessage, setErrorMessage] = useState("")
  const [checkedAt, setCheckedAt] = useState("")

  const checkHealth = useCallback(async () => {
    setRequestStatus("loading")
    setErrorMessage("")

    try {
      const response = await apiRequest<CompleteHealth>("/health/all")

      if (!response.data) {
        throw new Error("The health response did not contain service data.")
      }

      setHealth(response.data)
      setRequestStatus("connected")
      setCheckedAt(new Date().toLocaleTimeString())
    } catch (error) {
      setHealth(null)
      setRequestStatus("error")
      setCheckedAt(new Date().toLocaleTimeString())
      setErrorMessage(
        error instanceof ApiClientError || error instanceof Error
          ? error.message
          : "Unable to check the CONVO Identity service.",
      )
    }
  }, [])

  useEffect(() => {
    if (initialCheckStarted.current) {
      return
    }

    initialCheckStarted.current = true
    void checkHealth()
  }, [checkHealth])

  const isConnected = requestStatus === "connected"

  return (
    <main className="app-shell">
      <SeoMeta
        canonicalPath="/health/all"
        description="CONVO private health check page."
        robots="noindex, nofollow"
        title="CONVO Health Check"
      />
      <section className="status-page" aria-labelledby="page-title">
        <div className="brand-mark" aria-hidden="true">
          <img src={parrotIcon} alt="" />
        </div>

        <div className="intro">
          <p className="eyebrow">CONVO</p>
          <h1 id="page-title">Identity service status</h1>
          <p>
            Live connectivity check between this frontend and the CONVO
            Identity API.
          </p>
        </div>

        <section
          className={`health-card health-card--${requestStatus}`}
          aria-live="polite"
          aria-busy={requestStatus === "loading"}
        >
          <div className="health-card__header">
            <div className="status-icon" aria-hidden="true">
              {requestStatus === "loading" ? (
                <span className="spinner" />
              ) : (
                <span>{isConnected ? "✓" : "!"}</span>
              )}
            </div>

            <div className="status-copy">
              <p className="status-label">
                {requestStatus === "loading"
                  ? "Checking connection"
                  : isConnected
                    ? "Connected"
                    : "Connection failed"}
              </p>
              <h2>
                {requestStatus === "loading"
                  ? "Contacting CONVO Identity..."
                  : isConnected
                    ? "CONVO Identity is available"
                    : "CONVO Identity is unavailable"}
              </h2>
              <p>
                {requestStatus === "loading"
                  ? "A sleeping Render service can take up to a minute to respond."
                  : isConnected
                    ? `Environment: ${health?.environment ?? "unknown"}`
                    : errorMessage}
              </p>
            </div>

            <span className={`status-pill status-pill--${requestStatus}`}>
              {requestStatus === "loading"
                ? "Checking"
                : isConnected
                  ? (health?.status ?? "healthy")
                  : "Offline"}
            </span>
          </div>

          {health && (
            <div className="component-grid">
              {Object.values(health.checks).map((component) => (
                <article className="component-status" key={component.component}>
                  <div>
                    <span
                      className={`component-dot component-dot--${component.status}`}
                      aria-hidden="true"
                    />
                    <h3>
                      {getComponentLabel(
                        component.component,
                        health.environment,
                      )}
                    </h3>
                  </div>
                  <p>{component.message}</p>
                  <div className="component-meta">
                    {component.component === "service" && (
                      <code title={env.identityApiBaseUrl}>
                        {env.identityApiBaseUrl}
                      </code>
                    )}
                    {component.details?.database_engine && (
                      <span>
                        {formatDatabaseEngine(
                          component.details.database_engine,
                        )}
                      </span>
                    )}
                    <span>{component.latency_ms.toFixed(2)} ms</span>
                  </div>
                </article>
              ))}
            </div>
          )}

          <div className="health-card__footer">
            <div>
              <span>API endpoint</span>
              <code>{env.identityApiBaseUrl}/health/all</code>
            </div>
            <button
              type="button"
              onClick={() => void checkHealth()}
              disabled={requestStatus === "loading"}
            >
              {requestStatus === "loading" ? "Checking…" : "Check again"}
            </button>
          </div>
        </section>

        {checkedAt && <p className="last-checked">Last checked at {checkedAt}</p>}
      </section>
    </main>
  )
}

export default HealthPage
