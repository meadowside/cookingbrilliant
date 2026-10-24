(function () {
  var US_CUP = 236.5882365, METRIC_CUP = 250, US_TBSP = 14.78676478, AU_TBSP = 20, OZ = 28.349523125;
  var UNIT_WORDS = { cup: ["US cup", "US cups"], metric_cup: ["metric cup", "metric cups"], tbsp: ["tablespoon", "tablespoons"], au_tbsp: ["Australian tablespoon", "Australian tablespoons"], tsp: ["teaspoon", "teaspoons"], stick: ["stick", "sticks"] };
  var data = [], bySlug = {};
  var $ = function (id) { return document.getElementById(id); };

  function gramsPer(item, unit) {
    var u = item.u;
    if (unit === "metric_cup") return u.cup ? u.cup * METRIC_CUP / US_CUP : null;
    if (unit === "au_tbsp") return u.tbsp ? u.tbsp * AU_TBSP / US_TBSP : null;
    return u[unit] || null;
  }

  function findItem(q) {
    q = String(q || "").trim().toLowerCase();
    if (!q) return null;
    if (bySlug[q]) return bySlug[q];
    for (var i = 0; i < data.length; i++) {
      var d = data[i];
      if (d.n.toLowerCase() === q || d.us.toLowerCase() === q) return d;
    }
    for (i = 0; i < data.length; i++) {
      if (data[i].n.toLowerCase().indexOf(q) > -1 || data[i].us.toLowerCase().indexOf(q) > -1) return data[i];
    }
    return null;
  }

  function update() {
    var item = bySlug[$("ing").value], unit = $("unit").value;
    var amt = CB.parseQty($("amt").value);
    // Only offer measures we have a sourced weight for.
    Array.prototype.forEach.call($("unit").options, function (o) { o.disabled = gramsPer(item, o.value) === null; });
    if (gramsPer(item, unit) === null) {
      var first = Array.prototype.find.call($("unit").options, function (o) { return !o.disabled; });
      unit = $("unit").value = first.value;
    }
    var name = item.n.toLowerCase();
    if (isNaN(amt) || amt < 0) {
      $("res-q").textContent = "Type an amount, like 1/2 or 1.5";
      $("res-g").textContent = "–";
      $("res-extra").textContent = "";
      return;
    }
    var g = amt * gramsPer(item, unit);
    var words = UNIT_WORDS[unit][amt === 1 ? 0 : 1];
    $("res-q").textContent = $("amt").value.trim() + " " + words + " of " + name + " weighs";
    $("res-g").textContent = CB.fmtG(g);
    var extra = "That's " + (g / OZ).toFixed(1).replace(/\.0$/, "") + "oz.";
    if (item.l && (unit === "cup" || unit === "metric_cup")) extra += " By volume: " + Math.round(amt * (unit === "cup" ? US_CUP : METRIC_CUP)) + "ml.";
    $("res-extra").textContent = extra;
    $("res-link").innerHTML = '<a href="/convert/' + item.s + '/">Full table for ' + name + "</a>";
    var url = new URL(location.href);
    url.searchParams.set("i", item.s);
    history.replaceState(null, "", url);
    backToCups();
  }

  function backToCups() {
    var item = bySlug[$("ing").value], g = CB.parseQty($("grams").value);
    if (!item.u.cup || isNaN(g)) { $("cups-out").textContent = item.u.cup ? " " : "No cup weight for this one."; return; }
    var cups = g / item.u.cup;
    $("cups-out").textContent = "About " + CB.fmtFrac(cups) + " cup" + (cups > 1.1 ? "s" : "") + " (" + cups.toFixed(2) + ")";
  }

  fetch("/js/ingredients.json").then(function (r) { return r.json(); }).then(function (d) {
    data = d;
    d.forEach(function (x) { bySlug[x.s] = x; });
    var want = findItem(new URLSearchParams(location.search).get("i"));
    if (want) $("ing").value = want.s;
    ["ing", "unit"].forEach(function (id) { $(id).addEventListener("change", update); });
    $("amt").addEventListener("input", update);
    $("grams").addEventListener("input", backToCups);
    update();
  });
})();
