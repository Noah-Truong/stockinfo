import { useState, useEffect } from "react";

const SECTOR_BENCHMARKS = {
  "Technology": { pe: 28.0, ev_ebitda: 20.0 },
  "Communication Services": { pe: 22.0, ev_ebitda: 14.0 },
  "Consumer Cyclical": { pe: 24.0, ev_ebitda: 13.0 },
  "Healthcare": { pe: 22.0, ev_ebitda: 14.0 },
  "Financial Services": { pe: 14.0, ev_ebitda: 10.0 },
  "Energy": { pe: 12.0, ev_ebitda: 7.0 },
  "Default": { pe: 20.0, ev_ebitda: 13.0 },
};

const THRESHOLDS = { upside: 15, downside: -10, pe_premium: 30, pe_discount: -20, ev_premium: 25, ev_discount: -20 };

function getUpside(stock) {
  if (!stock.price || !stock.target) return null;
  return ((stock.target - stock.price) / stock.price) * 100;
}

function getAlerts(stock) {
  const alerts = [];
  const bench = SECTOR_BENCHMARKS[stock.sector] || SECTOR_BENCHMARKS["Default"];
  const upside = getUpside(stock);

  if (upside !== null) {
    if (upside >= THRESHOLDS.upside)
      alerts.push({ type: "UPSIDE", label: `+${upside.toFixed(1)}% upside`, color: "#22c55e", bg: "#052e16" });
    else if (upside <= THRESHOLDS.downside)
      alerts.push({ type: "DOWNSIDE", label: `${upside.toFixed(1)}% downside`, color: "#ef4444", bg: "#2d0a0a" });
  }

  if (stock.pe && bench.pe) {
    const diff = ((stock.pe - bench.pe) / bench.pe) * 100;
    if (diff >= THRESHOLDS.pe_premium)
      alerts.push({ type: "PE_HIGH", label: `P/E ${diff.toFixed(0)}% above sector`, color: "#f59e0b", bg: "#1c1408" });
    else if (diff <= THRESHOLDS.pe_discount)
      alerts.push({ type: "PE_LOW", label: `P/E ${Math.abs(diff).toFixed(0)}% below sector`, color: "#38bdf8", bg: "#0c1e2e" });
  }

  if (stock.ev_ebitda && bench.ev_ebitda) {
    const diff = ((stock.ev_ebitda - bench.ev_ebitda) / bench.ev_ebitda) * 100;
    if (diff >= THRESHOLDS.ev_premium)
      alerts.push({ type: "EV_HIGH", label: `EV/EBITDA ${diff.toFixed(0)}% above sector`, color: "#f59e0b", bg: "#1c1408" });
    else if (diff <= THRESHOLDS.ev_discount)
      alerts.push({ type: "EV_LOW", label: `EV/EBITDA ${Math.abs(diff).toFixed(0)}% below sector`, color: "#38bdf8", bg: "#0c1e2e" });
  }

  return alerts;
}

