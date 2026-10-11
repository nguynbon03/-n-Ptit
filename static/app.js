const $ = (selector) => document.querySelector(selector);
const api = async (path, options = {}) => {
  const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
};

const showNotice = (message) => { const notice = $("#notice"); notice.textContent = message; notice.hidden = false; };
const clearNotice = () => { $("#notice").hidden = true; };
const escapeHtml = (value) => String(value ?? "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]));

async function loadHealth() {
  try {
    const health = await api("/health");
    $("#health-badge").textContent = "API online"; $("#health-badge").dataset.state = "ok";
    $("#health-copy").textContent = `API online · v${health.version}`;
  } catch (error) { $("#health-badge").textContent = "API offline"; $("#health-badge").dataset.state = "error"; $("#health-copy").textContent = error.message; }
}

async function loadStats() {
  try {
    const stats = await api("/stats");
    $("#metric-total").textContent = stats.total ?? 0;
    $("#metric-valid").textContent = `${Math.round((stats.valid_rate || 0) * 100)}%`;
    $("#metric-pending").textContent = stats.by_status?.pending_review ?? 0;
    $("#metric-approved").textContent = stats.by_status?.approved ?? 0;
  } catch (error) { showNotice(error.message); }
}

function questionRow(question) {
  const title = question.question_text || "Untitled question";
  const difficulty = question.difficulty || "unknown";
  const status = question.status || "pending_review";
  return `<article class="question-row"><div><h3>${escapeHtml(title)}</h3><div class="question-meta"><span class="tag">${escapeHtml(difficulty)}</span><span class="tag status-${escapeHtml(status)}">${escapeHtml(status.replace("_", " "))}</span><span>${escapeHtml(question.topic || "General SQL")}</span></div></div><div class="question-actions"><button class="button button-small" type="button" data-question-id="${escapeHtml(question.id)}">Inspect</button></div></article>`;
}

async function loadQuestions() {
  const params = new URLSearchParams(); const difficulty = $("#difficulty-filter").value; const status = $("#status-filter").value;
  if (difficulty) params.set("difficulty", difficulty); if (status) params.set("status", status);
  try {
    const data = await api(`/questions?${params}`); const list = $("#questions-list");
    list.innerHTML = data.questions?.length ? data.questions.map(questionRow).join("") : '<div class="empty-state">No questions match current filters.</div>';
    list.querySelectorAll("[data-question-id]").forEach((button) => button.addEventListener("click", () => loadQuestion(button.dataset.questionId)));
  } catch (error) { $("#questions-list").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`; }
}

async function loadQuestion(id) {
  try {
    const question = await api(`/questions/${encodeURIComponent(id)}`); const detail = $("#question-detail");
    detail.dataset.triggerId = id;
    $("#detail-content").innerHTML = `<div class="detail-grid"><div class="detail-block"><h3>Prompt</h3><p>${escapeHtml(question.question_text)}</p><p class="question-meta">${escapeHtml(question.difficulty)} · ${escapeHtml(question.topic)} · valid: ${question.valid ? "yes" : "no"}</p></div><div class="detail-block"><h3>Review status</h3><form class="status-form" id="status-form"><select id="detail-status" aria-label="Question status"><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="archived">Archived</option></select><button class="button button-small" type="submit">Save</button></form></div><div class="detail-block"><h3>Schema</h3><pre class="code">${escapeHtml(question.schema_sql)}</pre></div><div class="detail-block"><h3>Answer SQL</h3><pre class="code">${escapeHtml(question.answer_sql)}</pre></div></div>`;
    detail.hidden = false; detail.tabIndex = -1; detail.scrollIntoView({ behavior: "smooth", block: "start" }); detail.focus({ preventScroll: true });
    $("#detail-status").value = ["approved", "rejected", "archived"].includes(question.status) ? question.status : "approved";
    $("#status-form").addEventListener("submit", async (event) => { event.preventDefault(); try { await api(`/questions/${encodeURIComponent(id)}/status`, { method: "PUT", body: JSON.stringify({ status: $("#detail-status").value, review_notes: "Updated in SQLArena workspace" }) }); showNotice("Question status updated."); await Promise.all([loadQuestions(), loadStats()]); } catch (error) { showNotice(error.message); } });
  } catch (error) { showNotice(error.message); }
}

async function pollTask(taskId) {
  const panel = $("#task-panel"); panel.hidden = false;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const task = await api(`/tasks/${encodeURIComponent(taskId)}`); const state = task.status || "queued";
      const percent = state === "done" || state === "failed" ? 100 : state === "running" ? 58 : 20;
      $("#task-state").textContent = state; $("#task-message").textContent = task.error || (state === "done" ? "Generation complete." : "Pipeline is working…");
      $("#task-progress").style.width = `${percent}%`; $("#task-progress").setAttribute("aria-valuenow", percent);
      if (state === "done") { await Promise.all([loadQuestions(), loadStats()]); return; } if (state === "failed") { showNotice(task.error || "Generation failed."); return; }
      await new Promise((resolve) => setTimeout(resolve, 1200));
    } catch (error) { showNotice(`${error.message} Try refreshing task status.`); return; }
  }
  showNotice("Generation status timed out. Refresh and retry if needed.");
}

$("#generate-form").addEventListener("submit", async (event) => {
  event.preventDefault(); clearNotice(); const specs = [...document.querySelectorAll('input[name="spec"]:checked')].map((input) => input.value); if (!specs.length) return showNotice("Choose at least one difficulty track.");
  try { const data = await api("/generate", { method: "POST", body: JSON.stringify({ specs, questions_per_spec: Number($("#questions-per-spec").value), excel_id: $("#excel-id").value || null }) }); if (data.task_id) pollTask(data.task_id); else { showNotice("Generation complete."); await Promise.all([loadQuestions(), loadStats()]); } } catch (error) { showNotice(error.message); }
});

$("#verify-form").addEventListener("submit", async (event) => {
  event.preventDefault(); clearNotice(); const box = $("#verify-result"); box.textContent = "Running sandbox…";
  try { const result = await api("/verify-sql", { method: "POST", body: JSON.stringify({ ddl_sql: $("#ddl-sql").value, seed_sql: $("#seed-sql").value, answer_sql: $("#answer-sql").value }) }); box.dataset.valid = String(result.valid); box.innerHTML = `<strong>${result.valid ? "Valid SQL" : "SQL rejected"}</strong> · ${escapeHtml(result.error || `${result.row_count} row(s), ${result.duration_ms} ms`)}${result.output?.length ? `\n\n${escapeHtml(JSON.stringify(result.output, null, 2))}` : ""}`; } catch (error) { box.textContent = error.message; box.dataset.valid = "false"; }
});

["#difficulty-filter", "#status-filter"].forEach((selector) => $(selector).addEventListener("change", loadQuestions));
$("#refresh-questions").addEventListener("click", () => Promise.all([loadQuestions(), loadStats()])); $("#close-detail").addEventListener("click", () => { const detail = $("#question-detail"); detail.hidden = true; document.querySelector(`[data-question-id="${CSS.escape(detail.dataset.triggerId || "")}"]`)?.focus(); });
loadHealth(); loadStats(); loadQuestions();
