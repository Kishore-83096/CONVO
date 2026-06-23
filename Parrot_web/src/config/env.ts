const identityApiBaseUrl =
  import.meta.env.VITE_IDENTITY_API_BASE_URL?.replace(/\/+$/, "")

console.log("Vite mode:", import.meta.env.MODE)
console.log(
  "Identity API URL loaded by Vite:",
  import.meta.env.VITE_IDENTITY_API_BASE_URL,
)

if (!identityApiBaseUrl) {
  throw new Error(
    "VITE_IDENTITY_API_BASE_URL is not configured for the current environment.",
  )
}

export const env = {
  identityApiBaseUrl,
  mode: import.meta.env.MODE,
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
} as const