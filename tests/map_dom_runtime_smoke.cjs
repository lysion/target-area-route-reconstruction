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
    "metric-legend": new Element("p"),
    "metric-screening": new Element("p"),
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
const metricInfo = JSON.parse(evidence[1]).metadata?.temporal_overlay;
if (metricInfo) {
    const overlays = groups().filter(g => g.attrs["data-layer"] === "target_metric_edge");
    assert.equal(overlays.length, 2, "two separately observed metric edges");
    assert.ok(overlays.every(g => g.children.length === 1 && g.children[0].tag === "path"));
    const strokes = overlays.map(g => g.children[0].attrs.stroke);
    assert.ok(strokes.includes("#94a3b8"), "missing timestamp must render neutral");
    assert.ok(strokes.some(v => v !== "#94a3b8"), "valid timestamp must render metric color");
    const derivedColored=groups().filter(g=>g.attrs["data-layer"]==="target_metric_edge" &&
        g.children[0].attrs.stroke!=="#94a3b8");
    if(metricInfo.speed_screen==="not_screened"){
        assert.ok(derivedColored.every(g=>g.children[0].attrs["stroke-dasharray"]==="7 3"),
            "unscreened numeric speed must be BLUE DASHED, not look like certified speed");
    }else if(metricInfo.speed_screen==="explicit_m2b_policy_enabled"){
        assert.ok(derivedColored.every(g=>g.children[0].attrs["stroke-dasharray"]===undefined),
            "explicit-screened numerical speed should use SOLID line");
    }

    assert.ok(strokes.includes("#1d4ed8")||strokes.includes("#93c5fd")||
        strokes.includes("#60a5fa")||strokes.includes("#bfdbfe")||
        strokes.includes("#2563eb"), "valid edge uses a documented blue bin");
    assert.ok(groups().filter(g=>g.attrs["data-layer"]==="target_metric_edge" &&
        g.children[0].attrs.stroke==="#94a3b8").every(g=>
        g.children[0].attrs["stroke-dasharray"]==="4 3"),
        "unavailable time must display dashed gray rather than plausible speed");
    assert.ok(elements["metric-legend"].textContent.includes("m/s"),
        "numeric speed legend required");
    if(metricInfo.speed_screen==="not_screened"){
        assert.ok(elements["metric-screening"].textContent.includes("DISABLED"),
            "unscreened jumps must be disclosed");
    }
    overlays[0].handlers.click();
    assert.ok(details.textContent.includes('"duration_s"'), "details must expose derived time evidence");
    const mode = elements["metric-mode"];
    assert.equal(mode.disabled, false);
    mode.value = "pace_s_per_km";
    mode.handlers.change();
    assert.ok(elements["metric-legend"].textContent.includes("min/km"),
        "pace mode must disclose inverse conversion and units");
    assert.ok(elements["metric-legend"].textContent.includes("reciprocal"),
        "switching to pace must explain identical reciprocal bin colors");
    assert.ok(elements["metric-legend"].textContent.includes("descending"),
        "pace bins decrease as velocity increases");
    const recolored=groups().filter(g=>g.attrs["data-layer"]==="target_metric_edge")
       .map(g=>g.children[0].attrs.stroke);
    assert.deepEqual(recolored,strokes,
        "speed and its reciprocal pace must map each same edge into the same speed bin");
    assert.equal(groups().filter(g => g.attrs["data-layer"] === "target_metric_edge").length, 2);
    const checkbox = checkboxes.find(c => c.dataset.layer === "target_metric_edge");
    checkbox.checked = false; checkbox.handlers.change();
    assert.equal(groups().filter(g => g.attrs["data-layer"] === "target_metric_edge").length, 0);
    assert.equal(groups().filter(g => g.attrs["data-layer"] === "target_segment").length, 2,
        "disabling overlay must preserve source-confirmed spatial segments");
    checkbox.checked = true; checkbox.handlers.change();
    assert.equal(groups().filter(g => g.attrs["data-layer"] === "target_metric_edge").length, 2);
}

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

console.log("M2E/M2F DOM runtime: SVG lines/points, verified metric colors, neutral missing time, layer/mode controls, click, zoom, pan, reset PASS");
