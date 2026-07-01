import { Link } from "react-router-dom";

import { PageShell } from "../../../shared/ui/PageShell";
import { useMessengerHealth } from "../hooks";

export function MessengerHealthPage() {
  const healthQuery = useMessengerHealth();
  const result = healthQuery.data;

  return (
    <PageShell
      eyebrow="Sprint 0 Phase 0.9"
      title="Messenger Health"
      description="This page checks the public Messenger service health endpoint."
    >
      <div className="health-panel">
        <div className="health-row">
          <strong>Endpoint</strong>
          <span>GET /health/</span>
        </div>

        <div className="health-row">
          <strong>Status</strong>
          <span className="health-status-line">
            <span
              aria-hidden="true"
              className={
                result?.ok ? "health-light health-light--ok" : "health-light"
              }
            />
            {healthQuery.isLoading
              ? "Checking..."
              : result?.ok
                ? "Healthy response received"
                : "Health check failed"}
          </span>
        </div>

        {result ? (
          <div className={result.ok ? "health-success" : "health-error"}>
            <div
              aria-label={result.ok ? "Service healthy" : "Service unhealthy"}
              className={
                result.ok ? "health-light health-light--ok" : "health-light"
              }
            />
            <div>
              <strong>{result.ok ? "Messenger service is online" : "Messenger service needs attention"}</strong>
              <p>HTTP {result.status} · {result.message ?? "Response received."}</p>
            </div>
          </div>
        ) : null}

        {!healthQuery.isLoading && result && !result.ok ? (
          <div className="notice">
            Messenger backend may not be running, the URL may be wrong, or CORS
            may not allow this frontend origin yet.
          </div>
        ) : null}

        <div className="actions">
          <button
            className="button"
            type="button"
            onClick={() => void healthQuery.refetch()}
          >
            Check again
          </button>

          <Link className="button secondary" to="/">
            Back home
          </Link>
        </div>
      </div>
    </PageShell>
  );
}
