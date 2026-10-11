import type { Question, Weekly } from "./api";

export function QuestionGrid({ questions, empty = "Chưa có câu hỏi." }: { questions: Question[]; empty?: string }) {
  if (!questions.length) return <div className="card"><p>{empty}</p></div>;
  return (
    <div className="grid">
      {questions.map((q) => (
        <article className="question" key={q.id}>
          <p className="tag">{q.difficulty || "medium"} · {q.topic || "SQL"}</p>
          <h3>{q.question_text}</h3>
          <small>{q.status}</small>
        </article>
      ))}
    </div>
  );
}

export function Learner({ tab, questions, weekly }: { tab: string; questions: Question[]; weekly: Weekly | null }) {
  const progress = weekly?.progress || { done: 0, total: 8, percent: 0 };
  return (
    <>
      {tab === "dashboard" && (
        <>
          <div className="weekly">
            <div>
              <h2>{weekly?.challenge?.title || "Thử thách tuần"}</h2>
              <p>Hoàn thành các bài trong tuần để ghi tên lên bảng xếp hạng cộng đồng.</p>
              <div className="bar"><span style={{ width: `${progress.percent}%` }} /></div>
              <strong>{progress.done}/{progress.total} câu hoàn thành <b>{progress.percent}%</b></strong>
            </div>
            <span>ĐANG DIỄN RA</span>
          </div>
          <QuestionGrid questions={weekly?.questions?.length ? weekly.questions : questions} />
        </>
      )}
      {tab === "questions" && <QuestionGrid questions={questions} empty="Chưa có câu hỏi nào được duyệt." />}
      {tab === "progress" && (
        <div className="card">
          <h2>Tiến độ</h2>
          <p>{progress.done}/{progress.total} câu hoàn thành ({progress.percent}%).</p>
          <p className="hint">Lưu bài làm và bảng xếp hạng chưa có trong bản prototype này.</p>
        </div>
      )}
    </>
  );
}
