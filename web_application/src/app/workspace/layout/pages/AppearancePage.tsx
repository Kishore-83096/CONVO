import { Check, X } from "lucide-react"

interface ThemeOption {
  id: string
  name: string
  colors: string[]
}

interface AppearancePageProps {
  currentTheme: string
  themes: ThemeOption[]
  onClose: () => void
  onThemeChange: (theme: string) => void
}

function AppearancePage({
  currentTheme,
  themes,
  onClose,
  onThemeChange,
}: AppearancePageProps) {
  return (
    <section className="main-view workspace-view active">
      <header className="workspace-header">
        <div className="workspace-title-row">
          <div>
            <h2>Appearance</h2>
          </div>
          <button
            className="main-close-button"
            type="button"
            aria-label="Close"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className="workspace-content">
        <section className="workspace-panel active">
          <div className="appearance-theme-grid">
            {themes.map((theme) => (
              <button
                className={`appearance-theme-option ${
                  currentTheme === theme.id ? "active" : ""
                }`}
                key={theme.id}
                type="button"
                onClick={() => onThemeChange(theme.id)}
              >
                <span className="appearance-swatch-row" aria-hidden="true">
                  {theme.colors.map((color) => (
                    <span
                      className="appearance-swatch"
                      key={color}
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </span>
                <span>{theme.name}</span>
                {currentTheme === theme.id ? (
                  <Check className="appearance-theme-check" aria-hidden="true" />
                ) : null}
              </button>
            ))}
          </div>
        </section>
      </div>
    </section>
  )
}

export default AppearancePage
