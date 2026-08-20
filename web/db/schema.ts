import { sql } from "drizzle-orm";
import { integer, real, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";

export const watchlist = sqliteTable("watchlist", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  symbol: text("symbol").notNull(),
  name: text("name").notNull(),
  market: text("market").notNull(),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => [uniqueIndex("idx_watchlist_symbol").on(table.symbol)]);

export const researchRuns = sqliteTable("research_runs", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  runId: text("run_id").notNull(),
  symbol: text("symbol").notNull(),
  asOf: text("as_of").notNull(),
  rating: text("rating").notNull(),
  confidence: real("confidence").notNull(),
  reportJson: text("report_json").notNull(),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => [
  uniqueIndex("idx_research_runs_run_id").on(table.runId),
]);

export const portfolioSnapshots = sqliteTable("portfolio_snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  asOf: text("as_of").notNull(),
  totalValue: real("total_value").notNull(),
  cash: real("cash").notNull(),
  positionsJson: text("positions_json").notNull(),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});

export const backtestRuns = sqliteTable("backtest_runs", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  name: text("name").notNull(),
  configJson: text("config_json").notNull(),
  metricsJson: text("metrics_json").notNull(),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});
