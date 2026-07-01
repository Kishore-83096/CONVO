type AppEnvironment = "local" | "development" | "production" | "test";

type FrontendEnv = {
  appEnv: AppEnvironment;
  appName: string;

  identityApiBaseUrl: string;
  messengerApiBaseUrl: string;
  messengerWsUrl: string;
  apiTimeoutMs: number;

  cloudinaryCloudName: string;

  enableE2ee: boolean;
  enableRecovery: boolean;
  enableGroups: boolean;
  enableAttachments: boolean;
  enableRealtime: boolean;

  realtimeHeartbeatFallbackSeconds: number;
};

function readRequiredString(key: keyof ImportMetaEnv): string {
  const value = import.meta.env[key];

  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`Missing required frontend environment variable: ${key}`);
  }

  return value.trim();
}

function readOptionalString(key: keyof ImportMetaEnv): string {
  const value = import.meta.env[key];

  if (typeof value !== "string") {
    return "";
  }

  return value.trim();
}

function readBoolean(key: keyof ImportMetaEnv): boolean {
  const value = readRequiredString(key).toLowerCase();

  if (value === "true") {
    return true;
  }

  if (value === "false") {
    return false;
  }

  throw new Error(`Invalid boolean value for ${key}. Expected true or false.`);
}

function readNumber(key: keyof ImportMetaEnv): number {
  const value = Number(readRequiredString(key));

  if (!Number.isFinite(value)) {
    throw new Error(`Invalid number value for ${key}.`);
  }

  return value;
}

function readAppEnvironment(): AppEnvironment {
  const value = readRequiredString("VITE_APP_ENV") as AppEnvironment;

  const allowed: AppEnvironment[] = [
    "local",
    "development",
    "production",
    "test",
  ];

  if (!allowed.includes(value)) {
    throw new Error(
      `Invalid VITE_APP_ENV value "${value}". Expected one of: ${allowed.join(
        ", ",
      )}`,
    );
  }

  return value;
}

function assertHttpUrl(key: keyof ImportMetaEnv, value: string): void {
  if (!value.startsWith("http://") && !value.startsWith("https://")) {
    throw new Error(`${key} must start with http:// or https://`);
  }
}

function assertWsUrl(key: keyof ImportMetaEnv, value: string): void {
  if (!value.startsWith("ws://") && !value.startsWith("wss://")) {
    throw new Error(`${key} must start with ws:// or wss://`);
  }
}

const identityApiBaseUrl = readRequiredString("VITE_IDENTITY_API_BASE_URL");
const messengerApiBaseUrl = readRequiredString("VITE_MESSENGER_API_BASE_URL");
const messengerWsUrl = readRequiredString("VITE_MESSENGER_WS_URL");

assertHttpUrl("VITE_IDENTITY_API_BASE_URL", identityApiBaseUrl);
assertHttpUrl("VITE_MESSENGER_API_BASE_URL", messengerApiBaseUrl);
assertWsUrl("VITE_MESSENGER_WS_URL", messengerWsUrl);

export const env: FrontendEnv = {
  appEnv: readAppEnvironment(),
  appName: readRequiredString("VITE_APP_NAME"),

  identityApiBaseUrl,
  messengerApiBaseUrl,
  messengerWsUrl,
  apiTimeoutMs: readNumber("VITE_API_TIMEOUT_MS"),

  cloudinaryCloudName: readOptionalString("VITE_CLOUDINARY_CLOUD_NAME"),

  enableE2ee: readBoolean("VITE_ENABLE_E2EE"),
  enableRecovery: readBoolean("VITE_ENABLE_RECOVERY"),
  enableGroups: readBoolean("VITE_ENABLE_GROUPS"),
  enableAttachments: readBoolean("VITE_ENABLE_ATTACHMENTS"),
  enableRealtime: readBoolean("VITE_ENABLE_REALTIME"),

  realtimeHeartbeatFallbackSeconds: readNumber(
    "VITE_REALTIME_HEARTBEAT_FALLBACK_SECONDS",
  ),
};
