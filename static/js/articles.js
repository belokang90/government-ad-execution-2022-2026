"use strict";
const checks = {
  numbers: "건수·금액·증감률이 팩트시트와 일치하는가?",
  scope: "연도·날짜 기준·기관·매체 범위·단위가 정확한가?",
  claims: "근거 없는 특혜·차별·정치적 원인 단정이 없는가?",
  sources: "자료 출처와 분석 조건·한계가 명시돼 있는가?",
};
const state = {
  config: null,
  current: null,
  articles: [],
  prepared: [],
  busy: false,
  batch: false,
  stop: false,
  contentDirty: false,
  reviewDirty: false,
  request: 0,
};
const $ = (id) => document.getElementById(id);
const say = (message, error = false) => {
  $("message").textContent = message;
  $("message").classList.toggle("error", error);
};
function node(tag, text) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  return e;
}
async function api(path, method = "GET", body) {
  const response = await fetch("/api/articles" + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw Error("서버 응답을 읽지 못했습니다. 연결 상태를 확인하세요.");
  }
  if (!response.ok)
    throw Error(typeof data.detail === "string" ? data.detail : "입력값과 필수 항목을 확인하세요.");
  return data;
}
function pairs() {
  const bases =
    $("baseYear").value === "all" ? state.config.available_years : [Number($("baseYear").value)];
  const targets = [...document.querySelectorAll(".target-year:checked:not(:disabled)")].map((e) =>
    Number(e.value),
  );
  return bases.flatMap((b) => targets.filter((c) => b !== c).map((c) => [b, c]));
}
function pairLabel(b, c) {
  return b === 2026 || c === 2026 ? "각 연도 광고시작일 9월 30일 이하" : "각 연도 파일 전체 · 연간";
}
function updateSelection() {
  if (!state.config) return;
  for (const box of document.querySelectorAll(".target-year")) {
    box.disabled =
      !state.config.available_years.includes(Number(box.value)) ||
      $("baseYear").value === box.value;
  }
  $("pairCount").textContent =
    `선택한 비교: ${pairs().length}개 조합 · 증감은 비교연도에서 기준연도를 뺀 값입니다.`;
  $("prepareButton").disabled = state.busy || !state.config.db_ready || pairs().length === 0;
}
function checked() {
  return Object.fromEntries(Object.keys(checks).map((k) => [k, $("check_" + k).value === "pass"]));
}
function updateButtons() {
  const a = state.current,
    complete = a && a.generation_status === "완료";
  $("generateOne").disabled = !a || state.busy || a.generation_status === "생성중" || complete;
  $("saveContent").disabled = !complete || state.busy || !state.contentDirty;
  $("saveReview").disabled = !complete || state.busy || state.contentDirty;
  $("holdArticle").disabled = $("saveReview").disabled;
  const ready =
    complete &&
    !state.contentDirty &&
    !state.reviewDirty &&
    a.status !== "보류" &&
    a.review_revision === a.revision &&
    a.review_checks &&
    Object.keys(checks).every((k) => a.review_checks[k] === true);
  $("approveArticle").disabled = !ready || state.busy || Boolean(a && a.status === "승인");
  $("approvalHint").textContent = state.contentDirty
    ? "수정 내용을 저장한 뒤 다시 검수하세요."
    : state.reviewDirty
      ? "검수 결과를 먼저 저장하세요."
      : ready
        ? "현재 원고의 검수 4항목을 모두 통과했습니다. 승인할 수 있습니다."
        : "현재 원고의 4항목을 모두 통과한 검수 결과를 저장해야 승인할 수 있습니다.";
  const n = document.querySelectorAll(".prepared-check:checked").length;
  $("generateSelected").disabled = state.busy || !n;
  $("generateSelected").textContent = `선택한 ${n}편 기사 생성`;
  updateSelection();
}
async function guarded(work) {
  if (state.busy) return;
  state.busy = true;
  updateButtons();
  try {
    await work();
  } catch (e) {
    say(e.message, true);
  } finally {
    state.busy = false;
    updateButtons();
  }
}
function number(value) {
  return value == null
    ? "계산 불가"
    : new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(Number(value));
}
function rate(value) {
  return value == null ? "계산 불가" : number(value) + "%";
}
function renderFact(a) {
  const f = a.fact_sheet,
    scope = f.scope;
  $("articleMeta").textContent =
    `${a.base_year}년 기준 → ${a.current_year}년 비교 | ${scope.period_label || pairLabel(a.base_year, a.current_year)} | ${scope.org_types.join("·")}`;
  $("factNote").textContent =
    "같은 기관·매체 조건의 집계입니다. 증감률은 원값으로 계산했습니다. 아래 금액은 대조를 위한 원 단위 값입니다.";
  $("factRows").replaceChildren();
  for (const r of f.기사용분석.유형별매체군비교) {
    const tr = node("tr");
    for (const v of [
      `${r.media_type} · ${r.group}`,
      number(r.base_count),
      number(r.current_count),
      number(r.count_change),
      rate(r.count_change_pct),
      number(r.base_amount),
      number(r.current_amount),
      rate(r.amount_change_pct),
    ])
      tr.append(node("td", v));
    $("factRows").append(tr);
  }
  $("sourceInfo").replaceChildren();
  for (const year of Object.keys(f.periods)) {
    $("sourceInfo").append(
      node(
        "p",
        `${year}년: ${f.periods[year].source.provider} / ${f.periods[year].source.file_name} / 자료 기준일 ${f.periods[year].source.reference_date}`,
      ),
    );
  }
  $("sourceInfo").append(
    node("p", "선정 매체: " + f.brand_definitions.map((b) => `${b.group} ${b.brand}`).join(", ")),
  );
  $("sourceInfo").append(node("p", f.classification_note));
  const budget = f.기사용분석.예산편성배경;
  if (budget) {
    $("sourceInfo").append(node("p", budget.비교연도선정이유 + " " + budget.확인범위));
    for (const source of budget.출처) {
      const p = node("p", `${source.year}년도 예산안 · ${source.government} · ${source.date} · `);
      const a = node("a", "공식 근거 보기");
      a.href = source.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      p.append(a);
      $("sourceInfo").append(p);
    }
  }
  for (const limit of f.limitations) $("sourceInfo").append(node("p", limit));
  $("factJson").textContent = JSON.stringify(f, null, 2);
  $("generationJson").textContent = a.generation_record
    ? JSON.stringify(a.generation_record, null, 2)
    : "아직 기사 생성 기록이 없습니다.";
}
function renderArticle(a) {
  state.current = a;
  state.contentDirty = false;
  state.reviewDirty = false;
  $("emptyEditor").hidden = true;
  $("editor").hidden = false;
  $("articleTitle").value = a.title;
  $("articleBody").value = a.body;
  $("articleTitle").disabled = $("articleBody").disabled = a.generation_status !== "완료";
  $("articleStatus").textContent =
    `기사 번호: ${a.id} · 상태: ${a.status} · 생성: ${a.generation_status} · 원고 버전: ${a.revision}`;
  $("generationError").textContent = a.generation_error || "";
  $("reviewer").value = a.reviewer || "";
  $("reviewComment").value = "";
  for (const k of Object.keys(checks))
    $("check_" + k).value = a.review_checks ? (a.review_checks[k] ? "pass" : "fail") : "";
  renderFact(a);
  $("reviewHistory").replaceChildren();
  for (const r of a.reviews) {
    $("reviewHistory").append(
      node(
        "p",
        `${r.reviewed_at} · ${r.reviewer} · 원고 v${r.article_revision} · ${r.action} · ${r.passed ? "전체 통과" : "실패 항목 있음"} · ${r.comment}`,
      ),
    );
  }
  renderList();
  updateButtons();
}
async function openArticle(id) {
  if (state.contentDirty) {
    say("현재 원고의 수정 내용을 먼저 저장하세요.", true);
    return;
  }
  const request = ++state.request;
  try {
    const article = await api("/" + id);
    if (request === state.request) renderArticle(article);
  } catch (e) {
    say(e.message, true);
  }
}
function renderList() {
  $("articleList").replaceChildren();
  let base;
  for (const a of state.articles) {
    if (base !== a.base_year) {
      base = a.base_year;
      $("articleList").append(node("h3", base + "년 기준"));
    }
    const b = node(
      "button",
      `${a.base_year} → ${a.current_year} · ${a.status} / ${a.generation_status}\n${a.title || "근거 준비 완료"}`,
    );
    b.type = "button";
    b.className = "article-item" + (state.current && state.current.id === a.id ? " active" : "");
    b.onclick = () => openArticle(a.id);
    $("articleList").append(b);
  }
  if (!state.articles.length) $("articleList").append(node("p", "저장된 기사가 없습니다."));
}
async function refreshList() {
  state.articles = (await api("")).articles;
  renderList();
  renderPrepared();
}
function renderPrepared() {
  $("preparedArea").hidden = state.prepared.length === 0;
  const chosen = new Set(
    [...document.querySelectorAll(".prepared-check:checked")].map((e) => Number(e.value)),
  );
  $("preparedRows").replaceChildren();
  for (const item of state.prepared) {
    const a = state.articles.find((a) => a.id === item.id) || {
      ...item,
      generation_status: "대기",
    };
    const tr = node("tr"),
      cell = node("td"),
      box = node("input");
    box.type = "checkbox";
    box.className = "prepared-check";
    box.value = String(a.id);
    box.checked = chosen.size ? chosen.has(a.id) : a.generation_status !== "완료";
    box.onchange = updateButtons;
    cell.append(box);
    tr.append(
      cell,
      node("td", `${a.base_year}년 → ${a.current_year}년`),
      node("td", pairLabel(a.base_year, a.current_year)),
      node("td", a.generation_status),
    );
    const open = node("button", "열기");
    open.type = "button";
    open.className = "secondary small";
    open.onclick = () => openArticle(a.id);
    const last = node("td");
    last.append(open);
    tr.append(last);
    $("preparedRows").append(tr);
  }
  const count = document.querySelectorAll(".prepared-check:checked").length;
  $("generateSelected").textContent = `선택한 ${count}편 기사 생성`;
}
function reviewPayload() {
  if (Object.keys(checks).some((k) => !$("check_" + k).value))
    throw Error("검수 4항목을 모두 통과 또는 실패로 선택하세요.");
  if (!$("reviewer").value.trim()) throw Error("검토자 이름을 입력하세요.");
  return {
    revision: state.current.revision,
    reviewer: $("reviewer").value.trim(),
    checks: checked(),
    comment: $("reviewComment").value,
  };
}
async function init() {
  for (const year of [2022, 2023, 2024, 2025, 2026]) {
    const label = node("label"),
      input = node("input");
    input.type = "checkbox";
    input.value = String(year);
    input.className = "target-year";
    input.checked = year === 2026;
    input.onchange = updateSelection;
    label.append(input, node("span", year + "년"));
    $("targetYears").append(label);
  }
  for (const [key, label] of Object.entries(checks)) {
    const row = node("div"),
      text = node("label", label),
      select = node("select");
    row.className = "check-row";
    text.htmlFor = "check_" + key;
    select.id = "check_" + key;
    for (const [value, caption] of [
      ["", "검수 전"],
      ["pass", "통과"],
      ["fail", "실패"],
    ]) {
      const option = node("option", caption);
      option.value = value;
      select.append(option);
    }
    select.onchange = () => {
      state.reviewDirty = true;
      updateButtons();
    };
    row.append(text, select);
    $("checklist").append(row);
  }
  $("baseYear").onchange = updateSelection;
  $("selectAllYears").onclick = () => {
    for (const e of document.querySelectorAll(".target-year:not(:disabled)")) e.checked = true;
    updateSelection();
  };
  $("prepareButton").onclick = () =>
    guarded(async () => {
      say("선택한 연도 자료를 집계하고 있습니다. 첫 집계는 잠시 걸릴 수 있습니다.");
      const ps = pairs();
      const data = await api("/prepare", "POST", {
        base_years: [...new Set(ps.map((p) => p[0]))],
        compare_years: [...new Set(ps.map((p) => p[1]))],
      });
      state.prepared = data.pairs;
      // 새 비교 묶음에는 이전 묶음의 체크 상태를 적용하지 않는다.
      $("preparedRows").replaceChildren();
      await refreshList();
      await openArticle(data.article_ids[0]);
      say(`${data.article_ids.length}개 비교의 근거를 저장했습니다. 생성할 기사를 선택하세요.`);
    });
  $("refreshList").onclick = () =>
    guarded(async () => {
      await refreshList();
      if (state.current && !state.contentDirty) await openArticle(state.current.id);
      say("목록을 새로 불러왔습니다.");
    });
  $("generateSelected").onclick = () =>
    guarded(async () => {
      const ids = [...document.querySelectorAll(".prepared-check:checked")].map((e) =>
        Number(e.value),
      );
      state.batch = true;
      state.stop = false;
      $("stopBatch").hidden = false;
      let ok = 0,
        failed = 0;
      const errors = [];
      try {
        for (const id of ids) {
          if (state.stop) break;
          say(`기사 생성 중: ${ok + failed + 1}/${ids.length}편`);
          try {
            const a = await api("/" + id + "/generate", "POST");
            ok++;
            if (state.current && state.current.id === id && !state.contentDirty) renderArticle(a);
          } catch (e) {
            failed++;
            errors.push(e.message);
          }
          await refreshList();
        }
        say(
          `생성 완료 ${ok}편 · 실패 ${failed}편${state.stop ? " · 중단했습니다." : ""}${errors.length ? "\n" + errors.join("\n") : ""}`,
          failed > 0,
        );
      } finally {
        state.batch = false;
        $("stopBatch").hidden = true;
      }
    });
  $("stopBatch").onclick = () => {
    state.stop = true;
    say("현재 요청이 끝나면 다음 기사 생성을 중단합니다.");
  };
  $("generateOne").onclick = () =>
    guarded(async () => {
      say("OpenAI API로 기사를 생성하고 있습니다.");
      const a = await api("/" + state.current.id + "/generate", "POST");
      renderArticle(a);
      await refreshList();
      say("기사 초안을 저장했습니다. 근거와 대조해 검수하세요.");
    });
  for (const id of ["articleTitle", "articleBody"])
    $(id).oninput = () => {
      state.contentDirty = true;
      updateButtons();
    };
  for (const id of ["reviewer", "reviewComment"])
    $(id).oninput = () => {
      state.reviewDirty = true;
      updateButtons();
    };
  $("saveContent").onclick = () =>
    guarded(async () => {
      const a = await api("/" + state.current.id, "PUT", {
        revision: state.current.revision,
        title: $("articleTitle").value,
        body: $("articleBody").value,
      });
      renderArticle(a);
      await refreshList();
      say("수정 내용을 저장했습니다. 변경된 원고를 다시 검수하세요.");
    });
  for (const [id, path] of [
    ["saveReview", "review"],
    ["holdArticle", "hold"],
  ])
    $(id).onclick = () =>
      guarded(async () => {
        const a = await api("/" + state.current.id + "/" + path, "PUT", reviewPayload());
        renderArticle(a);
        await refreshList();
        say(
          a.status === "보류"
            ? "보류로 저장했습니다. 수정·재검수 전에는 승인할 수 없습니다."
            : "검수 결과를 저장했습니다. 모든 항목이 통과해 승인할 수 있습니다.",
        );
      });
  $("approveArticle").onclick = () =>
    guarded(async () => {
      const a = await api("/" + state.current.id + "/approve", "PUT", {
        revision: state.current.revision,
      });
      renderArticle(a);
      await refreshList();
      say("승인했습니다. 승인된 기사 화면에서 확인할 수 있습니다.");
    });
  try {
    state.config = await api("/config");
    $("scopeInfo").textContent =
      `기관: ${state.config.org_types.join("·")} | 매체 유형: ${state.config.media_types.join("·")} | 모델: ${state.config.model} | 선정 매체 ${state.config.brands.length}개`;
    for (const option of $("baseYear").options)
      if (option.value !== "all")
        option.disabled = !state.config.available_years.includes(Number(option.value));
    updateSelection();
    if (!state.config.db_ready) say(state.config.db_error, true);
    else {
      await refreshList();
      say(
        state.config.api_key_ready
          ? "비교할 연도를 선택하세요."
          : "근거 집계는 가능합니다. 기사 생성에는 .env의 OPENAI_API_KEY 설정과 서버 재시작이 필요합니다.",
      );
    }
  } catch (e) {
    say(e.message, true);
  }
  updateButtons();
}
document.addEventListener("DOMContentLoaded", init);
