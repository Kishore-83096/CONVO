import type { CompleteProfile } from "@/app/workspace/profile/profile.types"

interface ProfilePageProps {
  profile: CompleteProfile
}

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
}

function ProfilePage({ profile }: ProfilePageProps) {
  const { identity, basic_data: basicData, address } = profile

  return (
    <section className="workspace-panel active">
      <div className="flat-profile-hero">
        {profile.profile_picture ? (
          <img
            className="profile-page-avatar"
            src={profile.profile_picture.url}
            alt=""
          />
        ) : (
          <span className="profile-page-avatar">{initials(identity.full_name)}</span>
        )}
        <div>
          <h3>{identity.full_name}</h3>
          <p>@{identity.username}</p>
        </div>
      </div>

      <dl className="profile-detail-grid">
        <div>
          <dt>Full name</dt>
          <dd>{identity.full_name}</dd>
        </div>
        <div>
          <dt>Username</dt>
          <dd>@{identity.username}</dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>{identity.email}</dd>
        </div>
        <div>
          <dt>Contact number</dt>
          <dd>{identity.contact_number}</dd>
        </div>
        <div>
          <dt>Bio</dt>
          <dd>{basicData?.bio || "No bio added."}</dd>
        </div>
        <div>
          <dt>Gender</dt>
          <dd>{basicData?.gender || "Not set"}</dd>
        </div>
        <div>
          <dt>Occupation</dt>
          <dd>{basicData?.occupation || "Not set"}</dd>
        </div>
        <div>
          <dt>Website</dt>
          <dd>{basicData?.website || "Not set"}</dd>
        </div>
        <div>
          <dt>Date of birth</dt>
          <dd>{basicData?.date_of_birth || "Not set"}</dd>
        </div>
        <div>
          <dt>City</dt>
          <dd>
            {address
              ? [address.city, address.state, address.country]
                  .filter(Boolean)
                  .join(", ")
              : "Not set"}
          </dd>
        </div>
        <div>
          <dt>Events</dt>
          <dd>{profile.events.length}</dd>
        </div>
      </dl>
    </section>
  )
}

export default ProfilePage
