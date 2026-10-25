(function () {
  // Ratios and packet size come from /js/yeast.json (data/yeast_eggs.json). Same maths as build.py.
  var $ = function (id) { return document.getElementById(id); }, Y = null;
  function tsp(dryG) { return CB.fmtFrac(Math.floor(dryG / Y.packet_g * Y.packet_tsp * 4 + 0.5) / 4); }
  function run() {
    var amt = CB.parseQty($("y-amt").value), u = $("y-unit").value, body = $("y-table").querySelector("tbody");
    body.innerHTML = "";
    if (!(amt > 0)) { $("y-a").textContent = "–"; $("y-extra").textContent = "Enter an amount."; return; }
    var toFresh = u !== "fresh";
    var dryG = u === "dry" ? amt : (u === "tsp" ? amt / Y.packet_tsp * Y.packet_g : amt * Y.packet_g);
    var res = Y.ratios.map(function (r) {
      var g = toFresh ? dryG / r.dry_per_fresh : amt * r.dry_per_fresh;
      return { label: r.label, g: g };
    });
    var lo = Math.min(res[0].g, res[1].g), hi = Math.max(res[0].g, res[1].g);
    var words = { fresh: "g fresh yeast", dry: "g dried yeast", tsp: " tsp dried yeast", packet: (amt === 1 ? " packet" : " packets") + " of dried yeast" }[u];
    $("y-q").textContent = $("y-amt").value.trim() + words + " is";
    $("y-a").textContent = CB.fmtG(lo) + " to " + CB.fmtG(hi) + "g " + (toFresh ? "fresh" : "dried");
    $("y-extra").textContent = toFresh ? (u === "dry" ? "" : "That's " + CB.fmtG(dryG) + "g of dried yeast to start with.")
      : "That's " + tsp(lo) + " to " + tsp(hi) + " level teaspoons of dried or instant yeast.";
    res.forEach(function (r) {
      var tr = document.createElement("tr");
      tr.innerHTML = "<td></td><td class=\"n\"></td>";
      tr.children[0].textContent = r.label;
      tr.children[1].textContent = CB.fmtG(r.g) + "g" + (toFresh ? "" : " (" + tsp(r.g) + " tsp)");
      body.appendChild(tr);
    });
  }
  fetch("/js/yeast.json").then(function (r) { return r.json(); }).then(function (y) {
    Y = y;
    $("y-amt").addEventListener("input", run);
    $("y-unit").addEventListener("change", run);
    run();
  });
})();
