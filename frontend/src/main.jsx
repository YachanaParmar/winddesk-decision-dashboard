import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Activity, ArrowDownRight, ArrowUpRight, Clock3, RefreshCw, Wind } from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const fmt = (n) => n == null ? '—' : new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1 }).format(n);

function App() {
  const [lead, setLead] = useState(24);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  async function load(forceRefresh = false) {
    setLoading(true); setError('');
    try {
      const refreshParam = forceRefresh ? '&refresh=true' : '';
      const res = await fetch(`${API}/api/dashboard?lead_hours=${lead}${refreshParam}`);
      if (!res.ok) throw new Error(`API returned ${res.status}: ${await res.text()}`);
      setData(await res.json());
    } catch (e) { setError(e.message || 'Could not load dashboard data.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [lead]);
  const chartRows = useMemo(() => (data?.rows || []).filter((_, i) => i % 4 === 0).map(r => ({ ...r, label: new Date(r.startTime).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' }) + ' ' + new Date(r.startTime).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) })), [data]);
  const m = data?.metrics || {};
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><div className="brand-icon"><Wind size={21}/></div><div><strong>wind<span>desk</span></strong><small>ENERGY INTELLIGENCE</small></div></div><div className="nav-label">WORKSPACE</div><div className="nav-item active"><Activity size={17}/> Forecast overview</div><div className="nav-item"><Clock3 size={17}/> Decision history</div><div className="side-note"><div className="live-dot"/> <span>Data source</span><strong>Elexon BMRS</strong><small>Wind generation · UK</small></div><div className="sidebar-bottom">JANUARY 2026<br/><span>Prototype dashboard</span></div></aside>
    <main className="main"><header className="topbar"><div><div className="eyebrow">ENERGY TRADING / ANALYTICS</div><h1>Wind forecast overview</h1><p className="subtitle">See what was knowable at purchase time — and how it compared with reality.</p></div><button className="refresh" onClick={() => load(true)} disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''}/> Refresh data</button></header>
      <section className="control-row"><div><span className="control-title">DELIVERY PERIOD</span><strong>January 2026 decision dates</strong></div><div className="lead-control"><label htmlFor="lead">Decision lead time</label><select id="lead" value={lead} onChange={e => setLead(Number(e.target.value))}><option value="6">6 hours before delivery</option><option value="12">12 hours before delivery</option><option value="24">24 hours before delivery (day-ahead)</option><option value="36">36 hours before delivery</option><option value="48">48 hours before delivery</option></select></div><div className="assumption">Cutoff = delivery time minus {lead}h</div></section>
      {error && <div className="alert"><strong>Could not load live data.</strong><p>{error}</p><small>Check that the FastAPI backend is running and the Elexon API response matches the expected schema.</small></div>}
      {loading && !data ? <div className="loading">Loading January wind data…</div> : <>
        {data?.message && <div className="alert"><strong>Data note</strong><p>{data.message}</p></div>}
        <section className="metrics"><Metric title="Matched intervals" value={fmt(m.matchedIntervals)} note="30-minute periods" icon={<Activity size={18}/>} /><Metric title="Mean absolute error" value={m.mae == null ? '—' : `${fmt(m.mae)} MW`} note="Average forecast miss" icon={<ArrowDownRight size={18}/>} /><Metric title="RMSE" value={m.rmse == null ? '—' : `${fmt(m.rmse)} MW`} note="Penalises larger misses" icon={<ArrowUpRight size={18}/>} /><Metric title="Forecast bias" value={m.bias == null ? '—' : `${m.bias > 0 ? '+' : ''}${fmt(m.bias)} MW`} note="Positive = over-forecast" icon={<Wind size={18}/>} /> </section>
        <section className="panel"><div className="panel-head"><div><h2>Forecast vs actual generation</h2><p>Sampled view across the month · MW</p></div><div className="legend"><span className="legend-blue"/> Forecast <span className="legend-green"/> Actual</div></div><div className="chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartRows} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}><defs><linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#6788f5" stopOpacity={0.22}/><stop offset="100%" stopColor="#6788f5" stopOpacity={0.01}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e8edf4"/><XAxis dataKey="label" tick={{fontSize:10, fill:'#8993a4'}} tickLine={false} axisLine={false} minTickGap={32}/><YAxis tick={{fontSize:11, fill:'#8993a4'}} tickLine={false} axisLine={false} width={55}/><Tooltip/><Legend/><Area type="monotone" dataKey="forecast" name="Forecast" stroke="#6788f5" fill="url(#forecastFill)" strokeWidth={2} dot={false}/><Line type="monotone" dataKey="actual" name="Actual" stroke="#20a77a" strokeWidth={2} dot={false}/></AreaChart></ResponsiveContainer></div><div className="panel-foot">Decision dates are restricted to January 2026. Forecast selected using the latest publication available by the selected decision cutoff.</div></section>
        <section className="panel table-panel"><div className="panel-head"><div><h2>Recent matched intervals</h2><p>Forecast publication time is shown to support auditability.</p></div><span className="count-pill">{data?.rows?.length || 0} records</span></div><div className="table-wrap"><table><thead><tr><th>DELIVERY TIME (UTC)</th><th>FORECAST PUBLISHED</th><th>FORECAST MW</th><th>ACTUAL MW</th><th>ERROR MW</th></tr></thead><tbody>{(data?.rows || []).slice(-12).reverse().map(r=><tr key={r.startTime}><td>{new Date(r.startTime).toLocaleString('en-GB',{timeZone:'UTC',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})}</td><td>{new Date(r.publishTime).toLocaleString('en-GB',{timeZone:'UTC',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})}</td><td>{fmt(r.forecast)}</td><td>{fmt(r.actual)}</td><td className={r.error > 0 ? 'positive' : r.error < 0 ? 'negative' : ''}>{r.error > 0 ? '+' : ''}{fmt(r.error)}</td></tr>)}</tbody></table></div></section>
        <div className="method"><strong>Methodology & assumption</strong><p>{data?.assumption || `Decision cutoff = delivery start minus ${lead} hours. For each interval, the app selects the latest forecast published on or before the cutoff, then compares it with actual wind generation.`} MAE and RMSE are in MW; bias is forecast minus actual. Intervals without both an eligible forecast and actual are excluded.</p></div>
      </>}
      <footer>WINDDESK <span>·</span> ELEXON DATA <span>·</span> JANUARY 2026 DECISIONS</footer>
    </main>
  </div>
}
function Metric({title,value,note,icon}) { return <div className="metric-card"><div className="metric-top"><span>{title}</span><div className="metric-icon">{icon}</div></div><strong className="metric-value">{value}</strong><small>{note}</small></div> }

createRoot(document.getElementById('root')).render(<App/>);
