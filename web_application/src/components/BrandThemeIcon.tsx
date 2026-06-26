import { useEffect, useState, type ImgHTMLAttributes } from "react"

import {
  brandThemeIcons,
  currentDocumentTheme,
  isBrandTheme,
} from "@/components/brand-theme-icons"

interface BrandThemeIconProps
  extends Omit<ImgHTMLAttributes<HTMLImageElement>, "alt" | "src"> {
  alt?: string
  theme?: string
}

function BrandThemeIcon({
  alt = "Myna logo",
  theme,
  ...props
}: BrandThemeIconProps) {
  const [documentTheme, setDocumentTheme] = useState(currentDocumentTheme)
  const activeTheme = isBrandTheme(theme) ? theme : documentTheme

  useEffect(() => {
    if (theme || typeof document === "undefined") {
      return undefined
    }

    const observer = new MutationObserver(() => {
      setDocumentTheme(currentDocumentTheme())
    })

    observer.observe(document.documentElement, {
      attributeFilter: ["data-theme"],
      attributes: true,
    })

    return () => observer.disconnect()
  }, [theme])

  return <img alt={alt} src={brandThemeIcons[activeTheme]} {...props} />
}

export default BrandThemeIcon
