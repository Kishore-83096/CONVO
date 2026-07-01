import { Button } from "../../../shared/ui/Button";
import { useMessengerWhoami } from "../hooks";

function formatUnixSeconds(value: number): string {
  if (!Number.isFinite(value)) {
    return "Unknown";
  }

  return new Date(value * 1000).toLocaleString();
}

export function MessengerWhoamiCard() {
  const whoamiMutation = useMessengerWhoami();
  const result = whoamiMutation.data;

  async function handleVerifyMessengerToken() {
    await whoamiMutation.mutateAsync();
  }

  return (
    <section className="messenger-whoami-card">
      <div>
        <p className="eyebrow">Sprint 1 · Phase 1.6</p>
        <h2>Messenger token check</h2>
        <p>
          Verify that Messenger accepts the current Identity JWT stored in
          IndexedDB. This does not create a new session and does not store a new
          token.
        </p>
      </div>

      <Button
        disabled={whoamiMutation.isPending}
        onClick={handleVerifyMessengerToken}
        type="button"
      >
        {whoamiMutation.isPending
          ? "Checking Messenger..."
          : "Check Messenger whoami"}
      </Button>

      {result?.ok ? (
        <div className="auth-success" role="status">
          <strong>Messenger accepted this token.</strong>

          <dl className="auth-result-list">
            <div>
              <dt>Authenticated</dt>
              <dd>{String(result.data.authenticated)}</dd>
            </div>

            <div>
              <dt>Messenger user ID</dt>
              <dd>{result.data.user_id}</dd>
            </div>

            <div>
              <dt>Token type</dt>
              <dd>{result.data.token_type}</dd>
            </div>

            <div>
              <dt>Expires at</dt>
              <dd>{formatUnixSeconds(result.data.expires_at)}</dd>
            </div>
          </dl>
        </div>
      ) : null}

      {result && !result.ok ? (
        <div className="auth-error" role="alert">
          <strong>Messenger rejected this token.</strong>
          <p>{result.message}</p>
        </div>
      ) : null}
    </section>
  );
}