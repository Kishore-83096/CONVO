import { Button } from "../../../shared/ui/Button";
import { useMyProfileBasic } from "../hooks";

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

export function BasicProfileReadPanel() {
  const basicProfileQuery = useMyProfileBasic();
  const result = basicProfileQuery.data;
  const basicProfile = result?.ok ? result.data : undefined;

  return (
    <section className="account-settings-panel" aria-label="Basic profile">
      <div className="section-heading">
        <p className="eyebrow">Phase 2.2</p>
        <h2>Basic Profile</h2>
        <p>
          This section directly reads your basic profile using GET
          /profiles/me/basic. Create, update, and delete are intentionally not
          added in this phase.
        </p>
      </div>

      <div className="actions">
        <Button
          disabled={basicProfileQuery.isFetching}
          onClick={() => void basicProfileQuery.refetch()}
          type="button"
          variant="secondary"
        >
          {basicProfileQuery.isFetching
            ? "Refreshing basic profile..."
            : "Refresh basic profile"}
        </Button>
      </div>

      {basicProfileQuery.isPending ? (
        <div className="auth-success" role="status">
          <strong>Loading basic profile...</strong>
          <p>Fetching basic profile data from Identity.</p>
        </div>
      ) : null}

      {!basicProfileQuery.isPending && result && !result.ok ? (
        <div className="auth-error" role="alert">
          {result.message}
        </div>
      ) : null}

      {!basicProfileQuery.isPending && basicProfileQuery.isError ? (
        <div className="auth-error" role="alert">
          Basic profile request failed before the server returned a response.
        </div>
      ) : null}

      {!basicProfileQuery.isPending && result?.ok ? (
        <div className="health-panel">
          <DetailRow label="Bio" value={basicProfile?.bio} />
          <DetailRow
            label="Date of birth"
            value={basicProfile?.date_of_birth}
          />
          <DetailRow label="Gender" value={basicProfile?.gender} />
          <DetailRow label="Occupation" value={basicProfile?.occupation} />
          <DetailRow label="Website" value={basicProfile?.website} />
        </div>
      ) : null}
    </section>
  );
}