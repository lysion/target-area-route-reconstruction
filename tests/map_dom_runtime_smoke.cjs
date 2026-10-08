"use strict";

/* Execute generated map JavaScript in a minimal DOM test double.
 * This tests actual event handlers and SVG children, rather than merely
 * searching HTML source for control labels. No browser or network needed.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync(process.argv[2], "utf8");
const evidence = html.match(/<script id="evidence" type="application\/json">([\s\S]*?)<\/script>/);
const match = html.match(/<script>\s*("use strict";[\s\S]*?)<\/script>/);
assert.ok(evidence && match, "HTML must contain data JSON and executable map script");
assert.ok(!/<(?:link|iframe)\b|<script\b[^>]*src=/i.test(html), "map must be self-contained");

class Element {
    constructor(tag) {
        this.tag = tag; this.attrs = {}; this.children = [];
        this.handlers = {}; this.dataset = {}; this.checked = true;
        this.textContent = ""; this.onclick = null;
    }
    setAttribute(name, value) { this.attrs[name] = String(value); }
    append(...els) { this.children.push(...els); }
    replaceChildren(...els) { this.children = [...els]; }
    addEventListener(event, callback) { this.handlers[event] = callback; }
    getBoundingClientRect() { return {width: 1000, height: 700}; }
    setPointerCapture() {}
}
const svg = new Element("svg"), details = new Element("p");
const elements = {
    evidence: {textContent: evidence[1]},
    map: svg,
    status: new Element("span"),
    detail: details,
    reset: new Element("button"),
    "metric-mode": new Element("select"),
};
const checkboxes = ["target_area", "target_segment", "target_metric_edge", "observed_outside", "gap_endpoint"]
    .map(layer => {const checkbox = new Element("input"); checkbox.dataset.layer = layer; return checkbox;});
const document = {
    getElementById(id) {assert.ok(elements[id], "Missing DOM node " + id); return elements[id];},
    createElementNS(ns, tag) {assert.equal(ns, "http://www.w3.org/2000/svg"); return new Element(tag);},
    querySelectorAll(selector) {assert.equal(selector, "[data-layer]"); return checkboxes;},
};
vm.runInNewContext(match[1], {document, console}, {timeout: 5000});

function groups() {return svg.children[0].children;}
const layers = groups().map(g => g.attrs["data-layer"]);
assert.equal(layers.filter(x => x === "target_area").length, 1);
assert.equal(layers.filter(x => x === "target_segment").length, 2);
assert.equal(layers.filter(x => x === "gap_endpoint").length, 2);
assert.ok(groups().filter(g => g.attrs["data-layer"] === "gap_endpoint")
    .every(g => g.children.length === 1 && g.children[0].tag === "circle"));
assert.ok(groups().filter(g => g.attrs["data-layer"] === "target_segment")
    .every(g => g.children.length === 1 && g.children[0].tag === "path"));
assert.ok(elements.status.textContent.includes("unknown"));
assert.ok(elements.status.textContent.includes("incomplete"));

const segment = groups().find(g => g.attrs["data-layer"] === "target_segment");
segment.handlers.click();
assert.ok(details.textContent.includes('"layer": "target_segment"'));

const gap = checkboxes.find(c => c.dataset.layer === "gap_endpoint");
gap.checked = false; gap.handlers.change();
assert.equal(groups().filter(g => g.attrs["data-layer"] === "gap_endpoint").length, 0);
gap.checked = true; gap.handlers.change();
assert.equal(groups().filter(g => g.attrs["data-layer"] === "gap_endpoint").length, 2);

const original = svg.attrs.viewBox;
svg.handlers.wheel({deltaY: -40, preventDefault() {}});
assert.notEqual(svg.attrs.viewBox, original, "wheel zoom must change viewport");
elements.reset.onclick();
assert.equal(svg.attrs.viewBox, original, "reset must restore initial viewport");
svg.handlers.pointerdown({clientX: 30, clientY: 40, pointerId: 1});
svg.handlers.pointermove({clientX: 50, clientY: 45});
assert.notEqual(svg.attrs.viewBox, original, "drag must pan viewport");
svg.handlers.pointerup();
elements.reset.onclick();
assert.equal(svg.attrs.viewBox, original);

console.log("M2E DOM runtime: actual SVG lines/points, layer visibility, click, zoom, pan, reset PASS");
