import { Button } from "../../../shared/ui/Button";
import { useMyProfileAddress } from "../hooks";

function formatValue(value: string | number | boolean | null | undefined) {
  if (value === true) {
    return "Yes";
  }

  if (value === false) {
    return "No";
  }

  if (value === null || value === undefined || value === "") {
    return "Not added yet";
  }

  return String(value);
}

type DetailRowProps = {
  label: string;
  value: string | number | boolean | null | undefined;
};

function DetailRow({ label, value }: DetailRowProps) {
  return (
    <div className="health-row">
      <strong>{label}</strong>
      <span>{formatValue(value)}</span>
    </div>
  );
}

export function AddressProfileReadPanel() {
  const addressProfileQuery = useMyProfileAddress();
  const result = addressProfileQuery.data;
  const addressProfile = result?.ok ? result.data : undefined;

  return (
    <section className="account-settings-panel" aria-label="Address profile">
      <div className="section-heading">
        <p className="eyebrow">Phase 2.6</p>
        <h2>Address Profile</h2>
        <p>
          This section directly reads your address profile using GET
          /profiles/me/address. Create, update, and delete are intentionally not
          added in this phase.
        </p>
      </div>

      <div className="actions">
        <Button
          disabled={addressProfileQuery.isFetching}
          onClick={() => void addressProfileQuery.refetch()}
          type="button"
          variant="secondary"
        >
          {addressProfileQuery.isFetching
            ? "Refreshing address profile..."
            : "Refresh address profile"}
        </Button>
      </div>

      {addressProfileQuery.isPending ? (
        <div className="auth-success" role="status">
          <strong>Loading address profile...</strong>
          <p>Fetching address profile data from Identity.</p>
        </div>
      ) : null}

      {!addressProfileQuery.isPending && result && !result.ok ? (
        <div className="auth-error" role="alert">
          {result.message}
        </div>
      ) : null}

      {!addressProfileQuery.isPending && addressProfileQuery.isError ? (
        <div className="auth-error" role="alert">
          Address profile request failed before the server returned a response.
        </div>
      ) : null}

      {!addressProfileQuery.isPending && result?.ok ? (
        <div className="health-panel">
          <DetailRow
            label="Address line 1"
            value={addressProfile?.address_line_1}
          />
          <DetailRow
            label="Address line 2"
            value={addressProfile?.address_line_2}
          />
          <DetailRow label="City" value={addressProfile?.city} />
          <DetailRow label="State" value={addressProfile?.state} />
          <DetailRow label="Postal code" value={addressProfile?.postal_code} />
          <DetailRow label="Country" value={addressProfile?.country} />
        </div>
      ) : null}
    </section>
  );
}