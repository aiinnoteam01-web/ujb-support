/* 의정부 지원모아 — 정적 화면 (외부 스크립트 없음) */
(() => {
  "use strict";

  // ---------- 상수 ----------
  const SCOPE = { uijeongbu: "의정부시", gyeonggi: "경기도", national: "전국" };
  const TARGETS = ["청년", "시니어", "장애인", "임산부·출산", "소상공인", "중소기업", "창업", "법인·단체"];
  const CATEGORIES = ["일자리", "주거", "교육", "생활·복지", "사업지원", "문화·참여"];
  const SOURCES = { gov24: "보조금24", bizinfo: "기업마당", kstartup: "K-Startup", jobaba: "경기도 잡아바" };
  const SOURCE_FULL = { gov24: "행정안전부 보조금24", bizinfo: "중소벤처기업부 기업마당(공공누리 제3유형)", kstartup: "창업진흥원 K-Startup", jobaba: "경기도 잡아바(경기데이터드림)" };
  const SORTS = { deadline: "마감 임박순", views: "많이 본 순", name: "이름순" };
  const PAGE = 30;

  // ---------- 상태 ----------
  let ITEMS = [], STATUS = null, UPDATED = "";
  const byId = new Map();
  let myAge = null;
  try { const v = localStorage.getItem("ujbs.age"); myAge = v === null ? null : JSON.parse(v); } catch { /* 저장 불가 */ }
  const saveAge = () => { try { localStorage.setItem("ujbs.age", JSON.stringify(myAge)); } catch { /* 저장 불가 */ } };

  // ---------- 날짜 ----------
  const TODAY = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const days = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 864e5);
  const fmt = (iso) => iso ? `${Number(iso.slice(5, 7))}.${Number(iso.slice(8, 10))}` : "";
  function state(it) {
    if (it.start && it.start > TODAY) return "upcoming";
    if (it.always || !it.end) return "always";
    return "open";
  }
  const dLeft = (it) => it.end && !it.always ? days(TODAY, it.end) : null;

  // ---------- DOM 도우미 ----------
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }

  // ---------- 거르기·정렬 ----------
  function ageOk(it) {
    if (myAge === null || myAge === "") return true;
    const a = Number(myAge);
    if (it.age_min != null && a < it.age_min) return false;
    if (it.age_max != null && a > it.age_max) return false;
    return true;
  }
  const norm = (s) => (s || "").replace(/\s+/g, "").toLowerCase();
  function matches(it, q) {
    if (it.end && !it.always && it.end < TODAY) return false; // 수집 뒤 마감된 공고
    if (q.scope && it.scope !== q.scope) return false;
    if (q.who && !(it.targets || []).includes(q.who)) return false;
    if (q.cat && it.category !== q.cat) return false;
    if (q.state && state(it) !== q.state) return false;
    if (q.soon) { const d = dLeft(it); if (d === null || d > 7) return false; }
    if (q.mine && !ageOk(it)) return false;
    if (q.q) {
      const hay = norm(`${it.title} ${it.agency} ${it.target_text} ${it.summary}`);
      if (!norm(q.q).split(",").every((w) => hay.includes(w))) return false;
    }
    return true;
  }
  function sortItems(list, how) {
    const key = {
      deadline: (it) => { const d = dLeft(it); return d === null ? 99999 : d; },
      views: (it) => -(it.views || 0),
      name: () => 0,
    }[how] || (() => 0);
    return list.slice().sort((a, b) => (key(a) - key(b)) || a.title.localeCompare(b.title, "ko"));
  }

  // ---------- 조각 ----------
  const scopeBadge = (it) => h("span", { class: `badge b-${it.scope}` }, SCOPE[it.scope] || "");
  const sourceTag = (it) => h("span", { class: "source" }, `출처 · ${SOURCES[it.source] || it.source}`);
  function ddayBadge(it) {
    const st = state(it);
    if (st === "upcoming") return h("span", { class: "dday soon" }, `${fmt(it.start)} 시작`);
    if (st === "always") return h("span", { class: "dday always" }, "상시");
    const d = dLeft(it);
    const cls = d <= 3 ? "dday d3" : d <= 7 ? "dday d7" : "dday";
    return h("span", { class: cls, title: `마감 ${it.end}` }, d === 0 ? "오늘 마감" : `D-${d}`);
  }
  function itemRow(it) {
    const who = (it.targets || []).join("·");
    return h("li", { class: "item" },
      ddayBadge(it),
      h("div", { class: "item-body" },
        h("button", { class: "item-title", type: "button", onclick: () => openDetail(it.id) }, it.title),
        h("div", { class: "item-meta" }, [who, it.category, it.agency].filter(Boolean).join(" · ")),
        h("div", { class: "item-tags" }, sourceTag(it))),
      scopeBadge(it));
  }
  function itemList(list) {
    if (!list.length) return h("p", { class: "empty" }, "조건에 맞는 지원사업이 없어요. 조건을 바꿔 보세요.");
    return h("ul", { class: "items" }, list.map(itemRow));
  }
  function searchForm(q) {
    const input = h("input", { type: "search", value: q.q || "", placeholder: "무엇을 도와드릴까요? 예: 출산, 운영자금, 일자리", "aria-label": "지원사업 검색" });
    return h("form", { class: "search", role: "search", onsubmit: (e) => { e.preventDefault(); go({ ...q, q: input.value.trim() || undefined }); } },
      input, h("button", { class: "btn btn-dark", type: "submit" }, "찾아보기"));
  }
  function meBar() {
    const input = h("input", { id: "my-age", type: "number", min: "0", max: "120", inputmode: "numeric", value: myAge ?? "", placeholder: "내 나이" });
    const apply = () => { const v = input.value.trim(); myAge = v === "" ? null : Math.max(0, Math.min(120, Number(v))); saveAge(); render(); };
    input.addEventListener("change", apply);
    return h("div", { class: "me" },
      h("strong", {}, "제 나이는 만"),
      h("label", { for: "my-age", class: "sr-only" }, "만 나이"), input,
      h("strong", {}, "살이에요"),
      h("button", { class: "btn btn-accent", type: "button", onclick: apply }, "적용"),
      myAge !== null ? h("button", { class: "btn", type: "button", onclick: () => { myAge = null; saveAge(); render(); } }, "지우기") : null,
      h("span", { class: "muted" }, "이 기기에만 기억해요"));
  }

  // ---------- 화면 ----------
  // 순서: 숫자 타일 → 검색 → 내 나이 → 구분 → 누구를 위한 지원 → 분야 → 신청 상태 → 기타 → 목록
  const TILE_KEYS = ["soon", "scope", "state"];
  let shown = PAGE;
  function viewMain(q) {
    const live = ITEMS.filter(ageOk);
    const count = (f) => live.filter((it) => matches(it, f)).length;
    const list = sortItems(ITEMS.filter((it) => matches(it, { ...q, mine: true })), q.sort || "deadline");
    const set = (patch) => go({ ...q, ...patch });

    const tile = (label, n, key, val, cls) => {
      const on = (q[key] || "") === val;
      const patch = Object.fromEntries(TILE_KEYS.map((k) => [k, undefined]));
      if (!on) patch[key] = val;
      return h("button", { class: `tile ${cls}`, type: "button", "aria-pressed": String(on), onclick: () => set(patch) },
        h("span", { class: "tile-label" }, label), h("span", { class: "tile-num" }, n.toLocaleString()));
    };
    const row = (label, key, options, extra) => h("div", { class: `frow ${extra || ""}`.trim(), role: "group", "aria-label": label },
      h("span", { class: "flabel" }, label),
      [["", "전체"], ...options].map(([v, t]) => h("button", { class: `chip ${key === "who" && v ? "who-" + TARGETS.indexOf(v) : ""}`.trim(), type: "button", "aria-pressed": String((q[key] || "") === v), onclick: () => set({ [key]: v || undefined }) }, t)));
    const active = TILE_KEYS.some((k) => q[k]) || q.who || q.cat || q.q;

    return [
      h("section", { class: "tiles", "aria-label": "한눈에 보기 (누르면 아래 목록이 바뀝니다)" },
        tile("7일 안에 마감", count({ soon: true }), "soon", "1", "t-peach"),
        tile("의정부시 사업", count({ scope: "uijeongbu" }), "scope", "uijeongbu", "t-sky"),
        tile("경기도 사업", count({ scope: "gyeonggi" }), "scope", "gyeonggi", "t-mint"),
        tile("전국 대상", count({ scope: "national" }), "scope", "national", "t-lilac"),
        tile("곧 접수 시작", count({ state: "upcoming" }), "state", "upcoming", "t-lemon")),
      searchForm(q),
      meBar(),
      h("section", { class: "filters", "aria-label": "조건" },
        row("구분", "scope", Object.entries(SCOPE)),
        row("누구를 위한 지원", "who", TARGETS.map((t) => [t, t])),
        row("분야", "cat", CATEGORIES.map((c) => [c, c])),
        row("신청 상태", "state", [["open", "접수 중"], ["upcoming", "접수 예정"], ["always", "상시·예산 소진 시"]]),
        h("div", { class: "frow" },
          h("span", { class: "flabel" }, "기타"),
          h("button", { class: "chip", type: "button", "aria-pressed": String(!!q.soon), onclick: () => set({ soon: q.soon ? undefined : "1" }) }, "7일 안에 마감"),
          active ? h("button", { class: "btn", type: "button", onclick: () => go({ sort: q.sort }) }, "조건 지우기") : null)),
      h("div", { class: "result-bar" },
        h("h2", {}, `${q.who ? q.who + " " : ""}지원사업 ${list.length.toLocaleString()}건`),
        myAge !== null ? h("span", { class: "muted" }, `만 ${myAge}세 조건 적용 중`) : null,
        h("label", { class: "sort-label", for: "sort" }, "정렬",
          h("select", { id: "sort", onchange: (e) => set({ sort: e.target.value }) },
            Object.entries(SORTS).map(([v, t]) => h("option", { value: v, selected: (q.sort || "deadline") === v }, t))))),
      itemList(list.slice(0, shown)),
      list.length > shown ? h("button", { class: "btn btn-dark more", type: "button", onclick: () => { shown += PAGE; render(); } },
        `더 보기 (${shown.toLocaleString()} / ${list.length.toLocaleString()}건)`) : null,
    ];
  }

  // ---------- 상세 ----------
  const dlg = () => document.getElementById("detail");
  function openDetail(id, push = true) {
    const it = byId.get(id);
    if (!it) return;
    dlg().replaceChildren(detailContent(it));
    if (!dlg().open) dlg().showModal();
    if (push) history.replaceState(null, "", withParam("id", id));
  }
  function closeDetail() { if (dlg().open) dlg().close(); }
  function detailContent(it) {
    const sec = (title, text) => text ? h("section", {}, h("h3", {}, title), h("p", {}, text)) : null;
    const shareBtn = h("button", { class: "btn", type: "button", onclick: async () => {
      try {
        if (navigator.share) await navigator.share({ title: it.title, url: location.href });
        else { await navigator.clipboard.writeText(location.href); shareBtn.textContent = "링크를 복사했어요"; }
      } catch { /* 취소 */ }
    } }, "공유");
    const periodText = it.always && !it.end ? (it.period_text || "상시") : [it.start && `${it.start} 부터`, it.end && `${it.end} 까지`].filter(Boolean).join(" ") || it.period_text;
    return h("div", {},
      h("div", { class: "d-head" },
        h("button", { class: "btn d-close", type: "button", "aria-label": "닫기", onclick: closeDetail }, "닫기"),
        h("div", { class: "d-badges" }, ddayBadge(it), scopeBadge(it), ...(it.targets || []).map((t) => h("span", { class: "badge b-who" }, t)), h("span", { class: "badge b-cat" }, it.category)),
        h("h2", { id: "detail-title" }, it.title),
        h("p", { class: "muted" }, it.agency)),
      h("div", { class: "d-body" },
        sec("신청 기간", periodText),
        sec("지원 대상", it.target_text),
        sec("내용", it.summary),
        sec("신청 방법", it.apply_method),
        sec("문의", it.contact),
        h("div", { class: "d-actions" },
          it.url ? h("a", { class: "btn btn-dark", href: it.url, target: "_blank", rel: "noopener noreferrer" }, "원문 공고 보기") : null,
          shareBtn,
          h("button", { class: "btn", type: "button", onclick: () => window.print() }, "인쇄")),
        h("p", { class: "license" }, `출처: ${SOURCE_FULL[it.source] || it.source}`)));
  }

  // ---------- 주소(해시) ----------
  function parse() {
    const raw = location.hash.replace(/^#/, "") || "/";
    const [path, qs] = raw.split("?");
    return { path: path || "/", q: Object.fromEntries(new URLSearchParams(qs || "")) };
  }
  const qsOf = (q) => new URLSearchParams(Object.entries(q).filter(([, v]) => v !== undefined && v !== "")).toString();
  function withParam(k, v) {
    const { path, q } = parse();
    if (v === undefined) delete q[k]; else q[k] = v;
    const s = qsOf(q);
    return `#${path}${s ? "?" + s : ""}`;
  }
  function go(q) { const s = qsOf(q); location.hash = `#/${s ? "?" + s : ""}`; }

  // ---------- 바닥글 수집 현황 ----------
  function renderStatus() {
    const box = document.getElementById("source-status");
    if (!box || !STATUS) return;
    box.replaceChildren(...Object.values(STATUS.sources).map((s) =>
      h("span", { class: s.ok ? "ok" : "fail" }, `${s.name} ${s.ok ? `${(s.kept || 0).toLocaleString()}건` : "수집 실패(이전 자료)"}`)));
  }

  // ---------- 그리기 ----------
  function render() {
    const { q } = parse();
    document.getElementById("main").replaceChildren(...viewMain(q).filter(Boolean));
    if (q.id) openDetail(q.id, false); else closeDetail();
  }
  let lastQuery = "";
  window.addEventListener("hashchange", () => {
    const query = location.hash.replace(/[?&]id=[^&]*/, "");
    if (query !== lastQuery) { shown = PAGE; lastQuery = query; }
    render();
  });

  document.addEventListener("DOMContentLoaded", async () => {
    dlg().addEventListener("close", () => { if (parse().q.id) history.replaceState(null, "", withParam("id", undefined)); });
    dlg().addEventListener("click", (e) => { if (e.target === dlg()) closeDetail(); });
    try {
      const [data, status] = await Promise.all([
        fetch("data/items.json", { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
        fetch("data/status.json", { cache: "no-cache" }).then((r) => r.ok ? r.json() : null).catch(() => null),
      ]);
      ITEMS = data.items || [];
      UPDATED = (data.updated_at || "").replace("T", " ").slice(0, 16);
      STATUS = status;
      ITEMS.forEach((it) => byId.set(it.id, it));
      const failed = STATUS ? Object.values(STATUS.sources).filter((s) => !s.ok).map((s) => s.name) : [];
      document.getElementById("updated").textContent = `${UPDATED} 새로 모음` + (failed.length ? ` · 수집 실패: ${failed.join(", ")}` : "");
    } catch {
      document.getElementById("updated").textContent = "자료 없음";
      document.getElementById("main").replaceChildren(h("p", { class: "empty" }, "아직 수집된 자료가 없어요. 첫 수집이 끝나면 지원사업이 보여요."));
      return;
    }
    renderStatus();
    render();
  });
})();
