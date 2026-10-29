(function () {
  "use strict";
  var root = document.documentElement;
  // theme toggle (no storage: works when opened from disk in any browser)
  var tb = document.getElementById("theme-btn");
  if (tb) tb.addEventListener("click", function () {
    root.setAttribute("data-theme", root.getAttribute("data-theme") === "dark" ? "light" : "dark");
  });
  // expand / collapse all sections
  var eb = document.getElementById("expand-btn");
  if (eb) eb.addEventListener("click", function () {
    var all = document.querySelectorAll("details");
    var open = Array.prototype.some.call(all, function (d) { return !d.open; });
    all.forEach(function (d) { d.open = open; });
    eb.textContent = open ? "Свернуть все" : "Раскрыть все";
  });
  // open all details before printing
  window.addEventListener("beforeprint", function () {
    document.querySelectorAll("details").forEach(function (d) { d.open = true; });
  });
  // JSON download from the embedded blob
  function dl() {
    var txt = document.getElementById("result-json").textContent;
    var blob = new Blob([txt], { type: "application/json;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "chem-agent-result.json";
    document.body.appendChild(a); a.click(); a.remove();
  }
  ["json-btn", "json-btn2"].forEach(function (id) {
    var b = document.getElementById(id); if (b) b.addEventListener("click", dl);
  });
  // sortable tables: numeric via data-v, otherwise text
  function val(td) {
    if (!td) return "";
    var v = td.getAttribute("data-v");
    if (v !== null && v !== "" && v !== "None" && !isNaN(parseFloat(v))) return parseFloat(v);
    return td.textContent.trim().toLowerCase();
  }
  document.querySelectorAll("table.sortable").forEach(function (t) {
    t.querySelectorAll("th").forEach(function (th, idx) {
      th.addEventListener("click", function () {
        var body = t.tBodies[0]; if (!body) return;
        var asc = !th.classList.contains("asc");
        t.querySelectorAll("th").forEach(function (h) { h.classList.remove("asc", "desc"); });
        th.classList.add(asc ? "asc" : "desc");
        var rows = Array.prototype.slice.call(body.rows);
        rows.sort(function (a, b) {
          var x = val(a.cells[idx]), y = val(b.cells[idx]);
          if (typeof x === "number" && typeof y === "number") return asc ? x - y : y - x;
          return asc ? String(x).localeCompare(String(y), "ru") : String(y).localeCompare(String(x), "ru");
        });
        rows.forEach(function (r) { body.appendChild(r); });
      });
    });
  });
  // click-to-zoom charts
  var zoom = document.getElementById("zoom");
  document.querySelectorAll("svg.chart").forEach(function (svg) {
    svg.addEventListener("click", function () {
      if (!zoom) return;
      var inner = zoom.querySelector(".zoom-inner");
      inner.innerHTML = "";
      inner.appendChild(svg.cloneNode(true));
      zoom.hidden = false;
    });
  });
  if (zoom) zoom.addEventListener("click", function () { zoom.hidden = true; });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && zoom) zoom.hidden = true; });
})();
