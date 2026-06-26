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

const seoMarker = "data-convo-seo"

function upsertMeta(
  parent: HTMLElement,
  attributes: Record<string, string>,
) {
  const element = document.createElement("meta")

  Object.entries(attributes).forEach(([key, value]) => {
    element.setAttribute(key, value)
  })

  element.setAttribute(seoMarker, "true")
  parent.appendChild(element)
}

function upsertLink(parent: HTMLElement, rel: string, href: string) {
  const element = document.createElement("link")
  element.setAttribute("rel", rel)
  element.setAttribute("href", href)
  element.setAttribute(seoMarker, "true")
  parent.appendChild(element)
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
  imagePath = "/CONVO-social-preview.png",
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

    upsertMeta(document.head, { name: "description", content: description })
    upsertMeta(document.head, { name: "robots", content: robots })
    upsertLink(document.head, "canonical", canonicalUrl)

    upsertMeta(document.head, { property: "og:title", content: title })
    upsertMeta(document.head, {
      property: "og:description",
      content: description,
    })
    upsertMeta(document.head, { property: "og:url", content: canonicalUrl })
    upsertMeta(document.head, { property: "og:type", content: type })
    upsertMeta(document.head, { property: "og:image", content: imageUrl })

    upsertMeta(document.head, {
      name: "twitter:card",
      content: "summary_large_image",
    })
    upsertMeta(document.head, { name: "twitter:title", content: title })
    upsertMeta(document.head, {
      name: "twitter:description",
      content: description,
    })
    upsertMeta(document.head, { name: "twitter:image", content: imageUrl })

    jsonLd.forEach((entry) => upsertJsonLd(document.head, entry))
  }, [canonicalPath, description, imagePath, jsonLd, robots, title, type])

  return null
}

export default SeoMeta
