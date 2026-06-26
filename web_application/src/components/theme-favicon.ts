import {
  brandThemeIcons,
  currentDocumentTheme,
} from "@/components/brand-theme-icons"

function iconLinks() {
  return [
    document.querySelector<HTMLLinkElement>('link[rel="icon"]'),
    document.querySelector<HTMLLinkElement>('link[rel="apple-touch-icon"]'),
  ].filter((link): link is HTMLLinkElement => Boolean(link))
}

function updateThemeFavicon() {
  const icon = brandThemeIcons[currentDocumentTheme()]

  for (const link of iconLinks()) {
    link.href = icon
  }
}

export function startThemeFaviconSync() {
  if (typeof document === "undefined") {
    return
  }

  updateThemeFavicon()

  const observer = new MutationObserver(updateThemeFavicon)

  observer.observe(document.documentElement, {
    attributeFilter: ["data-theme"],
    attributes: true,
  })
}
