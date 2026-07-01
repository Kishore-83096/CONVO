import { useTheme } from "../../app/providers/useTheme";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const themeLabel = theme === "light" ? "Light" : "Dark";
  const nextThemeLabel = theme === "light" ? "dark" : "light";

  return (
    <button
      aria-label={`Switch to ${nextThemeLabel} theme`}
      className="theme-toggle"
      type="button"
      onClick={toggleTheme}
    >
      <span aria-hidden="true" className="theme-toggle__icon" />
      {themeLabel}
    </button>
  );
}
