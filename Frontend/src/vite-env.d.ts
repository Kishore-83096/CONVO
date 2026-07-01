/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_ENV: string;
  readonly VITE_APP_NAME: string;

  readonly VITE_IDENTITY_API_BASE_URL: string;
  readonly VITE_MESSENGER_API_BASE_URL: string;
  readonly VITE_MESSENGER_WS_URL: string;
  readonly VITE_API_TIMEOUT_MS: string;

  readonly VITE_CLOUDINARY_CLOUD_NAME?: string;

  readonly VITE_ENABLE_E2EE: string;
  readonly VITE_ENABLE_RECOVERY: string;
  readonly VITE_ENABLE_GROUPS: string;
  readonly VITE_ENABLE_ATTACHMENTS: string;
  readonly VITE_ENABLE_REALTIME: string;

  readonly VITE_REALTIME_HEARTBEAT_FALLBACK_SECONDS: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
