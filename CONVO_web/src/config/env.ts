const identityApiBaseUrl =
  import.meta.env.VITE_IDENTITY_API_BASE_URL?.replace(/\/+$/, "") ?? ""
const configuredPublicSiteUrl =
  import.meta.env.VITE_PUBLIC_SITE_URL?.replace(/\/+$/, "")
const runtimeOrigin =
  typeof window !== "undefined" ? window.location.origin : ""
const publicSiteUrl = configuredPublicSiteUrl || runtimeOrigin

if (!publicSiteUrl) {
  throw new Error(
    "VITE_PUBLIC_SITE_URL is not configured for the current environment.",
  )
}

export const env = {
  identityApiBaseUrl,
  publicSiteUrl,
  mode: import.meta.env.MODE,
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
} as const
