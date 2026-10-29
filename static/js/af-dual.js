// Dual basket timer: when to start each basket so both finish together.
(function () {
  var out = document.getElementById("dual-out"), ready = document.getElementById("ready");
  var foods = {};

  function mins(i) {
    var v = parseFloat(document.getElementById("m" + i).value);
    return isNaN(v) || v <= 0 ? null : v;
  }

  function name(i) {
    var s = document.getElementById("f" + i);
    return s.value && foods[s.value] ? foods[s.value].n : "Basket " + i;
  }

  function clock(d) {
    return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }

  function run() {
    var a = mins(1), b = mins(2);
    if (a === null || b === null) { out.textContent = "Choose two foods or type two times."; return; }
    var first = a >= b ? 1 : 2, second = first === 1 ? 2 : 1;
    var long = Math.max(a, b), short = Math.min(a, b), gap = long - short;
    var lines = [];
    if (gap === 0) {
      lines.push("Start both baskets together. Both take " + long + " minutes.");
    } else {
      lines.push("1. Start " + name(first) + " (" + long + " min).");
      lines.push("2. After " + gap + " min, when it has " + short + " min left, start " + name(second) + ".");
      lines.push("3. Both finish " + long + " min after you started.");
    }
    if (ready.value) {
      var p = ready.value.split(":"), end = new Date();
      end.setHours(+p[0], +p[1], 0, 0);
      var s1 = new Date(end - long * 60000), s2 = new Date(end - short * 60000);
      lines.push("");
      lines.push("Ready at " + clock(end) + ": start " + name(first) + " at " + clock(s1) + (gap ? " and " + name(second) + " at " + clock(s2) + "." : "."));
    }
    out.textContent = lines.join("\n");
  }

  function pick(i) {
    var s = document.getElementById("f" + i), f = foods[s.value], t = document.getElementById("t" + i);
    if (!f) { t.textContent = ""; run(); return; }
    document.getElementById("m" + i).value = f.b;
    t.innerHTML = f.t + "°C, " + (f.a === f.b ? f.a : f.a + " to " + f.b) + " min. <a href=\"/air-fryer/" + f.s + "/\">Details and source</a>";
    run();
  }

  fetch("/js/airfryer.json").then(function (r) { return r.json(); }).then(function (d) {
    d.foods.forEach(function (f) { foods[f.s] = f; });
  });
  [1, 2].forEach(function (i) {
    document.getElementById("f" + i).addEventListener("change", function () { pick(i); });
    document.getElementById("m" + i).addEventListener("input", run);
  });
  ready.addEventListener("input", run);
})();
