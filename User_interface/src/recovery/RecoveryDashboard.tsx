import {
  Activity,
  FileClock,
  KeyRound,
  RefreshCw,
  ShieldOff,
} from "lucide-react";
import {
  type FormEvent,
  useState,
} from "react";

import { isApiError } from "@/api/api-errors";
import { Button, Input } from "@/components/ui";
import {
  recoveryApi,
  type RecoveryBackfillRequest,
  type RecoveryPublicKeysRequest,
  type RecoveryRewrapRequest,
  type RecoveryRotateRequest,
  type RecoverySetupRequest,
} from "@/recovery/recovery-api";

const defaultSetupPayload = JSON.stringify(
  {
    recovery_public_key: "base64-recovery-public-key",
    encrypted_recovery_private_key: "base64-encrypted-recovery-private-key",
    encryption_metadata: {
      algorithm: "xchacha20poly1305-ietf",
      nonce: "base64-24-byte-nonce",
      unlock_method: "recovery_key",
      kdf: "hkdf-sha256",
      bundle_schema: "myna.recovery.private-key.v1",
    },
  },
  null,
  2,
);

const defaultResolvePayload = JSON.stringify(
  {
    user_ids: ["1", "2"],
  },
  null,
  2,
);

const defaultRewrapPayload = JSON.stringify(
  {
    device_id: "",
    envelopes: [],
  },
  null,
  2,
);

const defaultBackfillPayload = JSON.stringify(
  {
    device_id: "",
    recovery_key_version: 1,
    envelopes: [],
  },
  null,
  2,
);

const defaultRotatePayload = JSON.stringify(
  {
    ...JSON.parse(defaultSetupPayload),
    current_recovery_version: 1,
    recovery_envelopes: [],
  },
  null,
  2,
);

