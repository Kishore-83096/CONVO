import convoLogo from "@/assets/convo/CONVO.png"

function EmptyPage() {
  return (
    <section className="main-view active">
      <div className="empty-main-content">
        <img className="empty-main-icon" src={convoLogo} alt="CONVO logo" />
        <h2>CONVO</h2>
        <p>Select a chat, profile, or settings page.</p>
      </div>
    </section>
  )
}

export default EmptyPage
