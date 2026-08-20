"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type Tone = "good" | "neutral" | "warn";

type WatchItem = {
  id?: number;
  symbol: string;
  name: string;
  market: string;
  quality: string;
  valuation: string;
  pricedIn: string;
  tone: Tone;
};

type ResearchRun = {
  symbol: string;
  report?: {
    synthesis?: { company_quality?: string };
    valuation?: { view?: string; pricing_status?: string };
    snapshot?: { name?: string };
  } | null;
};

const initialWatchlist: WatchItem[] = [
  { symbol: "600519.SH", name: "贵州茅台", market: "A股", quality: "待研究", valuation: "待估", pricedIn: "待判断", tone: "neutral" },
  { symbol: "00700.HK", name: "腾讯控股", market: "港股", quality: "待研究", valuation: "待估", pricedIn: "待判断", tone: "neutral" },
  { symbol: "300750.SZ", name: "宁德时代", market: "A股", quality: "待研究", valuation: "待估", pricedIn: "待判断", tone: "neutral" },
  { symbol: "03690.HK", name: "美团-W", market: "港股", quality: "待研究", valuation: "待估", pricedIn: "待判断", tone: "neutral" },
];

function normalizeRow(row: { id: number; symbol: string; name: string; market: string }): WatchItem {
  const sample = initialWatchlist.find((item) => item.symbol === row.symbol);
  return sample ? { ...sample, id: row.id } : {
    ...row,
    quality: "待研究",
    valuation: "待估",
    pricedIn: "待判断",
    tone: "neutral",
  };
}

function applyResearch(items: WatchItem[], runs: ResearchRun[]) {
  const latest = new Map(runs.map((run) => [run.symbol, run]));
  const qualityLabels: Record<string, string> = {
    excellent: "优秀",
    good: "良好",
    mixed: "一般",
    weak: "较弱",
    insufficient_data: "证据不足",
  };
  const valuationLabels: Record<string, string> = {
    attractive: "有吸引力",
    reasonable: "合理",
    demanding: "偏贵",
    excessive: "显著透支",
    insufficient_data: "无法可靠估值",
  };
  const pricingLabels: Record<string, string> = {
    under_reflected: "尚未充分反映",
    partly_reflected: "部分反映",
    largely_reflected: "大致充分反映",
    over_reflected: "过度反映",
    uncertain: "证据不足",
  };
  return items.map((item) => {
    const run = latest.get(item.symbol);
    if (!run?.report) return item;
    const quality = run.report.synthesis?.company_quality || "insufficient_data";
    const valuation = run.report.valuation?.view || "insufficient_data";
    const pricedIn = run.report.valuation?.pricing_status || "uncertain";
    const tone: Tone = quality === "weak" || valuation === "excessive"
      ? "warn"
      : quality === "excellent" || quality === "good"
        ? "good"
        : "neutral";
    return {
      ...item,
      name: run.report.snapshot?.name || item.name,
      quality: qualityLabels[quality] || quality,
      valuation: valuationLabels[valuation] || valuation,
      pricedIn: pricingLabels[pricedIn] || pricedIn,
      tone,
    };
  });
}

