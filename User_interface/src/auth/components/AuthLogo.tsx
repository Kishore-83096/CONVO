import { BrandLogo } from "@/components/brand";

export function AuthLogo() {
  return (
    <header className="auth-logo">
      <BrandLogo
        className="auth-logo__brand"
        iconClassName="auth-logo__badge"
        showName={false}
      />

      <h1 className="auth-logo__title">
        MYNA
      </h1>

      <p className="auth-logo__subtitle">
        Private. Secure. Real-time messaging designed for modern communication.
      </p>
    </header>
  );
}
