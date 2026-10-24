(function () {
  var LB = 2.20462;
  var $ = function (id) { return document.getElementById(id); };
  var meats = {}, order = [];

  // Q Guild rule, rounded UP to the next 5 minutes. Must match roast_minutes() in build.py.
  function minutes(per450, extra, kg) {
    var raw = per450 * (kg * 1000 / 450) + extra;
    return Math.ceil(raw / 5 - 1e-9) * 5;
  }
  function dur(m) {
    var h = Math.floor(m / 60), mm = m % 60;
    if (!h) return mm + " min";
    var hs = h === 1 ? "1 hour" : h + " hours";
    return mm ? hs + " " + mm + " min" : hs;
  }
  function ovenText(m) {
    return m.oven.stages.map(function (s) {
      return s.c + "°C (" + s.f + "°F, gas mark " + s.gas + ")" + (s.note ? " " + s.note : "");
    }).join(", then ");
  }
  function clock(totalMin) {
    var t = ((totalMin % 1440) + 1440) % 1440, h = Math.floor(t / 60), mm = t % 60;
    return (h < 10 ? "0" : "") + h + ":" + (mm < 10 ? "0" : "") + mm;
  }
  function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

  function renderDoneness(m) {
    var box = $("doneness");
    box.innerHTML = "";
    if (!m.doneness) { $("done-field").hidden = true; return; }
    $("done-field").hidden = false;
    m.doneness.forEach(function (d, i) {
      var l = document.createElement("label");
      l.innerHTML = '<input type="radio" name="done" value="' + d.key + '"' + (i === 1 ? " checked" : "") + "> " + esc(d.label);
      box.appendChild(l);
    });
    box.querySelectorAll("input").forEach(function (r) { r.addEventListener("change", run); });
  }

  function onMeat() {
    var m = meats[$("meat").value];
    renderDoneness(m);
    $("rolled-field").hidden = m.cooked_through;
    $("rolled").checked = false;
    run();
  }

  function run() {
    var m = meats[$("meat").value];
    var w = CB.parseQty($("weight").value);
    var kg = $("wunit").value === "lb" ? w / LB : w;
    var warn = [], rolled = !$("rolled-field").hidden && $("rolled").checked;
    $("r-plan").innerHTML = "";
    if (!(kg > 0)) {
      $("r-q").textContent = "Enter the weight, like 2.5";
      $("r-a").textContent = "–";
      $("r-extra").textContent = "";
      $("r-warn").innerHTML = "";
      return;
    }

    var per450 = m.per450, extra = m.extra, coreText = m.core ? m.core.text : "", label = m.label.toLowerCase();
    if (m.doneness) {
      var radios = document.querySelectorAll('input[name="done"]');
      radios.forEach(function (r) { r.disabled = rolled && r.value !== "well"; if (r.disabled && r.checked) { r.checked = false; } });
      if (rolled) document.querySelector('input[name="done"][value="well"]').checked = true;
      var key = (document.querySelector('input[name="done"]:checked') || {}).value || "medium";
      var d = m.doneness.filter(function (x) { return x.key === key; })[0];
      per450 = d.per450; extra = d.extra; coreText = d.core + "°C in the centre";
      label = d.label.toLowerCase() + " " + label;
    }
    if (rolled) {
      warn.push("Rolled and stuffed joints must be cooked all the way through, so " + (m.doneness ? "only well done is safe." : "cook it until the centre is at least 75°C, not pink."));
      if (!m.doneness) coreText = "at least 75°C in the centre";
    }
    if (kg < m.range[0] || kg > m.range[1]) {
      warn.push("That's an unusual weight for " + m.label.toLowerCase() + ", so double-check it. Times for very small or very large joints are least reliable.");
    }

    var mins = minutes(per450, extra, kg);
    var wLabel = $("weight").value.trim() + $("wunit").value;
    $("r-q").textContent = "A " + wLabel + " " + label + " needs about";
    $("r-a").textContent = dur(mins);
    var rest = m.rest ? (m.rest.max || m.rest.min) : 0;
    $("r-extra").textContent = "Oven: " + ovenText(m) + "." + (m.rest ? " Then rest for " + m.rest.text + "." : "");
    $("r-warn").innerHTML = warn.map(function (t) { return '<p class="caution">' + esc(t) + "</p>"; }).join("");

    var check = coreText ? "<p>It's done when it reaches <strong>" + esc(coreText) + "</strong>. Check the thickest part with a thermometer before you take it out.</p>" : "";
    var serve = $("serve").value;
    if (serve) {
      var p = serve.split(":"), eat = (+p[0]) * 60 + (+p[1]);
      var out = eat - rest, inn = out - mins;
      var steps = ["<li><strong>" + clock(inn) + "</strong>: into the hot oven at " + m.oven.stages[0].c + "°C</li>"];
      if (m.oven.stages.length > 1) steps.push("<li><strong>" + clock(inn + m.oven.stages[0].minutes) + "</strong>: turn down to " + m.oven.stages[1].c + "°C</li>");
      steps.push("<li><strong>" + clock(out) + "</strong>: check the temperature. Out to rest if it's there</li>");
      steps.push("<li><strong>" + clock(eat) + "</strong>: carve and eat</li>");
      $("r-plan").innerHTML = "<h2>Your timings</h2><ol class=\"steps\">" + steps.join("") + "</ol>" +
        "<p class=\"source\">Heat the oven before the first step. If it's not up to temperature at the check, give it longer and push the meal back.</p>" + check;
    } else {
      $("r-plan").innerHTML = check;
    }
    $("r-link").innerHTML = '<a href="/roast-timer/' + m.slug + '/">Full guide to ' + esc(m.label.toLowerCase()) + "</a>";
  }

  fetch("/js/roasts.json").then(function (r) { return r.json(); }).then(function (data) {
    data.meats.forEach(function (m) { meats[m.slug] = m; order.push(m.slug); });
    var q = new URLSearchParams(location.search);
    if (meats[q.get("m")]) $("meat").value = q.get("m");
    if (q.get("w") && !isNaN(parseFloat(q.get("w")))) $("weight").value = q.get("w");
    $("meat").addEventListener("change", onMeat);
    ["weight", "serve"].forEach(function (id) { $(id).addEventListener("input", run); });
    ["wunit", "rolled"].forEach(function (id) { $(id).addEventListener("change", run); });
    onMeat();
  });
})();
