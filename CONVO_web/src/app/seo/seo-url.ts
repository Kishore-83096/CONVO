import { env } from "@/config/env"

export function absoluteUrl(path: string) {
  if (!path || path === "/") {
    return `${env.publicSiteUrl}/`
  }

  return `${env.publicSiteUrl}${path.startsWith("/") ? path : `/${path}`}`
}
