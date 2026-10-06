"use strict";
let token = "", selected = null, activeTab = "evidence", connected = false;
let refreshing = false, tasks = [], lastRender = "";
const $ = id => document.getElementById(id);
const label = value => value.replaceAll("_", " ");
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function message(text = "") { $("message").textContent = text; }
async function request(path, method = "GET", body) {
  const response = await fetch(path, {method, headers: {"Authorization": "Bearer " + token,
    "Content-Type": "application/json"}, body: body === undefined ? undefined : JSON.stringify(body)});
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : "Request failed: " + response.status);
  }
  return response.headers.get("content-type")?.includes("application/json") ? response.json() : response.text();
}
async function refresh() {
  if (!connected || refreshing) return;
  refreshing = true;
  try {
    const runs = await request("/runs");
    $("total").textContent = runs.length;
    $("active").textContent = runs.filter(r => ["pending", "running"].includes(r.status)).length;
    $("ready").textContent = runs.filter(r => r.status === "ready_for_approval").length;
    $("attention").textContent = runs.filter(r => ["failed", "needs_attention"].includes(r.status)).length;
    const list = $("runs"); list.replaceChildren();
    if (!runs.length) list.append(node("p", "No runs yet. Submit your first task below.", "empty"));
    for (const run of runs) {
      const button = node("button", undefined, "run" + (run.id === selected ? " selected" : ""));
      button.append(node("span", run.task.id, "run-title"));
      const meta = node("span", undefined, "run-meta");
      meta.append(node("span", run.id.slice(0, 10)), node("span", label(run.status), "badge " + run.status));
      button.append(meta);
      button.onclick = () => { selected = run.id; activeTab = "evidence"; refresh(); };
      list.append(button);
    }
    if (selected) {
      const run = await request("/runs/" + selected);
      const key = selected + ":" + activeTab + ":" + JSON.stringify(run);
      if (key !== lastRender || activeTab === "events") { await renderDetail(run); lastRender = key; }
    }
  } catch (error) { message(error.message); }
  finally { refreshing = false; }
}
async function renderDetail(run) {
  const detail = $("detail"); detail.replaceChildren();
  const top = node("div", undefined, "detail-top");
  top.append(node("h2", run.task.id, "detail-title"), node("span", label(run.status), "badge " + run.status));
  detail.append(top, node("p", run.task.report, "report"));
  const hash = run.handoff?.candidate_commit;
  detail.append(node("div", hash ? "CANDIDATE  " + hash : "BASE  " + run.base_commit, "commit"));
  const pipeline = node("div", undefined, "pipeline");
  const revision = run.handoff?.revisions_used ?? Math.max(0, ...run.steps.filter(s => s.id.startsWith("revise_")).map(s => Number(s.id.split("_")[1])));
  const stages = [["Implementation", revision ? "revise_" + revision : "implement"], ["Verification", "verify_" + revision],
    ["Correctness", "correctness_" + revision], ["Security", "security_" + revision], ["Handoff", "handoff"]];
  for (const [name, id] of stages) {
    const step = run.steps.find(s => s.id === id);
    pipeline.append(node("div", name + " · " + (step?.status ?? "pending"), "stage " + (step?.status ?? "pending")));
  }
  detail.append(pipeline);
  if (run.error) detail.append(node("p", run.error, "note"));
  if (run.handoff) {
    const h = run.handoff;
    detail.append(node("p", `Verified: ${h.verified ? "yes" : "no"} · Reviewed: ${h.reviewed ? "yes" : "no"} · Revisions: ${h.revisions_used} · Blockers: ${h.blocking_findings.length}`, "note"));
    if (h.known_gaps.length) detail.append(node("p", "Known gaps: " + h.known_gaps.join("; "), "note"));
  }
  const actions = node("div", undefined, "actions");
  function action(text, endpoint, body, className) {
    const button = node("button", text, className); button.onclick = async () => {
      button.disabled = true;
      try { await request(`/runs/${run.id}/${endpoint}`, "POST", body); message(text + " recorded."); await refresh(); }
      catch (error) { message(error.message); button.disabled = false; }
    }; actions.append(button);
  }
  if (["pending", "running"].includes(run.status)) action("Cancel run", "cancel", undefined, "danger");
  if (["failed", "cancelled"].includes(run.status)) action("Resume unfinished steps", "resume");
  if (run.status === "ready_for_approval") action("Approve this commit", "approve", {candidate_commit: hash});
  if (["ready_for_approval", "needs_attention"].includes(run.status)) {
    const deny = node("button", "Deny candidate", "danger");
    deny.onclick = async () => {
      const reason = window.prompt("Reason for denying this candidate:");
      if (!reason?.trim()) return;
      try { await request(`/runs/${run.id}/deny`, "POST", {candidate_commit: hash, reason}); await refresh(); }
      catch (error) { message(error.message); }
    }; actions.append(deny);
  }
  detail.append(actions);
  const tabs = node("div", undefined, "tabs");
  for (const [id, title] of [["evidence", "Evidence"], ["diff", "Candidate diff"], ["events", "Event stream"]]) {
    const button = node("button", title, activeTab === id ? "chosen" : "");
    button.onclick = () => { activeTab = id; refresh(); }; tabs.append(button);
  }
  detail.append(tabs);
  if (activeTab === "diff") {
    try { detail.append(node("pre", await request(`/runs/${run.id}/diff`))); }
    catch (error) { detail.append(node("p", error.message, "empty")); }
  } else if (activeTab === "events") {
    const events = await request(`/runs/${run.id}/events`);
    for (const event of events.filter(e => e.type !== "worker.event").slice(-35)) {
      const row = node("div", undefined, "event");
      row.append(node("span", "#" + event.seq), node("span", event.type), node("span", event.step_id ?? "workflow"));
      detail.append(row);
    }
  } else {
    const artifacts = run.steps.filter(s => s.status === "completed" && !["implement", "handoff"].includes(s.id) && !s.id.startsWith("revise_"));
    for (const step of artifacts.slice(-4)) {
      const disclosure = node("details"); disclosure.append(node("summary", label(step.id)));
      let loaded = false;
      disclosure.ontoggle = async () => {
        if (disclosure.open && !loaded) {
          loaded = true;
          try { disclosure.append(node("pre", JSON.stringify(await request(`/runs/${run.id}/artifacts/${step.id}`), null, 2))); }
          catch (error) { disclosure.append(node("p", error.message)); }
        }
      }; disclosure.style.marginTop = "16px"; detail.append(disclosure);
    }
    if (!artifacts.length) detail.append(node("p", "Evidence appears as each step finishes.", "empty"));
  }
}
$("connect").onsubmit = async event => {
  event.preventDefault(); token = $("token").value.trim();
  try {
    await request("/runs"); connected = true;
    $("token").value = ""; $("connect").hidden = true;
    $("refresh").disabled = false; $("submit-button").disabled = false;
    const health = await (await fetch("/health")).json();
    $("environment").textContent = health.adapter === "fake" ? "Local · scripted fixtures" : "Local · Codex CLI";
    tasks = await request("/demo/tasks");
    for (let i = 0; i < tasks.length; i++) {
      const option = node("option", tasks[i].id); option.value = String(i); $("demo").append(option);
    }
    message(); await refresh();
  } catch (error) { message(error.message); token = ""; }
};
$("demo").onchange = () => { const index = $("demo").value; if (index !== "") $("task").value = JSON.stringify(tasks[Number(index)], null, 2); };
$("submit").onsubmit = async event => {
  event.preventDefault(); $("submit-button").disabled = true;
  try {
    const task = JSON.parse($("task").value);
    const result = await request("/runs", "POST", {task}); selected = result.run_id;
    message("Workflow queued. Publishing requires a separate action."); await refresh();
  } catch (error) { message(error.message); }
  finally { $("submit-button").disabled = false; }
};
$("refresh").onclick = refresh;
setInterval(refresh, 3000);
