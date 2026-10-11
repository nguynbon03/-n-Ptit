import { StrictMode, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type User = { id: string; email: string; role: "learner" | "admin"; status: string };
type Question = { id: string; question_text?: string; difficulty?: string; topic?: string; status?: string; answer_sql?: string; schema_sql?: string };
type Stats = { users?: number; questions?: number; approved_questions?: number; pending_questions?: number; documents?: number; jobs?: number };
type Weekly = { challenge: { title?: string; number?: number; status?: string }; progress: { done: number; total: number; percent: number }; questions: Question[] };

const savedToken = localStorage.getItem("sqlarena_token") || "";
const api = async <T,>(path: string, token: string, options: RequestInit = {}): Promise<T> => {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`/api${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
};

function App() {
  const [token, setToken] = useState(savedToken);
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("dashboard");
  const [stats, setStats] = useState<Stats>({});
  const [questions, setQuestions] = useState<Question[]>([]);
  const [weekly, setWeekly] = useState<Weekly | null>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [docs, setDocs] = useState<any[]>([]);

  const authed = async (nextToken = token) => {
    if (!nextToken) return;
    try {
      const me = await api<User>("/me", nextToken);
      setUser(me);
      if (me.role === "admin") setTab("admin");
    } catch {
      localStorage.removeItem("sqlarena_token");
      setToken("");
    }
  };
  useEffect(() => { authed(); }, []);

  const load = async () => {
    if (!token || !user) return;
    try {
      const [q, w] = await Promise.all([api<{ questions: Question[] }>("/questions?limit=100", token), api<Weekly>("/weekly/current", token)]);
      setQuestions(q.questions || []); setWeekly(w);
      if (user.role === "admin") {
        const [s, j, d] = await Promise.all([api<Stats>("/admin/stats", token), api<{ jobs: any[] }>("/admin/generation-jobs", token), api<{ documents: any[] }>("/admin/documents", token)]);
        setStats(s); setJobs(j.jobs || []); setDocs(d.documents || []);
      }
    } catch (e) { setNotice(e instanceof Error ? e.message : "Không tải được dữ liệu"); }
  };
  useEffect(() => { load(); }, [token, user?.role]);

  const submitAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setNotice("");
    const form = new FormData(event.currentTarget);
    try {
      const data = await api<{ access_token: string; user: User }>(`/auth/${mode}`, "", { method: "POST", body: JSON.stringify({ email: form.get("email"), password: form.get("password") }) });
      localStorage.setItem("sqlarena_token", data.access_token); setToken(data.access_token); setUser(data.user); setTab(data.user.role === "admin" ? "admin" : "dashboard");
    } catch (e) { setNotice(e instanceof Error ? e.message : "Đăng nhập thất bại"); }
  };
  const logout = () => { localStorage.removeItem("sqlarena_token"); setToken(""); setUser(null); };
  const uploadDoc = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const body = new FormData(event.currentTarget); await api("/admin/documents", token, { method: "POST", body }); setNotice("Đã nạp tài liệu vào Mongo."); load(); };
  const generate = async () => { const r = await api<{ task_id: string }>("/admin/generation-jobs", token, { method: "POST", body: JSON.stringify({ specs: ["easy", "medium", "hard"], questions_per_spec: 1 }) }); setNotice(`Đã tạo job ${r.task_id}`); load(); };
  const approve = async (q: Question, status: string) => { await api(`/questions/${q.id}/status`, token, { method: "PUT", body: JSON.stringify({ status, review_notes: "Updated by admin UI" }) }); load(); };

  if (!user) return <AuthScreen mode={mode} setMode={setMode} submitAuth={submitAuth} notice={notice} />;
  const nav = user.role === "admin" ? [["admin", "Tổng quan"], ["questions", "Ngân hàng đề"], ["documents", "Tài liệu"], ["jobs", "AI jobs"]] : [["dashboard", "Dashboard"], ["questions", "Câu hỏi"], ["progress", "Tiến độ"]];
  return <div className="app"><aside className="sidebar"><a className="brand"><span className="brandmark">SQL</span><span>sqlarena<small>{user.role === "admin" ? "ADMIN CONSOLE" : "LEARN BY QUERYING"}</small></span></a><nav>{nav.map(([id, label]) => <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}</nav><div className="profile"><strong>{user.email}</strong><small>{user.role}</small><button onClick={logout}>Đăng xuất</button></div></aside><main className="content"><header className="pagehead"><div><p className="eyebrow">SQLARENA</p><h1>{user.role === "admin" ? "Không gian quản trị." : "Học SQL bằng thử thách."}</h1></div><button className="btn" onClick={load}>Làm mới</button></header>{notice && <div className="notice">{notice}</div>}{user.role === "admin" ? <Admin tab={tab} stats={stats} questions={questions} docs={docs} jobs={jobs} uploadDoc={uploadDoc} generate={generate} approve={approve} /> : <Learner tab={tab} questions={questions} weekly={weekly} />}</main></div>;
}

function AuthScreen({ mode, setMode, submitAuth, notice }: any) { return <div className="auth"><section className="auth-art"><a className="brand"><span className="brandmark">SQL</span><span>sqlarena<small>Learn by querying</small></span></a><h1>Học bằng cách <em>đặt câu hỏi.</em></h1><p>Luyện SQL qua đề được sinh, duyệt và lưu trên MongoDB.</p><pre>SELECT skill, progress FROM learners ORDER BY progress DESC;</pre></section><section className="auth-form"><p className="eyebrow">{mode === "login" ? "Chào mừng trở lại" : "Bắt đầu hành trình"}</p><h2>{mode === "login" ? "Đăng nhập." : "Tạo tài khoản."}</h2><div className="switch"><button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Đăng nhập</button><button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Tạo tài khoản</button></div>{notice && <div className="notice">{notice}</div>}<form onSubmit={submitAuth}><label>Email<input name="email" type="email" required /></label><label>Mật khẩu<input name="password" type="password" minLength={mode === "register" ? 10 : 1} required /></label><button className="btn primary">{mode === "login" ? "Đăng nhập" : "Tạo tài khoản"} →</button></form></section></div> }
function Learner({ tab, questions, weekly }: any) { const progress = weekly?.progress || { done: 0, total: 8, percent: 0 }; return <>{tab === "dashboard" && <><div className="weekly"><div><h2>{weekly?.challenge?.title || "Thử thách tuần #42"}</h2><p>Hoàn thành các bài trong tuần để ghi tên lên bảng xếp hạng cộng đồng.</p><div className="bar"><span style={{ width: `${progress.percent}%` }} /></div><strong>{progress.done}/{progress.total} câu hoàn thành <b>{progress.percent}%</b></strong><a>Xem bảng xếp hạng tuần →</a></div><span>ĐANG DIỄN RA</span></div><QuestionGrid questions={questions} /></>}{tab === "questions" && <QuestionGrid questions={questions} />}{tab === "progress" && <div className="card"><h2>Tiến độ</h2><p>{progress.done}/{progress.total} câu hoàn thành.</p></div>}</> }
function Admin({ tab, stats, questions, docs, jobs, uploadDoc, generate, approve }: any) { return <>{tab === "admin" && <div className="stats">{[["Người dùng", stats.users], ["Câu hỏi", stats.questions], ["Đã duyệt", stats.approved_questions], ["Tài liệu", stats.documents]].map(x => <div className="stat" key={x[0]}><span>{x[0]}</span><strong>{x[1] ?? 0}</strong></div>)}</div>}{tab === "questions" && <QuestionGrid questions={questions} admin approve={approve} />}{tab === "documents" && <div className="card"><h2>Nạp tài liệu</h2><form onSubmit={uploadDoc}><input name="file" type="file" required /><button className="btn primary">Upload vào Mongo</button></form>{docs.map((d: any) => <p key={d.id}>{d.filename} · {d.size} bytes</p>)}</div>}{tab === "jobs" && <div className="card"><button className="btn primary" onClick={generate}>Sinh 3 đề AI</button>{jobs.map((j: any) => <p key={j.id}>{j.id} · {j.status}</p>)}</div>}</> }
function QuestionGrid({ questions, admin, approve }: any) { return <div className="grid">{questions.map((q: Question) => <article className="question" key={q.id}><p className="tag">{q.difficulty || "medium"} · {q.topic || "SQL"}</p><h3>{q.question_text}</h3><small>{q.status}</small>{admin && <div><button onClick={() => approve(q, "approved")}>Duyệt</button><button onClick={() => approve(q, "rejected")}>Từ chối</button></div>}</article>)}</div> }

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
