import { useEffect, useState, type ImgHTMLAttributes } from "react"

import auroraIcon from "@/assets/brand/theme-icons/theme-aurora.png"
import blueIcon from "@/assets/brand/theme-icons/theme-blue.png"
import darkIcon from "@/assets/brand/theme-icons/theme-dark.png"
import lavenderIcon from "@/assets/brand/theme-icons/theme-lavender.png"
import lightIcon from "@/assets/brand/theme-icons/theme-light.png"
import mintIcon from "@/assets/brand/theme-icons/theme-mint.png"
import pinkIcon from "@/assets/brand/theme-icons/theme-pink.png"
import sunsetIcon from "@/assets/brand/theme-icons/theme-sunset.png"

export type BrandTheme =
  | "light"
  | "dark"
  | "blue"
  | "pink"
  | "lavender"
  | "mint"
  | "sunset"
  | "aurora"

const icons: Record<BrandTheme, string> = {
  light: lightIcon,
  dark: darkIcon,
  blue: blueIcon,
  pink: pinkIcon,
  lavender: lavenderIcon,
  mint: mintIcon,
  sunset: sunsetIcon,
  aurora: auroraIcon,
}

function isBrandTheme(theme: string | undefined): theme is BrandTheme {
  return Boolean(theme && theme in icons)
}

function currentDocumentTheme() {
  if (typeof document === "undefined") {
    return "light"
  }

  const theme = document.documentElement.dataset.theme
  return isBrandTheme(theme) ? theme : "light"
}

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

  return <img alt={alt} src={icons[activeTheme]} {...props} />
}

export default BrandThemeIcon
