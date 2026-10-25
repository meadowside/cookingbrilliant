(function () {
  // Same geometry as tin_area() in build.py: scale by the ratio of base areas, same depth.
  var $ = function (id) { return document.getElementById(id); };
  var NAMES = { round: "round", square: "square", rect: "rectangular" };

  function area(shape, a, b) {
    if (shape === "round") return Math.PI * (a / 2) * (a / 2);
    if (shape === "square") return a * a;
    return a * b;
  }
  function unit() { return document.querySelector('input[name="t-unit"]:checked').value; }
  function label(side) {
    var sh = $(side + "-shape").value, u = unit(), a = $(side + "-a").value.trim(), b = $(side + "-b").value.trim();
    return (sh === "rect" ? a + " x " + b + u : a + u) + " " + NAMES[sh];
  }
  function fields(side) {
    var sh = $(side + "-shape").value;
    $(side + "-a-l").textContent = sh === "round" ? "Diameter" : (sh === "square" ? "Side" : "Length");
    $(side + "-b-f").hidden = sh !== "rect";
  }

  function run() {
    fields("f"); fields("t");
    var v = {};
    ["f", "t"].forEach(function (s) {
      var sh = $(s + "-shape").value;
      v[s] = area(sh, CB.parseQty($(s + "-a").value), sh === "rect" ? CB.parseQty($(s + "-b").value) : null);
    });
    if (!(v.f > 0) || !(v.t > 0)) {
      $("t-a").textContent = "–"; $("t-extra").textContent = "Enter the size of both tins."; $("t-link").innerHTML = ""; return;
    }
    var k = v.t / v.f, ks = k.toFixed(2), pct = Math.round((k - 1) * 100);
    $("t-a").textContent = "×" + ks;
    $("t-extra").textContent = "Your " + label("t") + " tin has " +
      (pct === 0 ? "the same area as" : (pct > 0 ? pct + "% more area than" : -pct + "% less area than")) +
      " the " + label("f") + " tin. 100g in the recipe becomes " + CB.fmtG(100 * k) + "g.";
    $("t-link").innerHTML = '<a href="/recipe-scaler/?x=' + ks + '">Scale your recipe by ×' + ks + "</a>";
  }

  document.querySelectorAll("#tin input, #tin select").forEach(function (el) {
    el.addEventListener(el.tagName === "SELECT" || el.type === "radio" ? "change" : "input", run);
  });
  run();
})();
