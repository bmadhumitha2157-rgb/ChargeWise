import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Circle, Tooltip, useMap } from "react-leaflet";

const API = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
async function api(path, opts) {
  let r;
  try { r = await fetch(API + path, opts); } catch { throw new Error("Cannot reach the ChargeWise backend. Check that it is running and VITE_API_URL is correct."); }
  if (!r.ok) { let m = `Request failed (${r.status})`; try { const j = await r.json(); m = typeof j.detail === "string" ? j.detail : m; } catch {} throw new Error(m); }
  return r.json();
}
const LVL = ["LOW", "MEDIUM", "HIGH", "VERY HIGH"], LC = ["#2e9e5b", "#e0a100", "#d64545", "#8e1b1b"], PURPLE = "#7b4fc9", GREY = "#9aa3af";
const MODES = [["status", "Current Status"], ["forecast", "Forecast Demand"], ["congestion", "Congestion Risk"], ["anomaly", "Anomalies"], ["utilization", "Utilization"], ["hotspots", "Demand Hotspots"]];
const pct = (v) => `${Math.round(v * 100)}%`;
const utilColor = (u) => LC[u < 0.5 ? 0 : u < 0.8 ? 1 : u < 1 ? 2 : 3];
const ramp = (t) => `hsl(215 ${40 + 40 * t}% ${78 - 42 * t}%)`;
const Badge = ({ level }) => <span className="badge" style={{ background: LC[LVL.indexOf(level)] }}>{level}</span>;

function FlyTo({ target }) { const map = useMap(); useEffect(() => { if (target) map.flyTo([target.latitude, target.longitude], Math.max(map.getZoom(), 12), { duration: 0.6 }); }, [target, map]); return null; }
function FitAll({ stations }) { const map = useMap(); useEffect(() => { if (stations.length) map.fitBounds(stations.map((s) => [s.latitude, s.longitude]), { padding: [60, 60] }); }, [stations.length]); return null; }

