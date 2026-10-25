(function () {
  var $ = function (id) { return document.getElementById(id); };
  var T = null, KEY = "cb-tg-plan";
  var DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function hours(m) { // 165 -> "2¾ hours", as USDA writes them
    var q = Math.round(m / 15), whole = Math.floor(q / 4), frac = q % 4;
    return (whole ? whole : "") + ["", "¼", "½", "¾"][frac] + (q === 4 ? " hour" : " hours");
  }
  function hourRange(a, b) { return hours(a).replace(/ hours?$/, "") + " to " + hours(b); }
  function hm(d) {
    var h = d.getHours(), m = d.getMinutes(), ap = h < 12 ? "am" : "pm";
    h = h % 12 || 12;
    return h + ":" + (m < 10 ? "0" : "") + m + " " + ap;
  }
  function dayLabel(d) { return DAYS[d.getDay()] + " " + MONTHS[d.getMonth()] + " " + d.getDate(); }
  function add(d, mins) { return new Date(d.getTime() + mins * 60000); }
  function esc(s) { var e = document.createElement("div"); e.textContent = s; return e.innerHTML; }

  // Thanksgiving is the fourth Thursday of November. Once it's passed, plan for next year.
  function thanksgiving(y) {
    var dow = new Date(y, 10, 1).getDay();
    return new Date(y, 10, 1 + ((4 - dow + 7) % 7) + 21);
  }
  function defaultDate(now) {
    now = now || new Date();
    var d = thanksgiving(now.getFullYear());
    if (now > new Date(d.getFullYear(), 10, d.getDate(), 23, 59)) d = thanksgiving(now.getFullYear() + 1);
    var m = d.getMonth() + 1;
    return d.getFullYear() + "-" + (m < 10 ? "0" : "") + m + "-" + (d.getDate() < 10 ? "0" : "") + d.getDate();
  }

  // Same rule as build.py turkey_range(): every USDA row that includes the weight.
  function range(lb, kind) {
    var all = T[kind].filter(function (r) { return r.lo <= lb && lb <= r.hi; });
    var rows = all.filter(function (r) { return !r.breast; });
    if (!rows.length) rows = all;
    if (!rows.length) return null;
    return { min: rows[0].min, max: rows[rows.length - 1].max, breast: !!rows[0].breast };
  }

  function save() {
    try {
      var sides = {};
      document.querySelectorAll(".side-row").forEach(function (r) {
        sides[r.dataset.key] = { on: r.querySelector(".s-on").checked, min: r.querySelector(".s-min").value, temp: (r.querySelector(".s-temp") || {}).value || "" };
      });
      localStorage.setItem(KEY, JSON.stringify({ weight: $("t-weight").value, eat: $("t-eat").value, date: $("t-date").value, stuffed: $("t-stuffed").checked, thaw: thawMode(), sides: sides }));
    } catch (e) {}
  }
  function restore() {
    try {
      var s = JSON.parse(localStorage.getItem(KEY) || "null");
      if (!s) return;
      $("t-weight").value = s.weight || $("t-weight").value;
      $("t-eat").value = s.eat || $("t-eat").value;
      if (s.date) $("t-date").value = s.date;
      $("t-stuffed").checked = !!s.stuffed;
      var r = document.querySelector('input[name="t-thaw"][value="' + s.thaw + '"]');
      if (r) r.checked = true;
      document.querySelectorAll(".side-row").forEach(function (row) {
        var v = (s.sides || {})[row.dataset.key];
        if (!v) return;
        row.querySelector(".s-on").checked = v.on;
        row.querySelector(".s-min").value = v.min;
        if (row.querySelector(".s-temp")) row.querySelector(".s-temp").value = v.temp;
      });
    } catch (e) {}
  }
  function thawMode() { return (document.querySelector('input[name="t-thaw"]:checked') || {}).value || "no"; }

  function blank(q) { $("t-a").textContent = "–"; $("t-q").textContent = q; $("t-extra").textContent = ""; $("t-tt").innerHTML = ""; }

  function run() {
    save();
    var lb = CB.parseQty($("t-weight").value), stuffed = $("t-stuffed").checked, kind = stuffed ? "stuffed" : "unstuffed";
    var eatParts = ($("t-eat").value || "16:00").split(":");
    var dParts = ($("t-date").value || defaultDate()).split("-");
    var eat = new Date(+dParts[0], +dParts[1] - 1, +dParts[2], +eatParts[0], +eatParts[1]);
    var warn = [], ev = [];
    $("t-warn").innerHTML = "";
    if (!(lb > 0)) return blank("Enter your turkey's weight in pounds");
    var r = range(lb, kind);
    if (!r) {
      var lo = T[kind][0].lo, hi = T[kind][T[kind].length - 1].hi;
      blank("USDA's " + kind + " chart covers " + lo + " to " + hi + " lb");
      $("t-warn").innerHTML = '<p class="caution">There\'s no USDA time for a ' + esc(String(lb)) + " lb " + kind + " turkey, so we won't guess one. Check the pack or ask the USDA Meat and Poultry Hotline.</p>";
      return;
    }
    if (r.breast) warn.push("USDA's row for this weight is for a turkey breast. A whole bird this small may cook differently, so check it early with a thermometer.");

    var rest = T.rest_min, out = add(eat, -rest), inn = add(out, -r.max), check = add(inn, r.min);
    var mode = thawMode();
    if (mode === "fridge") {
      var days = lb / T.thaw.fridge_lb_per_day_min;
      ev.push([add(inn, -days * 24 * 60), "Move the turkey into the fridge to thaw, in its wrapper on a tray (24 hours per " + T.thaw.fridge_lb_per_day_min + " to " + T.thaw.fridge_lb_per_day_max + " lb). Once thawed it keeps 1 to 2 days, so starting early is fine"]);
    } else if (mode === "water") {
      var wm = Math.ceil(lb * T.thaw.water_min_per_lb);
      ev.push([add(inn, -wm), "Start thawing the turkey in cold water, wrapped tight. Change the water every 30 minutes (about " + T.thaw.water_min_per_lb + " min per lb). Cook it as soon as it's thawed"]);
    }
    ev.push([inn, "Turkey into the oven at " + T.oven_f + "°F, on a rack in a shallow pan. Heat the oven first" + (mode !== "no" ? ". Take the giblets out of the cavities first and cook them separately" : "") + (stuffed ? ". Stuff it loosely just before it goes in" : "")]);
    ev.push([check, "Start checking with a thermometer. It's done at " + T.safe_f + "°F in the thigh, wing and thickest part of the breast" + (stuffed ? ", and the center of the stuffing must reach " + T.safe_f + "°F too" : "")]);
    ev.push([out, "Out of the oven to stand for " + rest + " minutes, once it's reached " + T.safe_f + "°F. If it hasn't, keep cooking and push dinner back"]);
    var ovenUse = [[inn, out, T.oven_f, "Turkey"]];

    var missing = [];
    document.querySelectorAll(".side-row").forEach(function (row) {
      if (!row.querySelector(".s-on").checked) return;
      var name = row.querySelector("label").textContent.trim(), mins = parseInt(row.querySelector(".s-min").value, 10);
      if (!(mins > 0)) { missing.push(name); return; }
      var start = add(eat, -mins);
      if (row.dataset.where === "oven") {
        var t = parseInt(row.querySelector(".s-temp").value, 10);
        ev.push([start, name + " into the oven" + (t ? " at " + t + "°F" : "") + " (" + mins + " min)"]);
        if (t) ovenUse.push([start, eat, t, name]);
      } else ev.push([start, name + " on the stove (" + mins + " min)"]);
    });
    if (missing.length) warn.push("Add a cooking time for " + missing.join(", ") + ", from your recipe or the pack, to fit " + (missing.length > 1 ? "them" : "it") + " into the timetable.");

    var clashes = [];
    for (var i = 0; i < ovenUse.length; i++) for (var j = i + 1; j < ovenUse.length; j++) {
      var a = ovenUse[i], b = ovenUse[j];
      if (a[0] < b[1] && b[0] < a[1] && a[2] !== b[2]) clashes.push(a[3] + " (" + a[2] + "°F) and " + b[3].toLowerCase() + " (" + b[2] + "°F)");
    }
    if (clashes.length) warn.push("These need the oven at the same time but at different temperatures: " + clashes.join("; ") + ". Use a second oven, or settle on one temperature and check each dish is done before serving.");

    ev.push([eat, "Carve and serve"]);
    ev.sort(function (p, q) { return p[0] - q[0]; });

    $("t-q").textContent = "Your " + lb + " lb " + kind + " turkey goes in at";
    $("t-a").textContent = hm(inn);
    $("t-extra").textContent = "USDA allows " + hourRange(r.min, r.max) + " at " + T.oven_f + "°F, plus " + rest + " minutes standing. Dinner at " + hm(eat) + " on " + dayLabel(eat) + ".";
    $("t-warn").innerHTML = warn.map(function (w) { return '<p class="caution">' + esc(w) + "</p>"; }).join("");

    var html = "", lastDay = "";
    ev.forEach(function (e) {
      var dl = dayLabel(e[0]);
      if (dl !== lastDay) { html += '<li class="tt-day">' + esc(dl) + "</li>"; lastDay = dl; }
      html += "<li><time>" + hm(e[0]) + "</time><span>" + esc(e[1]) + "</span></li>";
    });
    $("t-tt").innerHTML = html;
  }

  window.CB_TG = { defaultDate: defaultDate, range: function (lb, k) { return range(lb, k); } };
  fetch("/js/thanksgiving.json").then(function (r) { return r.json(); }).then(function (d) {
    T = d;
    $("t-date").value = defaultDate();
    restore();
    document.querySelectorAll("#tg input").forEach(function (i) { i.addEventListener(i.type === "checkbox" || i.type === "radio" ? "change" : "input", run); });
    $("t-print").addEventListener("click", function () { window.print(); });
    run();
  });
})();
