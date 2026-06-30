import mynaLogo from "@/assets/brand/myna-logo.png";

interface BrandLogoProps {
  className?: string;
  iconClassName?: string;
  showName?: boolean;
}

export function BrandLogo({
  className = "brand-lockup",
  iconClassName = "brand-icon",
  showName = true,
}: BrandLogoProps) {
  return (
    <span className={className}>
      <img
        className={iconClassName}
        src={mynaLogo}
        alt="MYNA logo"
      />
      {showName && <span className="brand-name">MYNA</span>}
    </span>
  );
}