export default function DashboardClient() {
  const [watchlist, setWatchlist] = useState(initialWatchlist);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("原型数据 · 等待首次同步");
  const [researchCount, setResearchCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch("/api/watchlist").then((response) => response.ok ? response.json() : { items: [] }),
      fetch("/api/research").then((response) => response.ok ? response.json() : { items: [] }),
    ]).then(([watchPayload, researchPayload]: [
      { items: Array<{ id: number; symbol: string; name: string; market: string }> },
      { items: ResearchRun[] },
    ]) => {
      if (!cancelled) {
        const base = watchPayload.items.length > 0 ? watchPayload.items.map(normalizeRow) : initialWatchlist;
        setWatchlist(applyResearch(base, researchPayload.items));
        setResearchCount(researchPayload.items.length);
        if (watchPayload.items.length || researchPayload.items.length) {
          setMessage(`已载入 ${watchPayload.items.length} 个观察标的与 ${researchPayload.items.length} 次公司研究`);
        }
      }
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  const visibleRows = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return watchlist;
    return watchlist.filter((item) =>
      `${item.symbol} ${item.name} ${item.market}`.toLowerCase().includes(keyword)
    );
  }, [query, watchlist]);

  const valuedCount = watchlist.filter((item) => !["待估", "无法可靠估值"].includes(item.valuation)).length;
  const evidenceGapCount = watchlist.filter((item) => item.quality === "证据不足" || item.valuation === "无法可靠估值").length;

  async function addToWatchlist(event: FormEvent) {
    event.preventDefault();
    const symbol = query.trim().toUpperCase();
    if (!symbol) {
      setMessage("请先输入股票代码，例如 600519.SH 或 00700.HK");
      return;
    }
    const market = symbol.endsWith(".HK") || /^\d{5}$/.test(symbol) ? "港股" : "A股";
    try {
      const response = await fetch("/api/watchlist", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ symbol, name: symbol, market }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "保存失败");
      setWatchlist((items) => [normalizeRow(payload.item), ...items.filter((item) => item.symbol !== payload.item.symbol)]);
      setMessage(`${payload.item.symbol} 已加入观察池，等待公司研究`);
      setQuery("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "观察池暂不可写");
    }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">衡</span><span>衡策</span></div>
        <nav aria-label="主导航">
          <a className="nav-item active" href="#overview"><span>◫</span> 公司研究总览</a>
          <a className="nav-item" href="#research"><span>⌁</span> 企业质量与增长</a>
          <a className="nav-item" href="#valuation"><span>◎</span> 估值与安全边际</a>
          <a className="nav-item" href="#evidence"><span>▤</span> 证据与复核</a>
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" /> 研究模式
          <strong>公司自适应</strong>
          <small>角色、KPI 与估值方法按公司选择</small>
        </div>
      </aside>

      <section className="workspace" id="overview">
        <header className="topbar">
          <div><p className="eyebrow">BUSINESS · GROWTH · EXPECTATIONS · VALUE</p><h1>公司研究总览</h1></div>
          <form className="header-actions" onSubmit={addToWatchlist}>
            <label className="search"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} aria-label="搜索股票" placeholder="A 股或港股代码 / 名称" /></label>
            <button className="primary-button" type="submit">＋ 加入观察池</button>
          </form>
        </header>

        <div className="notice" role="status">
          <div><strong>系统状态</strong><span>{message}</span></div>
          <span className="notice-tag">A + H 全市场</span>
        </div>

        <section className="metrics" aria-label="研究摘要">
          <article className="metric-card"><span>跟踪公司</span><strong>{watchlist.length}</strong><small>按商业模式分别研究</small></article>
          <article className="metric-card"><span>已同步研究</span><strong>{researchCount}</strong><small>保留证据与时点</small></article>
          <article className="metric-card"><span>已有估值锚</span><strong>{valuedCount}</strong><small>可生成公司特定价格区间</small></article>
          <article className="metric-card accent-card"><span>关键证据缺口</span><strong>{evidenceGapCount}</strong><small>不以通用倍数补齐</small></article>
        </section>

        <section className="content-grid" id="research">
          <article className="panel wide-panel">
            <div className="panel-title"><div><p className="eyebrow">COMPANY-SPECIFIC RESEARCH</p><h2>公司研究状态</h2></div><span className="row-count">{visibleRows.length} 个标的</span></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>公司</th><th>市场</th><th>企业质量</th><th>估值状态</th><th>市场计价</th></tr></thead>
                <tbody>
                  {visibleRows.map((stock) => (
                    <tr key={stock.symbol}>
                      <td><strong>{stock.name}</strong><small>{stock.symbol}</small></td>
                      <td><span className="market-pill">{stock.market}</span></td>
                      <td><span className={`rating ${stock.tone}`}>{stock.quality}</span></td>
                      <td>{stock.valuation}</td>
                      <td>{stock.pricedIn}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article className="panel strategy-panel">
            <div className="panel-title"><div><p className="eyebrow">RESEARCH BLUEPRINT</p><h2>研究原则</h2></div></div>
            <h3>先理解公司，再选择指标</h3>
            <p className="muted">从商业模式和价值驱动出发，动态选择 KPI、研究周期、专业角色、可比公司与估值方法。</p>
            <div className="weights"><div><span>商业模式</span><b>因公司而异</b></div><div><span>增长与质量</span><b>因阶段而异</b></div><div><span>估值与预期</span><b>交叉验证</b></div></div>
            <div className="strategy-footer"><span>研究周期</span><strong>跟随业务兑现周期</strong></div>
          </article>
        </section>

        <section className="operations-grid" id="valuation">
          <article className="panel operation-panel">
            <div className="panel-title"><div><p className="eyebrow">INTEGRATED REPORT</p><h2>一体化公司报告</h2></div><span className="module-ready">围绕主要矛盾</span></div>
            <p className="muted module-note">报告依次回答商业模式、盈利引擎、增长势头、有效可比、股价计价程度、动态安全边际、价格区间与证伪条件，不展示角色流水账。</p>
          </article>
          <article className="panel operation-panel" id="evidence">
            <div className="panel-title"><div><p className="eyebrow">EVIDENCE FIRST</p><h2>证据与估值纪律</h2></div><span className="module-ready">拒绝虚假精确</span></div>
            <p className="muted module-note">缺少正常化盈利、现金流或情景假设时，明确保留价格区间缺口；同业只有在真正可比并能改变结论时才进入报告。</p>
          </article>
        </section>

        <footer>公司研究与估值辅助系统 · 不构成投资建议</footer>
      </section>
    </main>
  );
}
