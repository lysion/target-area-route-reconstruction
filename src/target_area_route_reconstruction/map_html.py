"""M2E self-contained interactive vector map (no basemap/network dependency)."""

from __future__ import annotations

import html
import json
import math

from ._m2d_common import strict_load



def _position(value):
    # Type-exact checks reject bool-as-int and malformed nested coordinates.
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("M2E_MAP_INVALID_COORDINATES")
    lon, lat = value
    if type(lon) not in (int, float) or type(lat) not in (int, float):
        raise ValueError("M2E_MAP_INVALID_COORDINATES")
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("M2E_MAP_COORDINATE_OUT_OF_RANGE")
    if not (math.isfinite(lon) and math.isfinite(lat)):
        raise ValueError("M2E_MAP_NONFINITE_COORDINATE")


def _line(value):
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError("M2E_MAP_INVALID_LINE")
    for point in value:
        _position(point)
    if all(point == value[0] for point in value[1:]):
        raise ValueError("M2E_MAP_DEGENERATE_LINE")


def _ring(value):
    if not isinstance(value, list) or len(value) < 4:
        raise ValueError("M2E_MAP_INVALID_RING")
    for point in value:
        _position(point)
    if value[0] != value[-1]:
        raise ValueError("M2E_MAP_UNCLOSED_RING")


def _polygon(value):
    if not isinstance(value, list) or not value:
        raise ValueError("M2E_MAP_INVALID_POLYGON")
    for ring in value:
        _ring(ring)


def _geometry(geometry, layer):
    # Validate the declared nesting as well as its numeric leaves. A flat
    # coordinate walk would accept malformed Points containing nested rings.
    if not isinstance(geometry, dict):
        raise ValueError("M2E_MAP_INVALID_GEOMETRY")
    kind = geometry.get("type")
    expected = {
        "target_area": {"Polygon", "MultiPolygon"},
        "target_segment": {"LineString"},
        "target_metric_edge": {"LineString"},
        "observed_outside": {"LineString"},
        "gap_endpoint": {"Point"},
    }[layer]
    if kind not in expected:
        raise ValueError("M2E_MAP_LAYER_GEOMETRY_MISMATCH")
    coords = geometry.get("coordinates")
    if kind == "Point":
        _position(coords)
    elif kind == "LineString":
        _line(coords)
    elif kind == "Polygon":
        _polygon(coords)
    else:
        if not isinstance(coords, list) or not coords:
            raise ValueError("M2E_MAP_INVALID_MULTIPOLYGON")
        for polygon in coords:
            _polygon(polygon)


