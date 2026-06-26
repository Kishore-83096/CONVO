const identityApiBaseUrl =
  import.meta.env.VITE_IDENTITY_API_BASE_URL?.trim().replace(/\/+$/, "") ?? ""
const configuredPublicSiteUrl =
  import.meta.env.VITE_PUBLIC_SITE_URL?.trim().replace(/\/+$/, "")
const runtimeOrigin =
  typeof window !== "undefined" ? window.location.origin : ""
const fallbackPublicSiteUrl = "https://convo-5wqy.onrender.com"
const publicSiteUrl = configuredPublicSiteUrl || runtimeOrigin || fallbackPublicSiteUrl

export const env = {
  identityApiBaseUrl,
  publicSiteUrl,
  mode: import.meta.env.MODE,
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
} as const
