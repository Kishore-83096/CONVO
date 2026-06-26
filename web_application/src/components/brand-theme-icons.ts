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

export const brandThemeIcons: Record<BrandTheme, string> = {
  light: lightIcon,
  dark: darkIcon,
  blue: blueIcon,
  pink: pinkIcon,
  lavender: lavenderIcon,
  mint: mintIcon,
  sunset: sunsetIcon,
  aurora: auroraIcon,
}

export function isBrandTheme(theme: string | undefined): theme is BrandTheme {
  return Boolean(theme && theme in brandThemeIcons)
}

export function currentDocumentTheme() {
  if (typeof document === "undefined") {
    return "light"
  }

  const theme = document.documentElement.dataset.theme
  return isBrandTheme(theme) ? theme : "light"
}
