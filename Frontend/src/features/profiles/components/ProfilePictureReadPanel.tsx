import { Button } from "../../../shared/ui/Button";
import { useMyProfilePicture } from "../hooks";
import type { ProfilePicture } from "../types";

type FlexibleProfilePicture = ProfilePicture & {
  url?: string | null;
  picture_url?: string | null;
  profile_picture_url?: string | null;
  cloudinary_url?: string | null;
  file_url?: string | null;
  image?: string | null;
};

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

function getPictureUrl(picture: FlexibleProfilePicture | null | undefined) {
  return (
    picture?.secure_url ||
    picture?.image_url ||
    picture?.url ||
    picture?.picture_url ||
    picture?.profile_picture_url ||
    picture?.cloudinary_url ||
    picture?.file_url ||
    picture?.image ||
    ""
  );
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

export function ProfilePictureReadPanel() {
  const pictureQuery = useMyProfilePicture();
  const result = pictureQuery.data;
  const picture = result?.ok
    ? (result.data as FlexibleProfilePicture | null)
    : undefined;
  const pictureUrl = getPictureUrl(picture);

  return (
    <section className="account-settings-panel" aria-label="Profile picture">
      <div className="section-heading">
        <p className="eyebrow">Phase 2.15</p>
        <h2>Profile Picture</h2>
        <p>
          This section reads your profile picture using GET /profiles/me/picture.
        </p>
      </div>

      <div className="actions">
        <Button
          disabled={pictureQuery.isFetching}
          onClick={() => void pictureQuery.refetch()}
          type="button"
          variant="secondary"
        >
          {pictureQuery.isFetching
            ? "Refreshing picture..."
            : "Refresh picture"}
        </Button>
      </div>

      {pictureQuery.isPending ? (
        <div className="auth-success" role="status">
          <strong>Loading profile picture...</strong>
          <p>Fetching profile picture metadata from Identity.</p>
        </div>
      ) : null}

      {!pictureQuery.isPending && result && !result.ok ? (
        <div className="auth-error" role="alert">
          {result.message}
        </div>
      ) : null}

      {!pictureQuery.isPending && pictureQuery.isError ? (
        <div className="auth-error" role="alert">
          Profile picture request failed before the server returned a response.
        </div>
      ) : null}

      {!pictureQuery.isPending && result?.ok ? (
        <div className="health-panel">
          {pictureUrl ? (
            <div className="profile-picture-preview-card">
              <strong>Preview</strong>
              <img
                alt="Current profile"
                className="profile-picture-preview-image"
                src={pictureUrl}
              />
            </div>
          ) : (
            <div className="profile-picture-preview-card">
              <strong>Preview</strong>
              <span>No profile picture added yet</span>
            </div>
          )}

          <DetailRow label="Public ID" value={picture?.public_id} />
          <DetailRow label="Created at" value={picture?.created_at} />
          <DetailRow label="Updated at" value={picture?.updated_at} />
        </div>
      ) : null}
    </section>
  );
}
