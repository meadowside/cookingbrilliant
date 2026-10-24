// Shared number helpers for the browser tools. Loaded as a classic script.
(function (w) {
  var VULGAR = { "¼": 0.25, "½": 0.5, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875 };

  // Parse "1", "1.5", "1/2", "1 1/2", "1½", "¾". Returns NaN if it can't.
  function parseQty(s) {
    s = String(s).trim().replace(/,/g, ".");
    if (!s) return NaN;
    var total = 0, m;
    var v = s.match(/[¼½¾⅓⅔⅛⅜⅝⅞]/);
    if (v) { total += VULGAR[v[0]]; s = s.replace(v[0], " ").trim(); if (!s) return total; }
    if ((m = s.match(/^(\d+)\s+(\d+)\/(\d+)$/))) return total + (+m[1]) + (+m[2]) / (+m[3]);
    if ((m = s.match(/^(\d+)\/(\d+)$/))) return total + (+m[1]) / (+m[2]);
    if ((m = s.match(/^\d+(\.\d+)?$/))) return total + parseFloat(s);
    return NaN;
  }

  // Display weights the same way the static pages do.
  function fmtG(x) {
    if (x < 10) return String(Math.round(x * 10) / 10);
    return Math.round(x).toLocaleString("en-GB");
  }

  // Nearest kitchen fraction (quarters and thirds) for cups and spoons.
  var FRACS = [[0, ""], [0.25, "¼"], [1 / 3, "⅓"], [0.5, "½"], [2 / 3, "⅔"], [0.75, "¾"], [1, ""]];
  function fmtFrac(x) {
    var whole = Math.floor(x), part = x - whole, best = FRACS[0];
    for (var i = 0; i < FRACS.length; i++) if (Math.abs(FRACS[i][0] - part) < Math.abs(best[0] - part)) best = FRACS[i];
    if (best[0] === 1) { whole += 1; best = FRACS[0]; }
    var s = (whole ? String(whole) : "") + best[1];
    return s || "0";
  }

  w.CB = { parseQty: parseQty, fmtG: fmtG, fmtFrac: fmtFrac };
})(window);
