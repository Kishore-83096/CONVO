import { useEffect } from "react"

import { absoluteUrl } from "@/app/seo/seo-url"

interface SeoMetaProps {
  canonicalPath: string
  description: string
  imagePath?: string
  jsonLd?: Record<string, unknown>[]
  robots?: string
  title: string
  type?: "website" | "article"
}

const seoMarker = "data-myna-seo"

function setMeta(selector: string, attributes: Record<string, string>) {
  const element =
    document.head.querySelector<HTMLMetaElement>(selector) ??
    document.createElement("meta")

  Object.entries(attributes).forEach(([key, value]) => {
    element.setAttribute(key, value)
  })

  if (!element.parentElement) {
    document.head.appendChild(element)
  }
}

function setLink(rel: string, href: string) {
  const element =
    document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`) ??
    document.createElement("link")

  element.setAttribute("rel", rel)
  element.setAttribute("href", href)

  if (!element.parentElement) {
    document.head.appendChild(element)
  }
}

function upsertJsonLd(parent: HTMLElement, data: Record<string, unknown>) {
  const element = document.createElement("script")
  element.type = "application/ld+json"
  element.textContent = JSON.stringify(data)
  element.setAttribute(seoMarker, "true")
  parent.appendChild(element)
}

function SeoMeta({
  canonicalPath,
  description,
  imagePath = "/Myna-social-preview.png",
  jsonLd = [],
  robots = "index, follow",
  title,
  type = "website",
}: SeoMetaProps) {
  useEffect(() => {
    const canonicalUrl = absoluteUrl(canonicalPath)
    const imageUrl = absoluteUrl(imagePath)

    document.title = title
    document
      .querySelectorAll(`[${seoMarker}="true"]`)
      .forEach((element) => element.remove())

    setMeta('meta[name="description"]', {
      name: "description",
      content: description,
    })
    setMeta('meta[name="robots"]', { name: "robots", content: robots })
    setLink("canonical", canonicalUrl)

    setMeta('meta[property="og:title"]', { property: "og:title", content: title })
    setMeta('meta[property="og:description"]', {
      property: "og:description",
      content: description,
    })
    setMeta('meta[property="og:url"]', { property: "og:url", content: canonicalUrl })
    setMeta('meta[property="og:type"]', { property: "og:type", content: type })
    setMeta('meta[property="og:image"]', { property: "og:image", content: imageUrl })

    setMeta('meta[name="twitter:card"]', {
      name: "twitter:card",
      content: "summary_large_image",
    })
    setMeta('meta[name="twitter:title"]', { name: "twitter:title", content: title })
    setMeta('meta[name="twitter:description"]', {
      name: "twitter:description",
      content: description,
    })
    setMeta('meta[name="twitter:image"]', {
      name: "twitter:image",
      content: imageUrl,
    })

    jsonLd.forEach((entry) => upsertJsonLd(document.head, entry))
  }, [canonicalPath, description, imagePath, jsonLd, robots, title, type])

  return null
}

export default SeoMeta