export function RecoveryDashboard() {
  const [setupPayload, setSetupPayload] = useState(defaultSetupPayload);
  const [resolvePayload, setResolvePayload] = useState(defaultResolvePayload);
  const [rewrapPayload, setRewrapPayload] = useState(defaultRewrapPayload);
  const [backfillPayload, setBackfillPayload] = useState(defaultBackfillPayload);
  const [rotatePayload, setRotatePayload] = useState(defaultRotatePayload);
  const [candidateDeviceId, setCandidateDeviceId] = useState("");
  const [confirmDisable, setConfirmDisable] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<unknown>(null);

  async function runAction(
    action: string,
    callback: () => Promise<unknown>,
  ) {
    setBusyAction(action);
    setError(null);

    try {
      const response = await callback();
      setResult(response);
      return response;
    } catch (caught) {
      setError(errorMessage(caught));
      setResult(null);
      return undefined;
    } finally {
      setBusyAction(null);
    }
  }

  function submitJson<T>(
    action: string,
    value: string,
    callback: (payload: T) => Promise<unknown>,
  ) {
    return (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      void runAction(action, () => callback(parseJson<T>(value)));
    };
  }

  async function handleBackfillCandidates(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    await runAction("candidates", () => {
      const deviceId = candidateDeviceId.trim();

      if (!deviceId) {
        throw new Error("Device ID is required.");
      }

      return recoveryApi.backfillCandidates(deviceId);
    });
  }

  async function handleDisableRecovery() {
    await runAction("disable", () => {
      if (confirmDisable !== "DISABLE") {
        throw new Error("Type DISABLE to confirm recovery deletion.");
      }

      return recoveryApi.disable();
    });
  }

  return (
    <section className="settings-panel security-panel">
      <div className="settings-panel__header">
        <KeyRound size={20} aria-hidden="true" />
        <div>
          <h2>Encrypted recovery</h2>
          <p>
            Configure recovery, inspect coverage, resolve public keys, restore
            history, backfill old messages, rotate keys, or disable recovery.
          </p>
        </div>
      </div>

      {error && (
        <div className="settings-error" role="alert">
          {error}
        </div>
      )}

      <div className="security-action-grid">
        <Button
          variant="secondary"
          leftIcon={<Activity size={16} aria-hidden="true" />}
          loading={busyAction === "status"}
          onClick={() => void runAction("status", recoveryApi.status)}
        >
          Status
        </Button>
        <Button
          variant="secondary"
          loading={busyAction === "bundle"}
          onClick={() => void runAction("bundle", recoveryApi.bundle)}
        >
          Bundle
        </Button>
        <Button
          variant="secondary"
          loading={busyAction === "history"}
          onClick={() => void runAction("history", recoveryApi.history)}
        >
          History
        </Button>
        <Button
          variant="secondary"
          loading={busyAction === "coverage"}
          onClick={() => void runAction("coverage", recoveryApi.coverage)}
        >
          Coverage
        </Button>
      </div>

      <form
        className="settings-form"
        onSubmit={submitJson<RecoverySetupRequest>(
          "setup",
          setupPayload,
          recoveryApi.setup,
        )}
      >
        <JsonTextarea
          label="Recovery setup payload"
          value={setupPayload}
          onChange={setSetupPayload}
        />
        <div className="settings-actions">
          <Button type="submit" loading={busyAction === "setup"}>
            Setup Recovery
          </Button>
        </div>
      </form>

      <form
        className="settings-form"
        onSubmit={submitJson<RecoveryPublicKeysRequest>(
          "resolve",
          resolvePayload,
          recoveryApi.resolvePublicKeys,
        )}
      >
        <JsonTextarea
          label="Resolve public keys payload"
          value={resolvePayload}
          onChange={setResolvePayload}
        />
        <div className="settings-actions">
          <Button
            type="submit"
            variant="secondary"
            loading={busyAction === "resolve"}
          >
            Resolve Public Keys
          </Button>
        </div>
      </form>

      <form className="settings-form" onSubmit={handleBackfillCandidates}>
        <Input
          label="Backfill candidate device ID"
          value={candidateDeviceId}
          onChange={(event) => setCandidateDeviceId(event.target.value)}
          fullWidth
        />
        <div className="settings-actions">
          <Button
            type="submit"
            variant="secondary"
            leftIcon={<FileClock size={16} aria-hidden="true" />}
            loading={busyAction === "candidates"}
          >
            Load Candidates
          </Button>
        </div>
      </form>

      <form
        className="settings-form"
        onSubmit={submitJson<RecoveryBackfillRequest>(
          "backfill",
          backfillPayload,
          recoveryApi.backfill,
        )}
      >
        <JsonTextarea
          label="Backfill payload"
          value={backfillPayload}
          onChange={setBackfillPayload}
        />
        <div className="settings-actions">
          <Button
            type="submit"
            variant="secondary"
            loading={busyAction === "backfill"}
          >
            Backfill Recovery
          </Button>
        </div>
      </form>

      <form
        className="settings-form"
        onSubmit={submitJson<RecoveryRewrapRequest>(
          "rewrap",
          rewrapPayload,
          recoveryApi.rewrap,
        )}
      >
        <JsonTextarea
          label="Rewrap payload"
          value={rewrapPayload}
          onChange={setRewrapPayload}
        />
        <div className="settings-actions">
          <Button
            type="submit"
            variant="secondary"
            loading={busyAction === "rewrap"}
          >
            Rewrap To Device
          </Button>
        </div>
      </form>

      <form
        className="settings-form"
        onSubmit={submitJson<RecoveryRotateRequest>(
          "rotate",
          rotatePayload,
          recoveryApi.rotate,
        )}
      >
        <JsonTextarea
          label="Rotation payload"
          value={rotatePayload}
          onChange={setRotatePayload}
        />
        <div className="settings-actions">
          <Button
            type="submit"
            variant="secondary"
            leftIcon={<RefreshCw size={16} aria-hidden="true" />}
            loading={busyAction === "rotate"}
          >
            Rotate Recovery
          </Button>
        </div>
      </form>

      <div className="settings-form security-danger-zone">
        <Input
          label="Type DISABLE to delete recovery"
          value={confirmDisable}
          onChange={(event) => setConfirmDisable(event.target.value)}
          fullWidth
        />
        <div className="settings-actions">
          <Button
            variant="danger"
            leftIcon={<ShieldOff size={16} aria-hidden="true" />}
            loading={busyAction === "disable"}
            onClick={handleDisableRecovery}
          >
            Disable Recovery
          </Button>
        </div>
      </div>

      <ResponsePanel value={result} />
    </section>
  );
}

function JsonTextarea({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange(value: string): void;
}) {
  return (
    <label className="json-field">
      <span>{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
      />
    </label>
  );
}

function ResponsePanel({ value }: { value: unknown }) {
  if (!value) {
    return null;
  }

  return (
    <div className="api-response">
      <strong>Last response</strong>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}

function parseJson<T>(value: string): T {
  try {
    return JSON.parse(value) as T;
  } catch {
    throw new Error("JSON payload is not valid.");
  }
}

function errorMessage(error: unknown): string {
  if (isApiError(error) || error instanceof Error) {
    return error.message;
  }

  return "Recovery request failed.";
}
