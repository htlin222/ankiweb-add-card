// Type-in answer widget, embedded into a card field by `anki.py --type-answer`.
// AnkiWeb strips {{type:Field}}, so this replaces it: type on the front, Enter
// reveals the answer, and the back shows a letter-by-letter diff against the
// closest accepted answer. Expects a sibling <div class="tyin" data-ans="<base64>">.
(function () {
  function dec(b) { return decodeURIComponent(escape(atob(b))); }
  function tidy(s) { return s.normalize("NFKC").replace(/\s+/g, " ").trim().replace(/[.,;:!?\u3002\uff0c\uff1b\uff1a\uff01\uff1f]+$/, ""); }
  function same(a, b) { return a.toLowerCase() === b.toLowerCase(); }
  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function lcs(a, b) {
    var L = [], i, j;
    for (i = 0; i <= a.length; i++) { L.push([]); for (j = 0; j <= b.length; j++) L[i].push(0); }
    for (i = a.length - 1; i >= 0; i--) for (j = b.length - 1; j >= 0; j--)
      L[i][j] = same(a[i], b[j]) ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    return L;
  }
  function diff(a, b) {           // a = typed, b = expected
    var L = lcs(a, b), i = 0, j = 0, out = "";
    function span(c, t) { return '<span class="' + c + '">' + esc(t) + "</span>"; }
    while (i < a.length && j < b.length) {
      if (same(a[i], b[j])) { out += span("ok", a[i]); i++; j++; }
      else if (L[i + 1][j] >= L[i][j + 1]) out += span("bad", a[i++]);
      else out += span("miss", b[j++]);
    }
    while (i < a.length) out += span("bad", a[i++]);
    while (j < b.length) out += span("miss", b[j++]);
    return out;
  }
  function store(k, v) { try { v === null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch (e) { (window.__tyin = window.__tyin || {})[k] = v; } }
  function load(k) { try { return sessionStorage.getItem(k); } catch (e) { return (window.__tyin || {})[k] || null; } }
  function reveal() {
    if (typeof pycmd === "function") { pycmd("ans"); return; }        // desktop Anki
    var btns = document.querySelectorAll("button");
    for (var i = 0; i < btns.length; i++)
      if (/show answer|\u986f\u793a\u7b54\u6848/i.test(btns[i].textContent)) { btns[i].click(); return; }
  }
  function isBack() {             // desktop/most templates: <hr id=answer>; AnkiWeb: rating buttons
    if (document.getElementById("answer")) return true;
    var btns = document.querySelectorAll("button");
    for (var i = 0; i < btns.length; i++) if (/^(again|\u91cd\u4f86)$/i.test(btns[i].textContent.trim())) return true;
    return false;
  }
  setTimeout(function () {        // AnkiWeb runs card scripts before it swaps in the answer buttons
    var back = isBack();
    document.querySelectorAll(".tyin:not([data-init])").forEach(function (el) {
      el.setAttribute("data-init", "1");
      var alts = dec(el.dataset.ans).split("|").map(tidy).filter(Boolean);
      var key = "tyin:" + el.dataset.ans, input = el.querySelector("input"), res = el.querySelector(".res");
      ["keydown", "keyup", "keypress"].forEach(function (t) {
        input.addEventListener(t, function (e) { e.stopPropagation(); });   // keep site shortcuts out
      });
      if (!back) {
        store(key, null);
        input.addEventListener("input", function () { store(key, input.value); });
        input.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); reveal(); } });
        input.focus();
        return;
      }
      var typed = tidy(load(key) || "");
      input.value = typed; input.readOnly = true;
      var best = alts[0], score = -1;
      alts.forEach(function (a) { var s = lcs(typed, a)[0][0] / Math.max(a.length, typed.length, 1); if (s > score) { score = s; best = a; } });
      var right = alts.some(function (a) { return a.toLowerCase() === typed.toLowerCase(); });
      res.innerHTML = !typed ? '<span class="verdict miss">\u672a\u4f5c\u7b54</span>' + esc(best)
        : right ? '<span class="verdict ok">\u2713</span>' + diff(typed, best)
        : '<span class="verdict bad">\u2717</span>' + diff(typed, best);
    });
  }, 50);
})();
