"use strict";

/* Run the REAL generated map script for one independent Codex counterexample.
 * No mock of metricColor or draw is allowed. This minimal DOM checks the
 * resulting SVG attributes and the evidence detail/legend shown to users.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const [htmlPath, expectedDash, expectedScreen] = process.argv.slice(2);
assert.ok(htmlPath && expectedDash && expectedScreen);
const html = fs.readFileSync(htmlPath, "utf8");
const evidenceMatch = html.match(/<script id="evidence" type="application\/json">([\s\S]*?)<\/script>/);
const jsMatch = html.match(/<script>\s*("use strict";[\s\S]*?)<\/script>/);
assert.ok(evidenceMatch && jsMatch, "executable offline HTML must contain source data and code");
const data = JSON.parse(evidenceMatch[1]);
class Element {
  constructor(tag) {
    this.tag = tag; this.attrs = {}; this.children = [];
    this.handlers = {}; this.dataset = {}; this.checked = true;
    this.textContent = "";
  }
  setAttribute(k, v) {this.attrs[k] = String(v);}
  append(...items) {this.children.push(...items);}
  replaceChildren(...items) {this.children = [...items];}
  addEventListener(event, handler) {this.handlers[event] = handler;}
  getBoundingClientRect() {return {width: 1000, height: 700};}
  setPointerCapture() {}
}
const elements = {
  evidence: {textContent: evidenceMatch[1]},
  map: new Element("svg"), status: new Element("span"),
  detail: new Element("p"), reset: new Element("button"),
  "metric-mode": new Element("select"),
  "metric-legend": new Element("p"), "metric-screening": new Element("p"),
};
const controls = ["target_area", "target_segment", "target_metric_edge",
                  "observed_outside", "gap_endpoint"].map(layer => {
  const input = new Element("input"); input.dataset.layer = layer; return input;
});
const document = {
  getElementById: id => {
    assert.ok(elements[id], "missing element " + id); return elements[id];
  },
  createElementNS: (ns, tag) => {
    assert.equal(ns, "http://www.w3.org/2000/svg"); return new Element(tag);
  },
  querySelectorAll: selector => {
    assert.equal(selector, "[data-layer]"); return controls;
  },
};
vm.runInNewContext(jsMatch[1], {document, console}, {timeout: 5000});
function target() {
  return elements.map.children[0].children.filter(g => g.attrs["data-layer"] === "target_metric_edge");
}
const original = target();
assert.equal(original.length, 1, "one observed parent-edge clip expected");
const edge = data.features.find(f => f.properties.layer === "target_metric_edge");
assert.equal(edge.properties.speed_screen_result, expectedScreen,
             "source screening state and expected test witness must agree");
const rendered = original[0].children[0];
assert.equal(rendered.tag, "path");
if (expectedDash === "solid") {
  assert.equal(rendered.attrs["stroke-dasharray"], undefined,
               "only verified M2B parent-edge pass may draw solid");
} else {
  assert.equal(rendered.attrs["stroke-dasharray"], expectedDash,
               "known screening uncertainty must NOT look like verified pass");
}
if (expectedScreen === "unavailable") {
  assert.equal(rendered.attrs.stroke, "#94a3b8",
               "invalid metric must not acquire a blue speed bin");
} else {
  assert.notEqual(rendered.attrs.stroke, "#94a3b8",
                  "numerically valid speed retains bounded-color meaning");
}
assert.ok(elements["metric-legend"].textContent.includes("parent edge") ||
          elements["metric-legend"].textContent.includes("parent-edge"),
          "legend must distinguish parent screening from clipped speed");
assert.ok(elements["metric-legend"].textContent.includes("proportionally"),
          "legend must disclose clipped-time allocation");
original[0].handlers.click();
assert.ok(elements.detail.textContent.includes('"speed_screen_result"'),
          "edge details must show exact screening outcome");
assert.ok(elements.detail.textContent.includes('"speed_screen_reason"'),
          "edge details must show the actual M2B decision reason");
const before = rendered.attrs.stroke;
elements["metric-mode"].value = "pace_s_per_km";
elements["metric-mode"].handlers.change();
const after = target()[0].children[0];
assert.equal(after.attrs.stroke, before, "mode change cannot falsify numeric speed bin");
assert.equal(after.attrs["stroke-dasharray"], rendered.attrs["stroke-dasharray"],
             "mode change cannot remove screening uncertainty");
assert.ok(elements["metric-legend"].textContent.includes("min/km"));
console.log("M2 Codex P1 screening DOM: independent actual SVG rendering / provenance / pace mode PASS");