export default function App() {
  const [stations, setStations] = useState([]); const [meta, setMeta] = useState({}); const [hot, setHot] = useState({ hotspots: [], density: [] });
  const [err, setErr] = useState(""); const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState("status"); const [q, setQ] = useState(""); const [fly, setFly] = useState(null);
  const [f, setF] = useState({ cong: "ALL", anomaly: false, demand: "ALL", minUtil: 0, type: "ALL" });
  const [sel, setSel] = useState(null); const [compare, setCompare] = useState([]);

  useEffect(() => {
    Promise.all([api("/api/stations"), api("/api/hotspots")]).then(([s, h]) => { setStations(s.stations); setMeta(s); setHot(h); }).catch((e) => setErr(e.message)).finally(() => setLoading(false));
  }, []);

  const maxSess = useMemo(() => Math.max(1, ...stations.map((s) => s.predicted_sessions_24h)), [stations]);
  const terc = useMemo(() => { const v = stations.map((s) => s.predicted_sessions_24h).sort((a, b) => a - b); return [v[Math.floor(v.length / 3)], v[Math.floor((2 * v.length) / 3)]]; }, [stations]);
  const types = useMemo(() => [...new Set(stations.map((s) => s.station_type))], [stations]);
  const visible = stations.filter((s) => {
    const lvl = s.predicted_sessions_24h <= terc[0] ? "LOW" : s.predicted_sessions_24h <= terc[1] ? "MEDIUM" : "HIGH";
    return (f.cong === "ALL" || s.congestion === f.cong) && (!f.anomaly || s.anomaly.flag) && (f.demand === "ALL" || lvl === f.demand) && s.peak_utilization >= f.minUtil && (f.type === "ALL" || s.station_type === f.type);
  });

  function style(s) {
    if (mode === "forecast") return { c: ramp(s.predicted_sessions_24h / maxSess), r: 8 + 12 * (s.predicted_sessions_24h / maxSess) };
    if (mode === "congestion") return { c: LC[s.congestion_level], r: 11 };
    if (mode === "anomaly") return { c: s.anomaly.flag ? PURPLE : GREY, r: s.anomaly.flag ? 15 : 8 };
    if (mode === "utilization") return { c: utilColor(s.peak_utilization), r: 8 + 10 * Math.min(1.2, s.peak_utilization) };
    if (mode === "hotspots") return { c: s.hotspot_id ? LC[2] : GREY, r: 9 };
    return { c: s.anomaly.flag ? PURPLE : utilColor(s.current_utilization), r: 11 };
  }
  function search(e) { e.preventDefault(); const t = q.trim().toLowerCase(); const m = stations.find((s) => s.station_id.toLowerCase() === t) || stations.find((s) => s.location_name.toLowerCase().includes(t)); if (m) { setSel(m.station_id); setFly(m); setErr(""); } else setErr(`No station matches "${q}".`); }
  const legend = { status: [["Low", LC[0]], ["Medium", LC[1]], ["High", LC[2]], ["Anomaly", PURPLE]], congestion: LVL.map((l, i) => [l, LC[i]]), forecast: [["Lower demand", ramp(0.1)], ["Higher demand", ramp(1)]], anomaly: [["Anomaly", PURPLE], ["Normal", GREY]], utilization: [["<50%", LC[0]], ["50–80%", LC[1]], ["80–100%", LC[2]], [">100%", LC[3]]], hotspots: [["In hotspot", LC[2]], ["Other", GREY]] }[mode];

  return (
    <div className="app">
      <header className="top">
        <span className="brand">CHARGEWISE</span>
        <form onSubmit={search}><input placeholder="Search station ID or location" value={q} onChange={(e) => setQ(e.target.value)} /></form>
        <div className="modes">{MODES.map(([k, l]) => <button key={k} className={mode === k ? "on" : ""} onClick={() => setMode(k)}>{l}</button>)}</div>
        <div className="filters">
          <select value={f.cong} onChange={(e) => setF({ ...f, cong: e.target.value })}><option value="ALL">Congestion: all</option>{LVL.map((l) => <option key={l}>{l}</option>)}</select>
          <select value={f.demand} onChange={(e) => setF({ ...f, demand: e.target.value })}><option value="ALL">Demand: all</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option></select>
          <select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}><option value="ALL">Type: all</option>{types.map((t) => <option key={t}>{t}</option>)}</select>
          <label>Util ≥ {pct(f.minUtil)} <input type="range" min="0" max="1.2" step="0.1" value={f.minUtil} onChange={(e) => setF({ ...f, minUtil: +e.target.value })} /></label>
          <label><input type="checkbox" checked={f.anomaly} onChange={(e) => setF({ ...f, anomaly: e.target.checked })} /> Anomalies only</label>
        </div>
      </header>
      <div className="main">
        <div className="mapwrap">
          {meta.data_is_synthetic_demo && <div className="banner">Demo mode: synthetic dataset & fictional coordinates – not real-world data.</div>}
          {err && <div className="banner err" style={{ top: meta.data_is_synthetic_demo ? 40 : 8 }} onClick={() => setErr("")}>{err}</div>}
          {loading && <div className="banner">Loading stations…</div>}
          <MapContainer center={[13.08, 80.26]} zoom={11} zoomControl>
            <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <FitAll stations={stations} /><FlyTo target={fly} />
            {mode === "hotspots" && hot.density.map((d, i) => <Circle key={"d" + i} center={[d.latitude, d.longitude]} radius={1200 + 9000 * d.weight} pathOptions={{ color: "#d64545", weight: 0, fillOpacity: 0.12 + 1.2 * d.weight }} />)}
            {mode === "hotspots" && hot.hotspots.map((h) => <Circle key={h.hotspot_id} center={[h.latitude, h.longitude]} radius={h.radius_km * 1000} pathOptions={{ color: "#b02a2a", weight: 2, dashArray: "6 4", fillOpacity: 0.08 }}><Tooltip sticky>{`HIGH DEMAND HOTSPOT – ${h.stations.join(", ")}: ${h.predicted_sessions_24h} sessions / 24h`}</Tooltip></Circle>)}
            {visible.map((s) => { const st = style(s); return (
              <CircleMarker key={s.station_id} center={[s.latitude, s.longitude]} radius={st.r} pathOptions={{ color: sel === s.station_id ? "#111" : "#fff", weight: sel === s.station_id ? 3 : 2, fillColor: st.c, fillOpacity: 0.95 }} eventHandlers={{ click: () => setSel(s.station_id) }}>
                <Tooltip>{s.station_id} · {s.location_name}</Tooltip>
              </CircleMarker>); })}
          </MapContainer>
          <div className="legend"><b>{MODES.find((m) => m[0] === mode)[1]}</b>{legend.map(([l, c]) => <span key={l}><i style={{ background: c }} />{l}</span>)}<span style={{ color: "#647084" }}> · {visible.length}/{stations.length} shown</span></div>
          {compare.length > 1 && <CompareBar ids={compare} stations={stations} onClear={() => setCompare([])} />}
        </div>
        {sel && <Panel id={sel} onClose={() => setSel(null)} compare={compare} setCompare={setCompare} onPick={(id) => { setSel(id); setFly(stations.find((s) => s.station_id === id)); }} />}
      </div>
    </div>
  );
}

