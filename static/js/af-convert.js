// Oven to air fryer: Ninja's 25% packet rule, plus the range real packs use.
(function () {
  var minIn = document.getElementById("ov-min"), tempIn = document.getElementById("ov-temp"), out = document.getElementById("conv-out");
  var data = null;

  function run() {
    var m = parseFloat(minIn.value), t = parseFloat(tempIn.value);
    if (!data) return;
    if (isNaN(m) || m <= 0) { out.textContent = "Type the oven time from the pack."; return; }
    var ninja = Math.round(m * data.packet);
    var lo = Math.round(m * data.cmp.q1), med = Math.round(m * data.cmp.med), hi = Math.round(m * data.cmp.q3);
    var lines = [
      "Ninja's rule: about " + ninja + " min. Start checking at " + Math.max(1, ninja - 2) + " min.",
      "What packs do: scaled to " + m + " min in the oven, half the packs we checked land between " + lo + " and " + hi + " min, with the middle at about " + med + " min."
    ];
    if (!isNaN(t)) lines.push("Temperature: most packs we checked use the fan oven setting (" + t + "°C here) or turn it down a little. Cook a single layer and check early.");
    lines.push("Make sure it's piping hot all the way through before eating.");
    out.textContent = lines.join("\n");
  }

  fetch("/js/airfryer.json").then(function (r) { return r.json(); }).then(function (d) { data = d; run(); });
  minIn.addEventListener("input", run);
  tempIn.addEventListener("input", run);
})();
