(function () {
  var Q = "(\\d+\\s+\\d+\\/\\d+|\\d+\\/\\d+|\\d+(?:[.,]\\d+)?\\s?[¼½¾⅓⅔⅛]?|[¼½¾⅓⅔⅛])";
  var UNIT = "(kg|g|grams?|mg|ml|millilitres?|milliliters?|l|litres?|liters?|cl|tsp|teaspoons?|tbsp|tbs|tablespoons?|cups?|oz|ounces?|lbs?|pounds?|pints?|fl\\s?oz|sticks?|pinch(?:es)?|cloves?|tins?|cans?|slices?)?";
  var LINE = new RegExp("^\\s*" + Q + "(?:\\s*(?:-|–|to)\\s*" + Q + ")?\\s*" + UNIT + "\\b(.*)$", "i");

  var METRIC = /^(kg|g|grams?|mg|ml|millilitres?|milliliters?|l|litres?|liters?|cl)$/i;
  var SPOONCUP = /^(tsp|teaspoons?|tbsp|tbs|tablespoons?|cups?|sticks?)$/i;
  var IMPERIAL = /^(oz|ounces?|lbs?|pounds?|pints?|fl\s?oz)$/i;

  function roundMetric(x, unit) {
    if (/^(kg|l|litres?|liters?)$/i.test(unit)) return String(Math.round(x * 100) / 100);
    if (x >= 100) return String(Math.round(x / 5) * 5);
    if (x >= 10) return String(Math.round(x));
    return String(Math.round(x * 2) / 2);
  }

  function fmt(x, unit) {
    if (!unit) return CB.fmtFrac(x);
    if (METRIC.test(unit)) return roundMetric(x, unit);
    if (SPOONCUP.test(unit) || IMPERIAL.test(unit)) return CB.fmtFrac(x);
    return CB.fmtFrac(x);
  }

  function countHint(x, rest) {
    var whole = Math.round(x);
    if (Math.abs(x - whole) < 0.13) return "";
    if (/egg/i.test(rest)) return "Use " + Math.floor(x) + " eggs plus part of another: beat it and add " + CB.fmtFrac(x - Math.floor(x)) + " of it, or round to " + whole + ".";
    return "Round to " + Math.max(1, whole) + " if it can't be split.";
  }

  function scaleLine(line, k) {
    var m = line.match(LINE);
    if (!m || !line.trim()) return { text: line, changed: false };
    var a = CB.parseQty(m[1].replace(/(\d)\s?([¼½¾⅓⅔⅛])/, "$1 $2")), b = m[2] ? CB.parseQty(m[2]) : null;
    if (isNaN(a)) return { text: line, changed: false };
    var unit = (m[3] || "").trim(), rest = m[4] || "";
    if (rest && /^[A-Za-z(]/.test(rest)) rest = " " + rest;
    // "400g tin tomatoes": the tin size stays put, the number of tins changes.
    if (unit && METRIC.test(unit) && /^\s*(tins?|cans?|jars?|packs?|packets?|cartons?|bags?)\b/i.test(rest)) {
      return { text: CB.fmtFrac(k) + " x " + m[1].trim() + unit + rest, changed: true, hint: countHint(k, rest) };
    }
    var lo = a * k, hi = b !== null && !isNaN(b) ? b * k : null;
    // Small kilos and litres read better as grams and millilitres.
    if (/^kg$/i.test(unit) && Math.max(lo, hi || 0) < 1) { lo *= 1000; hi = hi && hi * 1000; unit = "g"; }
    if (/^(l|litres?|liters?)$/i.test(unit) && Math.max(lo, hi || 0) < 1) { lo *= 1000; hi = hi && hi * 1000; unit = "ml"; }
    var sa = fmt(lo, unit), sb = hi !== null ? "–" + fmt(hi, unit) : "";
    var joiner = unit && METRIC.test(unit) && unit.length <= 2 ? "" : (unit ? " " : "");
    var text = sa + sb + joiner + unit + rest;
    var hint = !unit ? countHint(lo, rest) : "";
    return { text: text, changed: true, hint: hint };
  }

  var $ = function (id) { return document.getElementById(id); };
  function run() {
    var from = CB.parseQty($("from").value), to = CB.parseQty($("to").value), out = $("scaled");
    out.innerHTML = "";
    if (!(from > 0) || !(to > 0)) { $("scale-note").textContent = "Enter both serving numbers to scale."; return; }
    var k = to / from;
    $("scale-note").textContent = "Multiplying everything by " + (Math.round(k * 100) / 100) + ".";
    $("recipe").value.split(/\r?\n/).forEach(function (line) {
      if (!line.trim()) return;
      var r = scaleLine(line, k), li = document.createElement("li");
      li.textContent = r.text;
      if (r.hint) { var s = document.createElement("span"); s.className = "source"; s.textContent = " " + r.hint; li.appendChild(s); }
      out.appendChild(li);
    });
  }
  ["from", "to", "recipe"].forEach(function (id) { $(id).addEventListener("input", run); });
  // ?x=1.32 from the cake tin converter: scale by a factor instead of servings.
  var x = parseFloat(new URLSearchParams(location.search).get("x"));
  if (x > 0 && x < 20) {
    $("from").value = "1"; $("to").value = String(x);
    var n = document.createElement("p"); n.className = "note";
    n.textContent = "Set to ×" + x + " for your new tin. Paste your recipe below.";
    $("from").closest(".tool").before(n);
  }
  run();
})();