def render_geojson_map(geojson_json: str, *, title: str = "Target area route map") -> str:
    """Return a local HTML map. Treat GeoJSON/provenance as untrusted input.

    SVG paths are built from numeric coordinate arrays, never injected as HTML.
    Gaps remain endpoint markers only; the renderer never draws gap chords.
    """
    collection = strict_load(geojson_json)
    if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection":
        raise ValueError("M2E_MAP_INVALID_GEOJSON")
    if type(title) is not str:
        raise ValueError("M2E_MAP_INVALID_TITLE")
    features = collection.get("features")
    if not isinstance(features, list):
        raise ValueError("M2E_MAP_INVALID_FEATURES")
    allowed = {"target_area", "target_segment", "target_metric_edge", "observed_outside", "gap_endpoint"}
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("M2E_MAP_INVALID_FEATURE")
        props = feature.get("properties")
        if not isinstance(props, dict) or props.get("layer") not in allowed:
            raise ValueError("M2E_MAP_INVALID_LAYER")
    # This rendering API does not independently establish spatial authority.
    # Validate Feature geometry strictly; callers must use verified export.
    for feature in features:
        _geometry(feature.get("geometry"), feature["properties"]["layer"])
    # Escape script closing tags and HTML metacharacters even inside JSON strings.
    payload = json.dumps(collection, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    safe_title = html.escape(title, quote=True)
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>""" + safe_title + """</title>
<style>
body{font:14px system-ui,sans-serif;margin:0;background:#f8fafc;color:#0f172a}
header{padding:12px 18px;background:white;border-bottom:1px solid #cbd5e1}
main{display:flex;flex-wrap:wrap;gap:14px;padding:14px}
#map{flex:1;min-width:280px;width:100%;height:65vh;background:white;border:1px solid #cbd5e1;touch-action:none}
aside{width:260px;max-width:100%}label{display:block;margin:9px 0}
button{padding:6px 12px;margin-right:6px}#detail{white-space:pre-wrap;overflow-wrap:anywhere}
</style></head><body><header><strong>""" + safe_title + """</strong>
<span id="status"></span></header><main><svg id="map" role="img" aria-label="Observed route evidence"></svg>
<aside><p><button id="reset">Reset view</button></p>
<label><input type="checkbox" data-layer="target_area" checked> Target area</label>
<label><input type="checkbox" data-layer="target_segment" checked> Observed inside</label>
<label><input type="checkbox" data-layer="target_metric_edge" checked> Temporal overlay</label>
<label>Metric <select id="metric-mode"><option value="speed_mps">Speed (m/s)</option><option value="pace_s_per_km">Pace (s/km)</option></select></label>
<p id="metric-legend">Gray: metric unavailable; blue shades: derived speed/pace (not quality certification).</p>
<label><input type="checkbox" data-layer="observed_outside" checked> Observed outside</label>
<label><input type="checkbox" data-layer="gap_endpoint" checked> Gap endpoints</label>
<p id="detail">Select a feature for evidence details.</p>
<p><small>Missing GPS sections are not drawn. No inferred routes.</small></p></aside></main>
<script id="evidence" type="application/json">""" + payload + """</script>
<script>
"use strict";
const data=JSON.parse(document.getElementById("evidence").textContent);
const svg=document.getElementById("map"),NS="http://www.w3.org/2000/svg";
const visible=new Set(["target_area","target_segment","target_metric_edge","observed_outside","gap_endpoint"]);
const metricMode=document.getElementById("metric-mode");
const overlayInfo=(data.metadata||{}).temporal_overlay;
metricMode.value=overlayInfo?.mode||"speed_mps";
metricMode.disabled=!overlayInfo;
const colors={target_area:"#2563eb",target_segment:"#15803d",observed_outside:"#64748b",gap_endpoint:"#d97706"};
// Fixed *display bins*, not GPS quality thresholds or speed validation.
const speedBins=[1.5,2.5,3.5,4.5];
const speedPalette=["#bfdbfe","#93c5fd","#60a5fa","#2563eb","#1d4ed8"];
function metricColor(properties){
 const metric=properties.metric;
 if(!metric||metric.status!=="valid")return "#94a3b8";
 const value=metric[metricMode.value];
 if(!Number.isFinite(value)||value<0|| (metricMode.value==="pace_s_per_km"&&value===0))return "#94a3b8";
 const speed=metricMode.value==="pace_s_per_km"?1000/value:value;
 let i=0;while(i<speedBins.length&&speed>=speedBins[i])i++;
 return speedPalette[i];
}
const coords=[];
function collect(g){if(!g)return;if(g.type==="Point")coords.push(g.coordinates);
else if(g.type==="LineString"||g.type==="MultiPoint")g.coordinates.forEach(p=>coords.push(p));
else if(g.type==="Polygon"||g.type==="MultiLineString")g.coordinates.forEach(r=>r.forEach(p=>coords.push(p)));
else if(g.type==="MultiPolygon")g.coordinates.forEach(p=>p.forEach(r=>r.forEach(c=>coords.push(c))));}
data.features.forEach(f=>collect(f.geometry));
const valid=coords.filter(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite));
if(valid.length!==coords.length)throw Error("Invalid coordinate");
let x0=0,x1=1,y0=0,y1=1;
if(valid.length){
 x0=x1=valid[0][0]; y0=y1=valid[0][1];
 for(const p of valid){x0=Math.min(x0,p[0]);x1=Math.max(x1,p[0]);y0=Math.min(y0,p[1]);y1=Math.max(y1,p[1]);}
}
const dx=Math.max(x1-x0,1e-9),dy=Math.max(y1-y0,1e-9),scale=Math.min(940/dx,640/dy);
const project=p=>[500+(p[0]-(x0+x1)/2)*scale,350-(p[1]-(y0+y1)/2)*scale];
const node=(tag,attrs)=>{const el=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,String(v)));return el;};
const path=ring=>ring.map((p,i)=>{const [x,y]=project(p);return (i?"L":"M")+x+" "+y;}).join(" ");
function shapes(g,layer){
 const out=[],color=colors[layer];
 if(g.type==="Point"){const [cx,cy]=project(g.coordinates);out.push(node("circle",{cx,cy,r:5,fill:color,stroke:"white","stroke-width":1}));}
 if(g.type==="LineString")out.push(node("path",{d:path(g.coordinates),fill:"none",stroke:color,"stroke-width":3}));
 if(g.type==="Polygon"||g.type==="MultiPolygon"){
  const polys=g.type==="Polygon"?[g.coordinates]:g.coordinates;
  polys.forEach(poly=>out.push(node("path",{d:poly.map(r=>path(r)+" Z").join(" "),fill:color,"fill-opacity":0.1,stroke:color,"stroke-width":2,"fill-rule":"evenodd"})));
 }
 return out;
}
function draw(){
 svg.replaceChildren();
 const root=node("g",{});svg.append(root);
 data.features.forEach(f=>{
  const layer=f.properties.layer;if(!visible.has(layer))return;
  const group=node("g",{"data-layer":layer});
  shapes(f.geometry,layer).forEach(s=>{
    if(layer==="target_metric_edge")s.setAttribute("stroke",metricColor(f.properties));
    group.append(s);
  });
  group.addEventListener("click",()=>{document.getElementById("detail").textContent=JSON.stringify(f.properties,null,2);});
  root.append(group);
 });
}
let view=[0,0,1000,700];function apply(){svg.setAttribute("viewBox",view.join(" "));}apply();draw();
const meta=data.metadata||{};
document.getElementById("status").textContent="  | relation: "+(meta.relation??"not assessable")+" | coverage: "+(meta.coverage_completeness??"not assessable");
document.querySelectorAll("[data-layer]").forEach(c=>c.addEventListener("change",()=>{c.checked?visible.add(c.dataset.layer):visible.delete(c.dataset.layer);draw();}));
metricMode.addEventListener("change",draw);
document.getElementById("reset").onclick=()=>{view=[0,0,1000,700];apply();};
svg.addEventListener("wheel",e=>{e.preventDefault();const factor=e.deltaY>0?1.15:1/1.15;view=[view[0]+view[2]*(1-factor)/2,view[1]+view[3]*(1-factor)/2,view[2]*factor,view[3]*factor];apply();},{passive:false});
let drag=null;svg.addEventListener("pointerdown",e=>{drag=[e.clientX,e.clientY,...view];svg.setPointerCapture(e.pointerId);});
svg.addEventListener("pointermove",e=>{if(!drag)return;const rect=svg.getBoundingClientRect();view[0]=drag[2]-(e.clientX-drag[0])*drag[4]/rect.width;view[1]=drag[3]-(e.clientY-drag[1])*drag[5]/rect.height;apply();});
svg.addEventListener("pointerup",()=>{drag=null;});svg.addEventListener("pointercancel",()=>{drag=null;});
</script></body></html>"""
