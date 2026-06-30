export type AppEnvironment = "local" | "production";

const requireEnv = (
  key: string,
  value: string | undefined,
): string => {
  if (!value || value.trim() === "") {
    throw new Error(
      `[Environment] Missing required environment variable: ${key}`,
    );
  }

  return value.replace(/\/$/, "");
};

export const env = {
  appName: requireEnv(
    "VITE_APP_NAME",
    import.meta.env.VITE_APP_NAME,
  ),

  appEnv: requireEnv(
    "VITE_APP_ENV",
    import.meta.env.VITE_APP_ENV,
  ) as AppEnvironment,

  identityApiBaseUrl: requireEnv(
    "VITE_IDENTITY_API_BASE_URL",
    import.meta.env.VITE_IDENTITY_API_BASE_URL,
  ),

  messengerApiBaseUrl: requireEnv(
    "VITE_MESSENGER_API_BASE_URL",
    import.meta.env.VITE_MESSENGER_API_BASE_URL,
  ),

  messengerWsBaseUrl: requireEnv(
    "VITE_MESSENGER_WS_BASE_URL",
    import.meta.env.VITE_MESSENGER_WS_BASE_URL,
  ),

  enableDevDiagnostics:
    import.meta.env.VITE_ENABLE_DEV_DIAGNOSTICS === "true",
} as const;

export default env;