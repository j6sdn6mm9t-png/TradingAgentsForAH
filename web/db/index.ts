import { env } from "cloudflare:workers";
import { drizzle } from "drizzle-orm/d1";
import * as schema from "./schema";

export function getDb() {
  if (!env.DB) throw new Error("Cloudflare D1 binding `DB` is unavailable");
  return drizzle(env.DB, { schema });
}

export async function ensureSchema() {
  if (!env.DB) throw new Error("Cloudflare D1 binding `DB` is unavailable");
  await env.DB.batch([
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS watchlist (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT NOT NULL,
      name TEXT NOT NULL,
      market TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )`),
    env.DB.prepare("CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_symbol ON watchlist(symbol)"),
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS research_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL,
      symbol TEXT NOT NULL,
      as_of TEXT NOT NULL,
      rating TEXT NOT NULL,
      confidence REAL NOT NULL,
      report_json TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )`),
    env.DB.prepare("CREATE UNIQUE INDEX IF NOT EXISTS idx_research_runs_run_id ON research_runs(run_id)"),
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS portfolio_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      as_of TEXT NOT NULL,
      total_value REAL NOT NULL,
      cash REAL NOT NULL,
      positions_json TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )`),
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS backtest_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      config_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )`),
  ]);
}