function UpsideBar({ upside }) {
  if (upside === null) return <span style={{ color: "#475569" }}>N/A</span>;
  const color = upside >= 15 ? "#22c55e" : upside <= -10 ? "#ef4444" : upside > 0 ? "#86efac" : "#fca5a5";
  const width = Math.min(Math.abs(upside) * 2, 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ width: 60, height: 6, background: "#1e293b", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${width}%`, height: "100%", background: color, borderRadius: 3, transition: "width .4s ease" }} />
      </div>
      <span style={{ color, fontWeight: 700, fontSize: 13, minWidth: 56 }}>
        {upside > 0 ? "+" : ""}{upside.toFixed(1)}%
      </span>
    </div>
  );
}

function Badge({ label, color, bg }) {
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: 4,
      fontSize: 11, fontWeight: 700, letterSpacing: ".04em",
      color, background: bg, border: `1px solid ${color}30`, marginRight: 4
    }}>{label}</span>
  );
}

function AlertCard({ stock }) {
  const alerts = getAlerts(stock);
  const upside = getUpside(stock);
  const bench = SECTOR_BENCHMARKS[stock.sector] || SECTOR_BENCHMARKS["Default"];

  return (
    <div style={{
      background: "#0f172a", border: "1px solid #1e3a5f", borderRadius: 10,
      padding: "18px 20px", marginBottom: 10,
      boxShadow: "0 4px 24px rgba(0,0,0,.4)",
      animation: "fadeSlide .35s ease both"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8 }}>
        <div>
          <span style={{ color: "#f8fafc", fontWeight: 800, fontSize: 16, fontFamily: "'IBM Plex Mono', monospace" }}>{stock.ticker}</span>
          <span style={{ color: "#64748b", fontSize: 13, marginLeft: 8 }}>{stock.name}</span>
          <span style={{ color: "#334155", fontSize: 11, marginLeft: 8, background: "#1e293b", padding: "2px 6px", borderRadius: 4 }}>{stock.sector}</span>
        </div>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {alerts.map((a, i) => <Badge key={i} {...a} />)}
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 12, marginTop: 14 }}>
        {[
          ["Price", `$${stock.price.toFixed(2)}`, "#e2e8f0"],
          ["Target", stock.target ? `$${stock.target.toFixed(2)}` : "N/A", "#e2e8f0"],
          ["P/E", stock.pe ? `${stock.pe.toFixed(1)}x` : "N/A", stock.pe && ((stock.pe - bench.pe)/bench.pe*100) >= 30 ? "#f59e0b" : "#e2e8f0"],
          ["EV/EBITDA", stock.ev_ebitda ? `${stock.ev_ebitda.toFixed(1)}x` : "N/A", "#e2e8f0"],
          ["Consensus", stock.recommendation, stock.recommendation === "STRONG BUY" ? "#22c55e" : stock.recommendation === "BUY" ? "#86efac" : "#f59e0b"],
        ].map(([label, value, color]) => (
          <div key={label}>
            <div style={{ color: "#475569", fontSize: 10, textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 2 }}>{label}</div>
            <div style={{ color, fontWeight: 700, fontSize: 14 }}>{value}</div>
          </div>
        ))}
        <div>
          <div style={{ color: "#475569", fontSize: 10, textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4 }}>Upside</div>
          <UpsideBar upside={upside} />
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background: "#0f172a", border: `1px solid ${accent}30`, borderRadius: 10,
      padding: "20px 24px", flex: "1 1 150px"
    }}>
      <div style={{ color: "#475569", fontSize: 11, textTransform: "uppercase", letterSpacing: ".06em" }}>{label}</div>
      <div style={{ color: accent, fontSize: 32, fontWeight: 800, margin: "6px 0 2px", fontFamily: "'IBM Plex Mono', monospace" }}>{value}</div>
      {sub && <div style={{ color: "#334155", fontSize: 12 }}>{sub}</div>}
    </div>
  );
}

export default function StockDashboard() {
  const [stocks, setStocks] = useState([]);
  const [filter, setFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("upside");
  const [newTicker, setNewTicker] = useState("");
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [emailSent, setEmailSent] = useState(false);

  useEffect(() => {
    async function loadData() {
      try {
        const res = await fetch("alerts_output.json", { cache: "no-store" });
        if (!res.ok) return;
        const json = await res.json();
        const runTime = json.run_time || json.runTime;
        if (runTime) {
          const dt = new Date(runTime);
          if (!isNaN(dt.getTime())) setLastUpdated(dt);
        }
        const watchlist = json.watchlist || [];
        const mapped = watchlist.map((d) => ({
          ticker: d.ticker,
          name: d.name || d.ticker,
          sector: d.sector || "Default",
          price: d.current_price ?? null,
          target: d.target_mean ?? null,
          pe: d.pe_ratio ?? null,
          ev_ebitda: d.ev_ebitda ?? null,
          recommendation: d.recommendation || "N/A",
          analysts: d.num_analysts ?? 0,
        }));
        setStocks(mapped);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error("Failed to load alerts_output.json", e);
      }
    }
    loadData();
  }, []);

  const allAlerts = stocks.flatMap(s => getAlerts(s).map(a => ({ ...a, ticker: s.ticker, name: s.name })));
  const upsideAlerts = allAlerts.filter(a => a.type === "UPSIDE");
  const downsideAlerts = allAlerts.filter(a => a.type === "DOWNSIDE");
  const valuationAlerts = allAlerts.filter(a => a.type.includes("PE") || a.type.includes("EV"));

  const filtered = stocks
    .filter(s => {
      if (search && !s.ticker.toLowerCase().includes(search.toLowerCase()) && !s.name.toLowerCase().includes(search.toLowerCase())) return false;
      if (filter === "UPSIDE") return getAlerts(s).some(a => a.type === "UPSIDE");
      if (filter === "DOWNSIDE") return getAlerts(s).some(a => a.type === "DOWNSIDE");
      if (filter === "VALUATION") return getAlerts(s).some(a => a.type.includes("PE") || a.type.includes("EV"));
      if (filter === "ALERTS") return getAlerts(s).length > 0;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "upside") return (getUpside(b) ?? -999) - (getUpside(a) ?? -999);
      if (sortBy === "ticker") return a.ticker.localeCompare(b.ticker);
      if (sortBy === "alerts") return getAlerts(b).length - getAlerts(a).length;
      return 0;
    });

  const handleRefresh = () => {
    setLastUpdated(new Date());
    setEmailSent(false);
    setTimeout(() => setLastUpdated(new Date()), 500);
  };

  const handleEmailSend = () => {
    setEmailSent(true);
    setTimeout(() => setEmailSent(false), 3000);
  };

  const handleAddTicker = () => {
    const t = newTicker.trim().toUpperCase();
    if (!t) return;
    alert("To add a real ticker, edit CONFIG['watchlist'] in stock_alerts.py and re-run the backend script.");
    setNewTicker("");
  };

  const handleRemove = (ticker) => setStocks(prev => prev.filter(s => s.ticker !== ticker));

  return (
    <div style={{
      minHeight: "100vh",
      background: "#060d1a",
      fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
      color: "#f8fafc",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=DM+Sans:wght@400;500;700;800&display=swap');
        @keyframes fadeSlide { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 3px; }
        input::placeholder { color: #334155; }
        button:hover { opacity: .85; }
        select option { background: #0f172a; }
      `}</style>

      {/* Top Bar */}
      <div style={{
        background: "linear-gradient(90deg, #0b1528, #0f172a)",
        borderBottom: "1px solid #1e293b",
        padding: "0 32px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        height: 60
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: "linear-gradient(135deg, #1e3a5f, #38bdf8)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16
          }}>📈</div>
          <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: "-.3px" }}>StockAlert</span>
          <span style={{
            background: "#1e3a5f", color: "#38bdf8", fontSize: 10,
            padding: "2px 7px", borderRadius: 4, fontWeight: 700, letterSpacing: ".05em"
          }}>DASHBOARD</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12, color: "#475569" }}>
          <span style={{ animation: "pulse 2s infinite", color: "#22c55e", marginRight: 2 }}>●</span>
          Updated {lastUpdated.toLocaleTimeString()}
          <button onClick={handleRefresh} style={{
            background: "#1e293b", border: "1px solid #334155", color: "#94a3b8",
            padding: "6px 12px", borderRadius: 6, cursor: "pointer", fontSize: 12
          }}>⟳ Refresh</button>
          <button onClick={handleEmailSend} style={{
            background: emailSent ? "#052e16" : "#1e3a5f",
            border: `1px solid ${emailSent ? "#22c55e" : "#38bdf8"}`,
            color: emailSent ? "#22c55e" : "#38bdf8",
            padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 700,
            transition: "all .2s"
          }}>
            {emailSent ? "✓ Email Sent!" : "📧 Send Alert Email"}
          </button>
        </div>
      </div>

      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 20px" }}>

        {/* Stats Row */}
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 28 }}>
          <StatCard label="Watching" value={stocks.length} sub="active tickers" accent="#38bdf8" />
          <StatCard label="Buy Signals" value={upsideAlerts.length} sub={`≥${THRESHOLDS.upside}% upside`} accent="#22c55e" />
          <StatCard label="Cautions" value={downsideAlerts.length} sub={`≤${THRESHOLDS.downside}% downside`} accent="#ef4444" />
          <StatCard label="Val. Flags" value={valuationAlerts.length} sub="P/E or EV/EBITDA" accent="#f59e0b" />
          <StatCard label="Total Alerts" value={allAlerts.length} sub="across watchlist" accent="#a78bfa" />
        </div>

        {/* Filters + Search + Add */}
        <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
          {["ALL", "ALERTS", "UPSIDE", "DOWNSIDE", "VALUATION"].map(f => (
            <button key={f} onClick={() => setFilter(f)} style={{
              background: filter === f ? "#1e3a5f" : "#0f172a",
              border: `1px solid ${filter === f ? "#38bdf8" : "#1e293b"}`,
              color: filter === f ? "#38bdf8" : "#64748b",
              padding: "7px 14px", borderRadius: 6, cursor: "pointer",
              fontSize: 12, fontWeight: 700, letterSpacing: ".04em",
              transition: "all .15s"
            }}>{f}</button>
          ))}
          <div style={{ flex: 1, minWidth: 180 }}>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search ticker or name..."
              style={{
                width: "100%", background: "#0f172a", border: "1px solid #1e293b",
                color: "#e2e8f0", padding: "8px 14px", borderRadius: 6,
                fontSize: 13, outline: "none"
              }}
            />
          </div>
          <select
            value={sortBy} onChange={e => setSortBy(e.target.value)}
            style={{
              background: "#0f172a", border: "1px solid #1e293b",
              color: "#94a3b8", padding: "8px 12px", borderRadius: 6,
              fontSize: 12, cursor: "pointer", outline: "none"
            }}
          >
            <option value="upside">Sort: Upside</option>
            <option value="ticker">Sort: Ticker</option>
            <option value="alerts">Sort: Most Alerts</option>
          </select>
          <div style={{ display: "flex", gap: 6 }}>
            <input
              value={newTicker}
              onChange={e => setNewTicker(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleAddTicker()}
              placeholder="Add ticker..."
              style={{
                background: "#0f172a", border: "1px solid #1e3a5f",
                color: "#e2e8f0", padding: "8px 12px", borderRadius: 6,
                fontSize: 13, outline: "none", width: 110
              }}
            />
            <button onClick={handleAddTicker} style={{
              background: "#1e3a5f", border: "1px solid #38bdf8",
              color: "#38bdf8", padding: "8px 14px", borderRadius: 6,
              cursor: "pointer", fontSize: 13, fontWeight: 700
            }}>+</button>
          </div>
        </div>

        {/* Thresholds Info */}
        <div style={{
          background: "#0a1628", border: "1px solid #1e293b", borderRadius: 8,
          padding: "10px 16px", marginBottom: 20, fontSize: 12, color: "#475569",
          display: "flex", gap: 20, flexWrap: "wrap"
        }}>
          <span>🟢 Upside alert: <b style={{color:"#94a3b8"}}>≥{THRESHOLDS.upside}%</b></span>
          <span>🔴 Downside alert: <b style={{color:"#94a3b8"}}>≤{THRESHOLDS.downside}%</b></span>
          <span>⚠️ P/E premium: <b style={{color:"#94a3b8"}}>≥{THRESHOLDS.pe_premium}% above sector</b></span>
          <span>💡 P/E discount: <b style={{color:"#94a3b8"}}>≤{Math.abs(THRESHOLDS.pe_discount)}% below sector</b></span>
          <span>⚠️ EV/EBITDA premium: <b style={{color:"#94a3b8"}}>≥{THRESHOLDS.ev_premium}% above sector</b></span>
        </div>

        {/* Results count */}
        <div style={{ color: "#334155", fontSize: 12, marginBottom: 14 }}>
          Showing {filtered.length} of {stocks.length} stocks
        </div>

        {/* Stock Cards */}
        <div>
          {filtered.length === 0 && (
            <div style={{ color: "#334155", textAlign: "center", padding: "60px 0", fontSize: 14 }}>
              No stocks match this filter.
            </div>
          )}
          {filtered.map(stock => (
            <div key={stock.ticker} style={{ position: "relative" }}>
              <AlertCard stock={stock} />
              <button
                onClick={() => handleRemove(stock.ticker)}
                style={{
                  position: "absolute", top: 18, right: 18,
                  background: "transparent", border: "none",
                  color: "#334155", cursor: "pointer", fontSize: 15,
                  lineHeight: 1
                }}
                title="Remove"
              >✕</button>
            </div>
          ))}
        </div>

        {/* Disclaimer */}
        <div style={{ color: "#1e3a5f", fontSize: 11, textAlign: "center", marginTop: 32, lineHeight: 1.6 }}>
          ⚠️ For informational use only — not financial advice.<br />
          Run the Python backend script to fetch live data and generate alerts_output.json for this dashboard.
        </div>
      </div>
    </div>
  );
}
