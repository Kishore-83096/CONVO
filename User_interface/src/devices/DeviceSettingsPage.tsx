import {
  Cpu,
  KeyRound,
  RadioTower,
  ShieldCheck,
} from "lucide-react";
import {
  type FormEvent,
  useState,
} from "react";

import { isApiError } from "@/api/api-errors";
import {
  devicesApi,
  normalizeRegisteredDevice,
  type ClaimPreKeyBundlesRequest,
  type RegisterDeviceRequest,
  type UploadOneTimePreKeysRequest,
} from "@/devices/devices-api";
import { Button, Input } from "@/components/ui";

const defaultDevicePayload = JSON.stringify(
  {
    device_name: "Chrome on Windows",
    platform: "web",
    registration_id: 184728391,
    identity_key_public: "base64-public-identity-key",
    signed_prekey_id: 1,
    signed_prekey_public: "base64-signed-prekey",
    signed_prekey_signature: "base64-signature",
    key_algorithm: "curve25519",
    key_bundle_version: 1,
  },
  null,
  2,
);

const defaultPrekeysPayload = JSON.stringify(
  {
    prekeys: [
      {
        key_id: 1001,
        public_key: "base64-one-time-prekey",
      },
    ],
  },
  null,
  2,
);

export function DeviceSettingsPage() {
  const [devicePayload, setDevicePayload] = useState(defaultDevicePayload);
  const [prekeysPayload, setPrekeysPayload] = useState(defaultPrekeysPayload);
  const [deviceId, setDeviceId] = useState("");
  const [recipientUserId, setRecipientUserId] = useState("");
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

  async function handleWhoami() {
    await runAction("whoami", () => devicesApi.whoami());
  }

  async function handleRegisterDevice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    await runAction("register", async () => {
      const payload = parseJson<RegisterDeviceRequest>(devicePayload);
      const response = await devicesApi.registerDevice(payload);
      const registeredDevice = normalizeRegisteredDevice(response.data);

      if (registeredDevice?.id) {
        setDeviceId(registeredDevice.id);
      }

      return response;
    });
  }

  async function handleUploadPrekeys(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    await runAction("prekeys", () => {
      const trimmedDeviceId = deviceId.trim();

      if (!trimmedDeviceId) {
        throw new Error("Device ID is required.");
      }

      return devicesApi.uploadPreKeys(
        trimmedDeviceId,
        parseJson<UploadOneTimePreKeysRequest>(prekeysPayload),
      );
    });
  }

  async function handleClaimBundles(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    await runAction("claim", () => {
      const payload: ClaimPreKeyBundlesRequest = {
        recipient_user_id: recipientUserId.trim(),
      };

      if (!payload.recipient_user_id) {
        throw new Error("Recipient user ID is required.");
      }

      return devicesApi.claimPreKeyBundles(payload);
    });
  }

  return (
    <section className="settings-panel security-panel">
      <div className="settings-panel__header">
        <ShieldCheck size={20} aria-hidden="true" />
        <div>
          <h2>Device and prekeys</h2>
          <p>
            Verify Messenger auth, register this browser device, upload public
            one-time prekeys, and claim recipient public bundles.
          </p>
        </div>
      </div>

      {error && (
        <div className="settings-error" role="alert">
          {error}
        </div>
      )}

      <div className="security-action-row">
        <Button
          variant="secondary"
          leftIcon={<RadioTower size={16} aria-hidden="true" />}
          loading={busyAction === "whoami"}
          onClick={handleWhoami}
        >
          Check Token
        </Button>
      </div>

      <form className="settings-form" onSubmit={handleRegisterDevice}>
        <JsonTextarea
          label="Device registration payload"
          value={devicePayload}
          onChange={setDevicePayload}
        />
        <div className="settings-actions">
          <Button
            type="submit"
            leftIcon={<Cpu size={16} aria-hidden="true" />}
            loading={busyAction === "register"}
          >
            Register Device
          </Button>
        </div>
      </form>

      <form className="settings-form" onSubmit={handleUploadPrekeys}>
        <Input
          label="Device ID"
          value={deviceId}
          onChange={(event) => setDeviceId(event.target.value)}
          fullWidth
        />
        <JsonTextarea
          label="Prekey upload payload"
          value={prekeysPayload}
          onChange={setPrekeysPayload}
        />
        <div className="settings-actions">
          <Button
            type="submit"
            leftIcon={<KeyRound size={16} aria-hidden="true" />}
            loading={busyAction === "prekeys"}
          >
            Upload Prekeys
          </Button>
        </div>
      </form>

      <form className="settings-form" onSubmit={handleClaimBundles}>
        <Input
          label="Recipient user ID"
          value={recipientUserId}
          onChange={(event) => setRecipientUserId(event.target.value)}
          fullWidth
        />
        <div className="settings-actions">
          <Button
            type="submit"
            variant="secondary"
            loading={busyAction === "claim"}
          >
            Claim Prekey Bundles
          </Button>
        </div>
      </form>

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

  return "Messenger device request failed.";
}
