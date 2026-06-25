function StoriesPage() {
  const stories = ["Today", "Design", "Launch notes"]

  return (
    <section className="sidebar-view active" aria-label="Stories tab">
      <div className="sidebar-view-heading">
        <div>
          <span className="section-kicker">Stories</span>
          <h2>Stories</h2>
        </div>
      </div>

      <div className="sidebar-list">
        {stories.map((story) => (
          <button className="story-item" key={story} type="button">
            <span className="list-avatar">{story[0]}</span>
            <span className="list-content">
              <span className="list-top-row">
                <strong>{story}</strong>
                <small>New</small>
              </span>
              <span className="list-bottom-row">
                <span>Story preview area</span>
              </span>
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}

export default StoriesPage
