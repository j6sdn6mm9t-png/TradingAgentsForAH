CREATE TABLE `backtest_runs` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`config_json` text NOT NULL,
	`metrics_json` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE TABLE `portfolio_snapshots` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`as_of` text NOT NULL,
	`total_value` real NOT NULL,
	`cash` real NOT NULL,
	`positions_json` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE TABLE `research_runs` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`run_id` text NOT NULL,
	`symbol` text NOT NULL,
	`as_of` text NOT NULL,
	`rating` text NOT NULL,
	`confidence` real NOT NULL,
	`report_json` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_research_runs_run_id` ON `research_runs` (`run_id`);--> statement-breakpoint
CREATE TABLE `watchlist` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`symbol` text NOT NULL,
	`name` text NOT NULL,
	`market` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_watchlist_symbol` ON `watchlist` (`symbol`);