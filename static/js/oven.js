(function () {
  var rows = Array.prototype.slice.call(document.querySelectorAll("#oven-table tbody tr"));
  var input = document.getElementById("temp"), scale = document.getElementById("scale"), out = document.getElementById("oven-out");

  function run() {
    rows.forEach(function (r) { r.classList.remove("hl"); });
    var v = CB.parseQty(input.value), key = scale.value;
    if (isNaN(v)) { out.textContent = "Type a temperature and the closest row lights up."; return; }
    var best = null, diff = Infinity;
    rows.forEach(function (r) {
      var d = Math.abs(parseFloat(r.dataset[key]) - v);
      if (d < diff) { diff = d; best = r; }
    });
    var tooFar = { f: 25, c: 15, fan: 15, gas: 1 }[key];
    best.classList.add("hl");
    var d = best.dataset;
    var msg = "Gas mark " + d.gas + ", " + d.c + "°C, " + d.fan + "°C fan, " + d.f + "°F.";
    if (key === "f") msg += " Exact: " + Math.round((v - 32) * 5 / 9) + "°C.";
    if (key === "c" || key === "fan") msg += " Exact: " + Math.round(v * 9 / 5 + 32) + "°F" + (key === "fan" ? " (fan setting)" : "") + ".";
    if (diff > tooFar) msg = "That's outside the gas mark range. Closest row: " + msg;
    out.textContent = msg;
  }
  input.addEventListener("input", run);
  scale.addEventListener("change", run);
})();
