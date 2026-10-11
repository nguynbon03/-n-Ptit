import { useState } from "react";
import type { FormEvent } from "react";
import { api, errorText, setToken } from "./api";
import type { User } from "./api";

export function AuthScreen({ mode, onModeChange, onAuthed }: { mode: "login" | "register"; onModeChange: (mode: "login" | "register") => void; onAuthed: (user: User) => void }) {
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice("");
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      const data = await api<{ access_token: string; user: User }>(`/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      setToken(data.access_token);
      onAuthed(data.user);
    } catch (e) {
      setNotice(errorText(e, mode === "login" ? "Đăng nhập thất bại" : "Tạo tài khoản thất bại"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <section className="auth-art">
        <a className="brand"><span className="brandmark">SQL</span><span>sqlarena<small>Learn by querying</small></span></a>
        <h1>Học bằng cách <em>đặt câu hỏi.</em></h1>
        <p>Luyện SQL qua đề được sinh, duyệt và lưu trên MongoDB.</p>
        <pre>SELECT skill, progress FROM learners ORDER BY progress DESC;</pre>
      </section>
      <section className="auth-form">
        <p className="eyebrow">{mode === "login" ? "Chào mừng trở lại" : "Bắt đầu hành trình"}</p>
        <h2>{mode === "login" ? "Đăng nhập." : "Tạo tài khoản."}</h2>
        <div className="switch">
          <button type="button" className={mode === "login" ? "active" : ""} onClick={() => onModeChange("login")}>Đăng nhập</button>
          <button type="button" className={mode === "register" ? "active" : ""} onClick={() => onModeChange("register")}>Tạo tài khoản</button>
        </div>
        {notice && <div className="notice" role="alert">{notice}</div>}
        <form onSubmit={submit}>
          <label>Email<input name="email" type="email" autoComplete="email" required /></label>
          <label>Mật khẩu<input name="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 10 : 1} required /></label>
          <button className="btn primary" disabled={busy}>{busy ? "Đang xử lý…" : mode === "login" ? "Đăng nhập →" : "Tạo tài khoản →"}</button>
        </form>
        <p className="hint">Phiên đăng nhập chỉ nằm trong bộ nhớ trang. Tải lại trang sẽ cần đăng nhập lại.</p>
      </section>
    </div>
  );
}
