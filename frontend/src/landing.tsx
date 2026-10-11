type LandingProps = { onLogin: () => void; onRegister: () => void };

export function Landing({ onLogin, onRegister }: LandingProps) {
  return (
    <main className="landing">
      <nav className="landing-nav" aria-label="Điều hướng chính">
        <a className="brand" href="/" onClick={(event) => event.preventDefault()}>
          <span className="brandmark">SQL</span>
          <span>sqlarena<small>LEARN BY QUERYING</small></span>
        </a>
        <div className="landing-actions">
          <button className="btn" onClick={onLogin}>Đăng nhập</button>
          <button className="btn primary" onClick={onRegister}>Bắt đầu học →</button>
        </div>
      </nav>

      <section className="landing-hero">
        <div className="landing-copy">
          <p className="eyebrow">LUYỆN SQL CÓ CHỦ ĐÍCH</p>
          <h1>Học bằng cách <em>đặt câu hỏi.</em></h1>
          <p className="landing-lead">Luyện SQL qua thử thách được sinh, kiểm tra và duyệt trước khi đến tay người học.</p>
          <div className="landing-cta">
            <button className="btn primary" onClick={onRegister}>Tạo tài khoản miễn phí →</button>
            <button className="text-button" onClick={onLogin}>Tôi đã có tài khoản</button>
          </div>
        </div>
        <div className="landing-card" aria-label="Tổng quan hành trình học">
          <div className="landing-card-top"><span>SQLARENA / 2026</span><strong>01</strong></div>
          <p className="tag">THỬ THÁCH TUẦN</p>
          <h2>Query trước.<br /><em>Hiểu sau.</em></h2>
          <div className="landing-query">SELECT skill, progress<br />FROM learners<br />ORDER BY progress DESC;</div>
          <div className="landing-metrics"><span><b>8</b> câu mỗi tuần</span><span><b>100%</b> tập trung</span></div>
        </div>
      </section>

      <section className="landing-points" aria-label="Điểm nổi bật">
        <article><strong>01</strong><h2>Đề rõ ràng</h2><p>Mỗi câu hỏi có mục tiêu, độ khó và chủ đề cụ thể.</p></article>
        <article><strong>02</strong><h2>Kiểm tra thật</h2><p>Đáp án được chạy trong sandbox trước khi duyệt.</p></article>
        <article><strong>03</strong><h2>Tiến bộ đều</h2><p>Thử thách tuần giúp bạn duy trì nhịp học.</p></article>
      </section>
    </main>
  );
}