function CompareBar({ ids, stations, onClear }) {
  const rows = ids.map((i) => stations.find((s) => s.station_id === i)).filter(Boolean);
  const dist = (a, b) => { const R = 6371.0088, r = Math.PI / 180, dl = (b.latitude - a.latitude) * r, dn = (b.longitude - a.longitude) * r; const h = Math.sin(dl / 2) ** 2 + Math.cos(a.latitude * r) * Math.cos(b.latitude * r) * Math.sin(dn / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };
  return <div className="cmp"><b>Compare</b> <button onClick={onClear}>clear</button>
    <table><thead><tr><th></th>{rows.map((s) => <th key={s.station_id}>{s.station_id}</th>)}</tr></thead><tbody>
      <tr><td>Sessions (24h)</td>{rows.map((s) => <td key={s.station_id}>{s.predicted_sessions_24h}</td>)}</tr>
      <tr><td>Energy (kWh)</td>{rows.map((s) => <td key={s.station_id}>{s.predicted_energy_kwh_24h}</td>)}</tr>
      <tr><td>Peak utilization</td>{rows.map((s) => <td key={s.station_id}>{pct(s.peak_utilization)}</td>)}</tr>
      <tr><td>Congestion</td>{rows.map((s) => <td key={s.station_id}>{s.congestion}</td>)}</tr>
      <tr><td>Anomaly</td>{rows.map((s) => <td key={s.station_id}>{s.anomaly.flag ? "Yes" : "No"}</td>)}</tr>
      <tr><td>Distance from {rows[0].station_id}</td>{rows.map((s) => <td key={s.station_id}>{s === rows[0] ? "–" : dist(rows[0], s).toFixed(1) + " km"}</td>)}</tr></tbody></table></div>;
}

function Panel({ id, onClose, compare, setCompare, onPick }) {
  const [tab, setTab] = useState("overview"); const [d, setD] = useState(null); const [nb, setNb] = useState(null); const [err, setErr] = useState("");
  useEffect(() => { setD(null); setNb(null); setErr(""); Promise.all([api(`/api/stations/${id}`), api(`/api/stations/${id}/nearby`)]).then(([a, b]) => { setD(a); setNb(b); }).catch((e) => setErr(e.message)); }, [id]);
  if (err) return <aside className="panel"><button onClick={onClose}>Close</button><p>{err}</p></aside>;
  if (!d) return <aside className="panel">Loading…</aside>;
  const inCmp = compare.includes(id);
  return (
    <aside className="panel">
      <div style={{ display: "flex", justifyContent: "space-between" }}><h2>STATION {d.station_id}</h2><button onClick={onClose}>✕</button></div>
      <div className="sub">{d.location_name} · {d.station_type} · {d.latitude.toFixed(4)}, {d.longitude.toFixed(4)}</div>
      <Badge level={d.congestion} /> {d.anomaly.flag && <span className="badge" style={{ background: "#7b4fc9" }}>ANOMALY</span>}{" "}
      <button style={{ float: "right" }} onClick={() => setCompare(inCmp ? compare.filter((x) => x !== id) : [...compare, id].slice(-4))}>{inCmp ? "Remove from compare" : "Compare"}</button>
      <div className="tabs">{[["overview", "Overview"], ["forecast", "Forecast"], ["nearby", "Nearby"], ["whatif", "What-if"]].map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "overview" && <>
        <div className="kv"><span>Chargers</span><span>{d.chargers}</span><span>Current utilization</span><span>{pct(d.current_utilization)}</span>
          <span>Predicted sessions (24h)</span><span>{d.predicted_sessions_24h}</span><span>Predicted energy (24h)</span><span>{d.predicted_energy_kwh_24h} kWh</span>
          <span>Expected peak</span><span>{d.peak_window}</span><span>Predicted peak utilization</span><span>{pct(d.peak_utilization)}</span></div>
        <b>Anomaly</b><p style={{ margin: "2px 0 8px" }}>{d.anomaly.flag ? `Unusual demand pattern detected. Historical average ${d.anomaly.historical_avg_sessions_per_day} sessions/day; observed ${d.anomaly.observed_sessions} on ${d.anomaly.date}.` : d.anomaly.message}</p>
        <b>Key prediction factors</b><ul className="f">{d.factors.map((x) => <li key={x}>{x}</li>)}</ul>
        <b>Capacity insight</b><p style={{ margin: "2px 0" }}>{d.capacity.estimated_additional_chargers > 0 ? `Estimated additional capacity: ${d.capacity.estimated_additional_chargers} chargers. ` : ""}{d.capacity.message}</p>
        <div className="note">{d.capacity.disclaimer}</div></>}
      {tab === "forecast" && <Forecast d={d} />}
      {tab === "nearby" && <Nearby d={d} nb={nb} onPick={onPick} />}
      {tab === "whatif" && <WhatIf d={d} />}
    </aside>
  );
}

function Forecast({ d }) {
  const mx = Math.max(...d.forecast.map((x) => x.sessions), 1), W = 360, H = 130, bw = W / d.forecast.length;
  return <><div className="sub">Next 24 hours from {d.forecast[0].timestamp.slice(0, 16)} (model output)</div>
    <svg width="100%" viewBox={`0 0 ${W} ${H + 18}`}>{d.forecast.map((x, i) => <g key={i}><rect x={i * bw + 1} y={H - (x.sessions / mx) * H} width={bw - 2} height={(x.sessions / mx) * H} fill={x.utilization >= 0.8 ? "#d64545" : "#1f5fbf"}><title>{`${x.hour_label}: ${x.sessions} sessions, ${x.kwh} kWh, util ${pct(x.utilization)}`}</title></rect>{i % 3 === 0 && <text x={i * bw} y={H + 13} fontSize="9" fill="#647084">{x.hour_label}</text>}</g>)}</svg>
    <div className="note">Bars = predicted sessions starting each hour; red = predicted utilization ≥ 80%.</div>
    <div className="kv"><span>Peak hour</span><span>{d.peak_hour}</span><span>Peak window</span><span>{d.peak_window}</span><span>Max sessions/hour</span><span>{d.peak_sessions}</span></div></>;
}

function Nearby({ d, nb, onPick }) {
  if (!nb) return <p>Loading…</p>;
  return <>{d.congestion_level >= 2 && <><b>Recommended alternatives</b>{nb.alternatives_recommended.length ? nb.alternatives_recommended.map((a) => <div className="alt" key={a.station_id}><b style={{ cursor: "pointer" }} onClick={() => onPick(a.station_id)}>{a.station_id} · {a.location_name}</b> <Badge level={a.congestion} />
    <div className="note">{a.distance_km} km · predicted peak util {pct(a.peak_utilization)} · ~{a.spare_chargers_at_peak} spare chargers · score {a.score}</div></div>) : <p>{nb.message || "No alternatives found."}</p>}
    <div className="note">Ranked by distance, utilization and spare capacity (not just nearest).</div></>}
    <b>Nearby stations</b>{nb.nearby.length ? nb.nearby.slice(0, 8).map((n) => <div key={n.station_id} style={{ display: "flex", justifyContent: "space-between", margin: "3px 0", cursor: "pointer" }} onClick={() => onPick(n.station_id)}><span>{n.station_id} · {n.location_name}</span><span><Badge level={n.congestion} /> {n.distance_km} km</span></div>) : <p>No stations within the search radius.</p>}</>;
}

function WhatIf({ d }) {
  const [pctv, setPct] = useState(20), [add, setAdd] = useState(0), [r, setR] = useState(null), [err, setErr] = useState("");
  const run = () => { setErr(""); api("/api/what-if", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ station_id: d.station_id, demand_change_pct: pctv, added_chargers: add }) }).then(setR).catch((e) => setErr(e.message)); };
  return <><div className="note" style={{ marginTop: 0 }}>Scenario simulation on model forecasts – not a real-world experiment.</div>
    <label>Demand change: <b>{pctv > 0 ? "+" : ""}{pctv}%</b><input style={{ width: "100%" }} type="range" min="-50" max="100" step="10" value={pctv} onChange={(e) => setPct(+e.target.value)} /></label>
    <label>Chargers added/removed: <b>{add > 0 ? "+" : ""}{add}</b> (now {d.chargers})<input style={{ width: "100%" }} type="range" min={-Math.min(5, d.chargers - 1)} max="10" step="1" value={add} onChange={(e) => setAdd(+e.target.value)} /></label>
    <button className="on" onClick={run}>Run scenario</button>{err && <p style={{ color: "#b02a2a" }}>{err}</p>}
    {r && <div className="kv" style={{ marginTop: 10 }}><span>Sessions (24h)</span><span>{r.current.sessions_24h} → {r.scenario.sessions_24h}</span><span>Chargers</span><span>{r.current.chargers} → {r.scenario.chargers}</span>
      <span>Peak utilization</span><span>{pct(r.current.peak_utilization)} → {pct(r.scenario.peak_utilization)}</span><span>Congestion</span><span>{r.current.congestion} → {r.scenario.congestion}</span>
      <span>Extra chargers to reach ≤80%</span><span>{r.scenario.additional_chargers_suggested}</span></div>}</>;
}
