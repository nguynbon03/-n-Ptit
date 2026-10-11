import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { api, clearToken, errorText, hasToken, onSessionLost } from "./api";
import type { AuditLog, Doc, Job, LlmSettings, Question, Stats, User, Weekly } from "./api";
import { AuthScreen } from "./auth";
import { Landing } from "./landing";
import { Admin } from "./admin";
import { Learner } from "./learner";

const ADMIN_NAV: [string, string][] = [["admin", "Tổng quan"], ["questions", "Ngân hàng đề"], ["users", "Người dùng"], ["documents", "Tài liệu"], ["jobs", "AI jobs"], ["settings", "Cấu hình LLM"]];
const LEARNER_NAV: [string, string][] = [["dashboard", "Dashboard"], ["questions", "Câu hỏi"], ["progress", "Tiến độ"]];

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [screen, setScreen] = useState<"landing" | "auth">(() => window.location.pathname === "/" ? "landing" : "auth");
  const [authMode, setAuthMode] = useState<"login" | "register">(() => window.location.pathname === "/register" ? "register" : "login");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("dashboard");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [weekly, setWeekly] = useState<Weekly | null>(null);
  const [stats, setStats] = useState<Stats>({});
  const [jobs, setJobs] = useState<Job[]>([]);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [logs, setLogs] = useState<AuditLog[]>([]);

  // There is no refresh endpoint, so a lost session means re-authenticating.
  useEffect(() => onSessionLost(() => {
    if (!hasToken()) {
      setUser(null);
      setNotice("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
    }
  }), []);

  const load = useCallback(async (current: User | null) => {
    if (!current || !hasToken()) return;
    try {
      const [q, w] = await Promise.all([api<{ questions: Question[] }>("/questions?limit=100"), api<Weekly>("/weekly/current")]);
      setQuestions(q.questions || []);
      setWeekly(w);
      if (current.role === "admin") {
        const [s, j, d, u, cfg, a] = await Promise.all([
          api<Stats>("/admin/stats"),
          api<{ jobs: Job[] }>("/admin/generation-jobs"),
          api<{ documents: Doc[] }>("/admin/documents"),
          api<{ users: User[] }>("/admin/users"),
          api<LlmSettings>("/admin/settings/llm"),
          api<{ logs: AuditLog[] }>("/admin/audit-logs?limit=50"),
        ]);
        setStats(s);
        setJobs(j.jobs || []);
        setDocs(d.documents || []);
        setUsers(u.users || []);
        setSettings(cfg);
        setLogs(a.logs || []);
      }
    } catch (e) {
      setNotice(errorText(e, "Không tải được dữ liệu"));
    }
  }, []);

  useEffect(() => { load(user); }, [user, load]);

  const showAuth = (mode: "login" | "register") => {
    setAuthMode(mode);
    setScreen("auth");
    window.history.pushState({}, "", mode === "register" ? "/register" : "/login");
  };

  const onAuthed = (authenticated: User) => {
    setNotice("");
    setUser(authenticated);
    setTab(authenticated.role === "admin" ? "admin" : "dashboard");
  };
  const logout = () => { clearToken(); setUser(null); setNotice(""); };

  if (!user) {
    if (screen === "landing") return <Landing onLogin={() => showAuth("login")} onRegister={() => showAuth("register")} />;
    return <><AuthScreen mode={authMode} onModeChange={showAuth} onAuthed={onAuthed} />{notice && <div className="notice" role="alert">{notice}</div>}</>;
  }

  const nav = user.role === "admin" ? ADMIN_NAV : LEARNER_NAV;
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand"><span className="brandmark">SQL</span><span>sqlarena<small>{user.role === "admin" ? "ADMIN CONSOLE" : "LEARN BY QUERYING"}</small></span></a>
        <nav>{nav.map(([id, label]) => <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}</nav>
        <div className="profile"><strong>{user.email}</strong><small>{user.role}</small><button onClick={logout}>Đăng xuất</button></div>
      </aside>
      <main className="content">
        <header className="pagehead">
          <div><p className="eyebrow">SQLARENA</p><h1>{user.role === "admin" ? "Không gian quản trị." : "Học SQL bằng thử thách."}</h1></div>
          <button className="btn" onClick={() => load(user)}>Làm mới</button>
        </header>
        {notice && <div className="notice" role="status">{notice}</div>}
        {user.role === "admin"
          ? <Admin tab={tab} me={user} stats={stats} questions={questions} docs={docs} jobs={jobs} users={users} settings={settings} logs={logs} reload={() => load(user)} notify={setNotice} />
          : <Learner tab={tab} questions={questions} weekly={weekly} />}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
