import { env } from "@/config/env"

export function absoluteUrl(path: string) {
  const siteUrl = env.publicSiteUrl.replace(/\/+$/, "")

  if (!path || path === "/") {
    return `${siteUrl}/`
  }

  if (/^https?:\/\//i.test(path)) {
    return path
  }

  return `${siteUrl}${path.startsWith("/") ? path : `/${path}`}`
}
