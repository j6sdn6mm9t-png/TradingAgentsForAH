"""Small CLI that keeps framework verification dependency-free."""

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

from .config import ResearchConfig
from .data.akshare_provider import AkShareDataProvider
from .data.demo import DemoDataProvider
from .data.json_file import JsonFileDataProvider
from .report import render_markdown, write_reports
from .workflow import ResearchWorkflow
from .web_sync import sync_research_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ashare-research")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("symbol", help="例如 600519.SH 或 00700.HK")
        command.add_argument("--date", dest="as_of", default=date.today().isoformat())
        command.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
        command.add_argument("--save", action="store_true", help="保存 Markdown 和 JSON 报告")
        command.add_argument("--output-dir", help="覆盖报告输出目录")
        command.add_argument("--data-file", help="使用符合数据契约的 point-in-time JSON 文件")
        command.add_argument(
            "--provider",
            choices=("demo", "akshare"),
            help="覆盖 ASHARE_PROVIDER；AkShare 当日研究会补充 A/H 行情、最新财务与估值",
        )
        command.add_argument(
            "--web-url",
            help="可选：将结果同步到 Web 报告查看器",
        )

    analyze = subparsers.add_parser("analyze", help="研究一个 A/H 股标的")
    add_common_arguments(analyze)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "analyze":
        return 2
    try:
        as_of = date.fromisoformat(args.as_of)
    except ValueError as exc:
        raise SystemExit(f"无效日期 {args.as_of!r}，请使用 YYYY-MM-DD") from exc
    config = ResearchConfig.from_env()
    provider_name = args.provider or config.provider
    if args.data_file:
        provider = JsonFileDataProvider(Path(args.data_file))
    elif provider_name == "demo":
        provider = DemoDataProvider()
    elif provider_name == "akshare":
        provider = AkShareDataProvider()
    else:
        raise SystemExit(
            f"当前已配置 provider={provider_name!r}，但该适配器尚未安装；"
            "请使用 --data-file 或 ASHARE_PROVIDER=demo。"
        )
    state = ResearchWorkflow(provider, config).run(args.symbol, as_of)
    if args.json:
        print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_markdown(state), end="")
    if args.save:
        output_dir = Path(args.output_dir or config.report_dir)
        markdown_path, json_path = write_reports(state, output_dir)
        print(f"\n已保存：{markdown_path}，{json_path}")
    if args.web_url:
        try:
            response = sync_research_run(state, args.web_url)
            print(f"已同步到 Web：research_id={response['item']['id']}")
        except Exception as exc:
            print(f"Web 同步失败：{exc}", file=sys.stderr)
            return 1
    return 0
