(function () {
  var $ = function (id) { return document.getElementById(id); };
  var meats = {}, X = null, KEY = "cb-xmas-plan";
  var DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // Same Q Guild rule as the roast timer: rounded UP to the next 5 minutes.
  function minutes(per450, extra, kg) { return Math.ceil((per450 * (kg * 1000 / 450) + extra) / 5 - 1e-9) * 5; }
  function dur(m) {
    var h = Math.floor(m / 60), mm = m % 60;
    if (!h) return mm + " min";
    return (h === 1 ? "1 hour" : h + " hours") + (mm ? " " + mm + " min" : "");
  }
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function hm(d) { return pad(d.getHours()) + ":" + pad(d.getMinutes()); }
  function dayLabel(d) { return DAYS[d.getDay()] + " " + d.getDate() + " " + MONTHS[d.getMonth()]; }
  function add(d, mins) { return new Date(d.getTime() + mins * 60000); }
  function esc(s) { var e = document.createElement("div"); e.textContent = s; return e.innerHTML; }

  function defaultDate() {
    var now = new Date(), y = now.getFullYear();
    var xmas = new Date(y, 11, 25);
    if (now > new Date(y, 11, 25, 23, 59)) y += 1;
    return y + "-12-25";
  }

  function renderDone() {
    var m = meats[$("x-meat").value], box = $("x-done");
    box.innerHTML = "";
    $("x-done-field").hidden = !m.doneness;
    if (!m.doneness) return;
    m.doneness.forEach(function (d, i) {
      var l = document.createElement("label");
      l.innerHTML = '<input type="radio" name="x-done" value="' + d.key + '"' + (i === 1 ? " checked" : "") + "> " + esc(d.label);
      box.appendChild(l);
    });
    box.querySelectorAll("input").forEach(function (r) { r.addEventListener("change", run); });
  }

  function save() {
    try {
      var sides = {};
      document.querySelectorAll(".side-row").forEach(function (r) {
        sides[r.dataset.key] = { on: r.querySelector(".s-on").checked, min: r.querySelector(".s-min").value, temp: (r.querySelector(".s-temp") || {}).value || "" };
      });
      localStorage.setItem(KEY, JSON.stringify({ meat: $("x-meat").value, weight: $("x-weight").value, eat: $("x-eat").value, date: $("x-date").value, frozen: $("x-frozen").checked, pots: $("x-pots").checked, sides: sides }));
    } catch (e) {}
  }
  function restore() {
    try {
      var s = JSON.parse(localStorage.getItem(KEY) || "null");
      if (!s) return;
      if (meats[s.meat]) $("x-meat").value = s.meat;
      $("x-weight").value = s.weight || $("x-weight").value;
      $("x-eat").value = s.eat || $("x-eat").value;
      if (s.date) $("x-date").value = s.date;
      $("x-frozen").checked = !!s.frozen;
      $("x-pots").checked = s.pots !== false;
      document.querySelectorAll(".side-row").forEach(function (r) {
        var v = (s.sides || {})[r.dataset.key];
        if (!v) return;
        r.querySelector(".s-on").checked = v.on;
        r.querySelector(".s-min").value = v.min;
        if (r.querySelector(".s-temp")) r.querySelector(".s-temp").value = v.temp;
      });
    } catch (e) {}
  }

  function run() {
    var m = meats[$("x-meat").value];
    var kg = CB.parseQty($("x-weight").value);
    var eatParts = ($("x-eat").value || "14:00").split(":");
    var dParts = ($("x-date").value || defaultDate()).split("-");
    var eat = new Date(+dParts[0], +dParts[1] - 1, +dParts[2], +eatParts[0], +eatParts[1]);
    var warn = [], ev = [];
    save();
    if (!(kg > 0)) { $("x-a").textContent = "–"; $("x-q").textContent = "Enter the weight of your roast"; $("x-tt").innerHTML = ""; $("x-warn").innerHTML = ""; return; }

    var per450 = m.per450, extra = m.extra, label = m.label.toLowerCase(), coreText = m.core ? m.core.text : "";
    if (m.doneness) {
      var key = (document.querySelector('input[name="x-done"]:checked') || {}).value || "medium";
      var d = m.doneness.filter(function (x) { return x.key === key; })[0];
      per450 = d.per450; extra = d.extra; coreText = d.core + "°C in the centre"; label = d.label.toLowerCase() + " " + label;
    }
    var cook = minutes(per450, extra, kg);
    var rest = m.rest ? (m.rest.max || m.rest.min) : 0;
    var out = add(eat, -rest), inn = add(out, -cook);

    // Oven use, for clash checks: [start, end, temperature, label]
    var ovenUse = [];
    var st = m.oven.stages;
    if (st.length > 1) {
      ovenUse.push([inn, add(inn, st[0].minutes), st[0].c, m.label]);
      ovenUse.push([add(inn, st[0].minutes), out, st[1].c, m.label]);
    } else ovenUse.push([inn, out, st[0].c, m.label]);

    if ($("x-frozen").checked) {
      var thawH = X.thaw.hours_per_kg_max * kg;
      var thawAt = add(inn, -thawH * 60);
      ev.push([thawAt, "Move the " + m.name.toLowerCase() + " from the freezer to the bottom shelf of the fridge (" + Math.round(thawH) + " hours to thaw at " + X.thaw.hours_per_kg_max + " hours per kg)", true]);
    }
    ev.push([inn, "Into a hot oven at " + st[0].c + "°C (gas mark " + st[0].gas + "). Heat the oven before this"]);
    if (st.length > 1) ev.push([add(inn, st[0].minutes), "Turn the oven down to " + st[1].c + "°C (gas mark " + st[1].gas + ")"]);
    ev.push([out, "Check it's reached " + coreText + ". If it has, take it out to rest" + (m.rest ? " for " + m.rest.text : "") + ". If not, keep cooking and push dinner back"]);

    if ($("x-pots").checked) {
      var P = X.potatoes;
      var pIn = add(eat, -P.roast_max), boil = add(pIn, -P.parboil_max);
      ev.push([boil, "Potatoes on to parboil (" + P.parboil_min + " to " + P.parboil_max + " min), then drain and shake"]);
      ev.push([pIn, "Potatoes into the oven at " + P.oven_c + "°C (gas mark " + P.gas + ") for " + P.roast_min + " to " + P.roast_max + " min"]);
      ovenUse.push([pIn, eat, P.oven_c, "Roast potatoes"]);
    }

    var missing = [];
    document.querySelectorAll(".side-row").forEach(function (r) {
      if (!r.querySelector(".s-on").checked) return;
      var name = r.querySelector("label").textContent.trim(), mins = parseInt(r.querySelector(".s-min").value, 10);
      if (!(mins > 0)) { missing.push(name); return; }
      var start = add(eat, -mins);
      if (r.dataset.where === "oven") {
        var t = parseInt(r.querySelector(".s-temp").value, 10);
        ev.push([start, name + " into the oven" + (t ? " at " + t + "°C" : "") + " (" + mins + " min)"]);
        if (t) ovenUse.push([start, eat, t, name]);
      } else {
        ev.push([start, name + " on the hob (" + mins + " min)"]);
      }
    });
    if (missing.length) warn.push("Add a cooking time for " + missing.join(", ") + ", from the pack or your recipe, to fit " + (missing.length > 1 ? "them" : "it") + " into the timetable.");

    // Two things in the oven at once at different temperatures.
    var clashes = [];
    for (var i = 0; i < ovenUse.length; i++) for (var j = i + 1; j < ovenUse.length; j++) {
      var a = ovenUse[i], b = ovenUse[j];
      if (a[3] === b[3]) continue;
      if (a[0] < b[1] && b[0] < a[1] && a[2] !== b[2]) clashes.push(a[3] + " (" + a[2] + "°C) and " + b[3].toLowerCase() + " (" + b[2] + "°C)");
    }
    if (clashes.length) warn.push("These need the oven at the same time but at different temperatures: " + clashes.join("; ") + ". Use a second oven, or settle on one temperature and check each item is done before serving.");

    ev.push([eat, "Carve and serve"]);
    ev.sort(function (p, q) { return p[0] - q[0]; });

    $("x-q").textContent = "Your " + label + " goes in at";
    $("x-a").textContent = hm(inn);
    $("x-extra").textContent = "Cooking time " + dur(cook) + (m.rest ? ", plus " + m.rest.text + " resting" : "") + ". Dinner at " + hm(eat) + " on " + dayLabel(eat) + ".";
    $("x-warn").innerHTML = warn.map(function (w) { return '<p class="caution">' + esc(w) + "</p>"; }).join("");

    var html = "", lastDay = "";
    ev.forEach(function (e) {
      var dl = dayLabel(e[0]);
      if (dl !== lastDay) { html += '<li class="tt-day">' + esc(dl) + "</li>"; lastDay = dl; }
      html += '<li><time>' + hm(e[0]) + "</time><span>" + esc(e[1]) + "</span></li>";
    });
    $("x-tt").innerHTML = html;
  }

  Promise.all([
    fetch("/js/roasts.json").then(function (r) { return r.json(); }),
    fetch("/js/christmas.json").then(function (r) { return r.json(); })
  ]).then(function (res) {
    res[0].meats.forEach(function (m) { meats[m.slug] = m; });
    X = res[1];
    $("x-date").value = defaultDate();
    restore();
    renderDone();
    $("x-meat").addEventListener("change", function () { renderDone(); run(); });
    document.querySelectorAll("#xmas input").forEach(function (i) { i.addEventListener(i.type === "checkbox" ? "change" : "input", run); });
    $("x-print").addEventListener("click", function () { window.print(); });
    run();
  });
})();
