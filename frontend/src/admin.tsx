import { useState } from "react";
import type { FormEvent } from "react";
import { api, errorText } from "./api";
import type { AuditLog, Doc, Job, LlmSettings, Question, Stats, User } from "./api";

type AdminProps = {
  tab: string;
  me: User;
  stats: Stats;
  questions: Question[];
  docs: Doc[];
  jobs: Job[];
  users: User[];
  settings: LlmSettings | null;
  logs: AuditLog[];
  reload: () => void;
  notify: (message: string) => void;
};

const useAction = (reload: () => void, notify: (m: string) => void) => {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const run = async (key: string, fn: () => Promise<string>) => {
    setBusy(key);
    setError("");
    try {
      notify(await fn());
      reload();
    } catch (e) {
      setError(errorText(e, "Tác vụ thất bại"));
    } finally {
      setBusy("");
    }
  };
  return { busy, error, run };
};

export function Admin({ tab, me, stats, questions, docs, jobs, users, settings, logs, reload, notify }: AdminProps) {
  const { busy, error, run } = useAction(reload, notify);
  const [jobDetail, setJobDetail] = useState<Job | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const review = (q: Question, status: string) =>
    run(`review-${q.id}-${status}`, async () => {
      await api(`/questions/${q.id}/status`, { method: "PUT", body: JSON.stringify({ status, review_notes: notes[q.id] || "" }) });
      return `Đã cập nhật câu hỏi ${q.id} → ${status}`;
    });

  const upload = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const body = new FormData(form);
    run("upload", async () => {
      const doc = await api<Doc>("/admin/documents", { method: "POST", body });
      form.reset();
      return `Đã nạp ${doc.filename} (checksum ${(doc.checksum || "").slice(0, 12)}…)`;
    });
  };

  const generate = () =>
    run("generate", async () => {
      const r = await api<{ task_id: string }>("/admin/generation-jobs", { method: "POST", body: JSON.stringify({ specs: ["easy", "medium", "hard"], questions_per_spec: 1 }) });
      return `Đã tạo job ${r.task_id} (không bền vững, chạy trong tiến trình API)`;
    });

  const openJob = (id: string) =>
    run(`job-${id}`, async () => {
      setJobDetail(await api<Job>(`/admin/generation-jobs/${id}`));
      return `Đã tải chi tiết job ${id}`;
    });

  const changeUser = (user: User, patch: Partial<Pick<User, "role" | "status">>) =>
    run(`user-${user.id}`, async () => {
      await api(`/admin/users/${user.id}`, { method: "PATCH", body: JSON.stringify(patch) });
      return `Đã cập nhật ${user.email}`;
    });

  const saveSettings = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const token = String(form.get("api_token") ?? "");
    run("settings", async () => {
      const payload: Record<string, string> = { provider: String(form.get("provider")), model: String(form.get("model") || ""), base_url: String(form.get("base_url") || "") };
      // Only send the secret when the admin typed one; blank keeps the stored value.
      if (token) payload.api_token = token;
      await api("/admin/settings/llm", { method: "PUT", body: JSON.stringify(payload) });
      return "Đã lưu cấu hình LLM (token không bao giờ được trả về)";
    });
  };

  const clearToken = () =>
    run("settings-clear", async () => {
      await api("/admin/settings/llm", { method: "PUT", body: JSON.stringify({ provider: settings?.provider || "anthropic", api_token: "" }) });
      return "Đã xoá token khỏi cấu hình";
    });

  const testProvider = () =>
    run("llm-test", async () => {
      const r = await api<{ provider: string; model: string; sample: string }>("/admin/llm/test", { method: "POST" });
      return `Provider OK: ${r.provider} / ${r.model}`;
    });

  return (
    <>
      {error && <div className="notice" role="alert">{error}</div>}

      {tab === "admin" && (
        <>
          <div className="stats">
            {([["Người dùng", stats.users], ["Đang hoạt động", stats.active_users], ["Câu hỏi", stats.questions], ["Đã duyệt", stats.approved_questions], ["Chờ duyệt", stats.pending_questions], ["Tài liệu", stats.documents], ["Jobs", stats.jobs]] as [string, number | undefined][]).map(([label, value]) => (
              <div className="stat" key={label}><span>{label}</span><strong>{value ?? 0}</strong></div>
            ))}
          </div>
          <div className="card">
            <h2>Audit gần đây</h2>
            {logs.length ? logs.slice(0, 15).map((log) => (
              <p key={log.id}><code>{log.action}</code> · {log.resource_type}/{log.resource_id} · {log.summary} <small>{log.created_at}</small></p>
            )) : <p>Chưa có bản ghi audit.</p>}
          </div>
        </>
      )}

      {tab === "questions" && (
        <div className="grid">
          {questions.map((q) => (
            <article className="question" key={q.id}>
              <p className="tag">{q.difficulty || "medium"} · {q.topic || "SQL"}</p>
              <h3>{q.question_text}</h3>
              <small>{q.status}{q.review_notes ? ` · ${q.review_notes}` : ""}</small>
              <label>Ghi chú duyệt
                <input value={notes[q.id] || ""} onChange={(e) => setNotes({ ...notes, [q.id]: e.target.value })} placeholder="Lý do duyệt / từ chối" />
              </label>
              <div>
                <button disabled={busy.startsWith(`review-${q.id}`)} onClick={() => review(q, "approved")}>Duyệt</button>
                <button disabled={busy.startsWith(`review-${q.id}`)} onClick={() => review(q, "rejected")}>Từ chối</button>
                <button disabled={busy.startsWith(`review-${q.id}`)} onClick={() => review(q, "archived")}>Lưu trữ</button>
              </div>
            </article>
          ))}
          {!questions.length && <div className="card"><p>Chưa có câu hỏi.</p></div>}
        </div>
      )}

      {tab === "users" && (
        <div className="card">
          <h2>Người dùng</h2>
          <table>
            <thead><tr><th>Email</th><th>Vai trò</th><th>Trạng thái</th><th>Hành động</th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}{u.id === me.id ? " (bạn)" : ""}</td>
                  <td>{u.role}</td>
                  <td>{u.status}</td>
                  <td>
                    <button disabled={busy === `user-${u.id}` || u.id === me.id} onClick={() => changeUser(u, { role: u.role === "admin" ? "learner" : "admin" })}>
                      {u.role === "admin" ? "Hạ quyền" : "Cấp admin"}
                    </button>
                    <button disabled={busy === `user-${u.id}` || u.id === me.id} onClick={() => changeUser(u, { status: u.status === "locked" ? "active" : "locked" })}>
                      {u.status === "locked" ? "Mở khoá" : "Khoá"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint">Không thể tự khoá hoặc tự hạ quyền chính mình.</p>
        </div>
      )}

      {tab === "documents" && (
        <div className="card">
          <h2>Nạp tài liệu</h2>
          <form onSubmit={upload}>
            <input name="file" type="file" accept=".csv,.xlsx,.json,.md,.txt,.pdf" required />
            <button className="btn primary" disabled={busy === "upload"}>{busy === "upload" ? "Đang nạp…" : "Upload vào Mongo"}</button>
          </form>
          <p className="hint">Hỗ trợ .csv .xlsx .json .md .txt .pdf. Trùng checksum sẽ bị từ chối.</p>
          <table>
            <thead><tr><th>Tên</th><th>Kích thước</th><th>Checksum</th><th>Trạng thái</th></tr></thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td>{d.filename}</td>
                  <td>{d.size} bytes{d.truncated ? " (text đã cắt)" : ""}</td>
                  <td><code>{(d.checksum || "").slice(0, 12)}…</code></td>
                  <td>{d.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "jobs" && (
        <div className="card">
          <h2>AI generation jobs</h2>
          <button className="btn primary" disabled={busy === "generate"} onClick={generate}>{busy === "generate" ? "Đang tạo…" : "Sinh 3 đề AI"}</button>
          <p className="hint">Job chạy bằng FastAPI BackgroundTasks trong tiến trình API: không bền vững, mất khi restart. Trạng thái lấy từ Mongo.</p>
          <table>
            <thead><tr><th>Job</th><th>Trạng thái</th><th>Lỗi</th><th>Chi tiết</th></tr></thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td><code>{j.id.slice(0, 8)}…</code></td>
                  <td>{j.status}{j.durable === false ? " (non-durable)" : ""}</td>
                  <td>{j.error_code || "-"}</td>
                  <td><button disabled={busy === `job-${j.id}`} onClick={() => openJob(j.id)}>Xem</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {jobDetail && (
            <div className="card">
              <h3>Job {jobDetail.id}</h3>
              <p>Trạng thái: {jobDetail.status} · executor: {jobDetail.executor || "-"} · durable: {String(jobDetail.durable ?? false)}</p>
              <p>Specs: {(jobDetail.specs || []).join(", ") || "-"}</p>
              <p>Câu hỏi đã lưu: {(jobDetail.persisted_question_ids || []).length}</p>
              {jobDetail.error && <p>Lỗi ({jobDetail.error_code}): {jobDetail.error}</p>}
              <button onClick={() => setJobDetail(null)}>Đóng</button>
            </div>
          )}
        </div>
      )}

      {tab === "settings" && (
        <div className="card">
          <h2>Cấu hình LLM</h2>
          {settings ? (
            <>
              <p>
                Provider hiện tại: <strong>{settings.provider}</strong> · model: {settings.model || "(mặc định)"} · token:{" "}
                {settings.token_configured ? `đã cấu hình (${settings.token_source}) ${settings.token_hint}` : "chưa cấu hình"}
              </p>
              <form onSubmit={saveSettings}>
                <label>Provider
                  <select name="provider" defaultValue={settings.provider}>
                    {settings.supported_providers.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </label>
                <label>Model<input name="model" defaultValue={settings.model} placeholder="claude-sonnet-4-6" /></label>
                <label>Base URL<input name="base_url" defaultValue={settings.base_url} placeholder="https://api.anthropic.com/v1/messages" /></label>
                <label>API token<input name="api_token" type="password" autoComplete="off" placeholder="Để trống để giữ token hiện tại" /></label>
                <button className="btn primary" disabled={busy === "settings"}>{busy === "settings" ? "Đang lưu…" : "Lưu cấu hình"}</button>
              </form>
              <div>
                <button disabled={busy === "llm-test"} onClick={testProvider}>{busy === "llm-test" ? "Đang kiểm tra…" : "Kiểm tra provider"}</button>
                <button disabled={busy === "settings-clear" || !settings.token_configured} onClick={clearToken}>Xoá token</button>
              </div>
              <p className="hint">Token chỉ lưu phía server và không bao giờ được trả về giao diện.</p>
            </>
          ) : <p>Đang tải cấu hình…</p>}
        </div>
      )}
    </>
  );
}
