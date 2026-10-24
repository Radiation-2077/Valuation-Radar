from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.codex import CodexExecutor, CodexResult
from app.models import (
    AiRun,
    Instrument,
    JobRun,
    Listing,
    MacroObservation,
    QuoteObservation,
    ValuationReport,
)
from app.services.importer import import_candidate_card, validate_card
from app.services.job_events import append_job_event
from app.services.macro import latest_macro_values


class RevaluationExecutor(Protocol):
    def run(
        self,
        cwd: Path,
        prompt: str,
        output_schema: Path,
        manifest_path: Path,
    ) -> CodexResult: ...


def run_valuation_refresh(
    session: Session,
    job: JobRun,
    settings: Settings,
    executor: RevaluationExecutor | None = None,
) -> ValuationReport:
    instrument_id = _instrument_id(job.scope)
    instrument = session.get(Instrument, instrument_id)
    if instrument is None:
        raise ValueError(f"标的 {instrument_id} 不存在")
    if instrument.archived_at is not None:
        raise ValueError(f"标的 {instrument.name} 已归档，不能重新估值")
    _record_job_event(session, job, "valuing", "准备估值目录、上一版数据卡与行情证据")

    staging = settings.staging_dir / f"job-{job.id}" / _safe_name(instrument.name)
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "data").mkdir(parents=True)
    if settings.legacy_common_dir.is_dir():
        shutil.copytree(
            settings.legacy_common_dir,
            staging / "common",
            dirs_exist_ok=True,
        )

    previous_card = _latest_card(session, instrument.id)
    (staging / "previous_card.json").write_text(
        json.dumps(previous_card, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    evidence = _build_evidence(session, instrument)
    (staging / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    schema_path = staging / "manifest.schema.json"
    schema_path.write_text(json.dumps(_manifest_schema(), ensure_ascii=False), encoding="utf-8")
    analysis_date = datetime.now(ZoneInfo(settings.timezone)).date()
    card_name = f"{instrument.name}_{analysis_date.isoformat()}.json"
    prompt = _prompt(
        instrument,
        evidence,
        analysis_date,
        card_name,
        has_previous_card=bool(previous_card),
    )
    prompt_path = staging / "prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    ai_run = AiRun(
        job_id=job.id,
        instrument_id=instrument.id,
        status="running",
        prompt_path=str(prompt_path),
        metadata_json={
            "analysis_date": analysis_date.isoformat(),
            "stdout_path": str(staging / "codex.stdout.jsonl"),
            "stderr_path": str(staging / "codex.stderr.log"),
        },
    )
    session.add(ai_run)
    append_job_event(job, "valuing", "Codex 子进程已启动，等待模型输出")
    session.commit()

    codex = executor or CodexExecutor(
        binary=settings.codex_binary,
        timeout_seconds=settings.codex_timeout_seconds,
        model=settings.codex_model,
    )
    try:
        result = codex.run(
            cwd=staging,
            prompt=prompt,
            output_schema=schema_path,
            manifest_path=staging / "manifest.json",
        )
        _record_result(ai_run, result)
        session.commit()
        _record_job_event(
            session,
            job,
            "validating",
            f"Codex 已退出，退出码 {result.exit_code}，开始校验候选数据卡",
        )
        if result.exit_code != 0:
            message = result.failure or (
                "Codex 执行超时"
                if result.timed_out
                else f"Codex 退出码 {result.exit_code}"
            )
            raise RuntimeError(message)

        manifest_path = staging / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError("缺少 Codex manifest，终止估值")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") not in {"ok", "needs_review"}:
            raise RuntimeError(f"Codex manifest 状态失败：{manifest.get('status')}")
        warnings = manifest.get("warnings") or []
        if warnings:
            raise RuntimeError(f"Codex 报告存在警告，终止估值：{'；'.join(map(str, warnings))}")

        card_path = staging / "data" / card_name
        if not card_path.is_file():
            raise ValueError(f"缺少候选数据卡：{card_name}")
        card = json.loads(card_path.read_text(encoding="utf-8"))
        missing = [str(item) for item in card.get("missing") or []]
        if missing:
            raise RuntimeError(f"候选估值存在缺失数据，终止估值：{'；'.join(missing)}")
        validate_card(card, card_path)
        if card["name"] != instrument.name:
            raise ValueError("候选数据卡标的名与原标的不一致")
        if card["analysis_date"] != analysis_date.isoformat():
            raise ValueError("候选数据卡分析日期不是本次任务日期")

        report = import_candidate_card(session, card_path)
        _record_job_event(session, job, "candidate_ready", "候选数据卡已校验并写入待复核库")
        ai_run.status = "succeeded"
        ai_run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        ai_run.output_path = str(card_path)
        ai_run.metadata_json = {
            **ai_run.metadata_json,
            "report_id": report.id,
        }
        session.commit()
        return report
    except Exception as exc:
        session.rollback()
        failed = session.get(AiRun, ai_run.id)
        if failed is not None:
            failed.status = "rejected"
            failed.finished_at = datetime.now(UTC).replace(tzinfo=None)
            failed.stderr = f"{failed.stderr}\n{exc}".strip()
        failed_job = session.get(JobRun, job.id)
        if failed_job is not None:
            append_job_event(failed_job, failed_job.phase, f"重估失败：{exc}")
        session.commit()
        raise


def _instrument_id(scope: str) -> int:
    prefix, _, value = scope.partition(":")
    if prefix != "instrument" or not value.isdigit():
        raise ValueError(f"无效的重估范围：{scope}")
    return int(value)


def _safe_name(value: str) -> str:
    return "".join(char for char in value if char not in '\\/:*?"<>|').strip() or "instrument"


def _record_job_event(session: Session, job: JobRun, phase: str, message: str) -> None:
    append_job_event(job, phase, message)
    session.commit()


def _latest_card(session: Session, instrument_id: int) -> dict[str, Any]:
    report = session.scalar(
        select(ValuationReport)
        .where(
            ValuationReport.instrument_id == instrument_id,
            ValuationReport.status == "published",
        )
        .order_by(
            ValuationReport.analysis_date.desc(),
            ValuationReport.revision.desc(),
        )
        .limit(1)
    )
    return dict(report.raw_card) if report else {}


def _build_evidence(session: Session, instrument: Instrument) -> dict[str, Any]:
    listings = session.scalars(
        select(Listing).where(Listing.instrument_id == instrument.id)
    ).all()
    listing_ids = [listing.id for listing in listings]
    quotes = (
        session.scalars(
            select(QuoteObservation)
            .where(QuoteObservation.listing_id.in_(listing_ids))
            .order_by(QuoteObservation.observed_at.desc())
        ).all()
        if listing_ids
        else []
    )
    latest_quotes: dict[int, QuoteObservation] = {}
    for quote in quotes:
        latest_quotes.setdefault(quote.listing_id, quote)
    macro_rows = session.scalars(
        select(MacroObservation).order_by(MacroObservation.observed_at.desc())
    ).all()
    return {
        "instrument": {
            "id": instrument.id,
            "name": instrument.name,
            "asset_type": instrument.asset_type,
            "industry": instrument.industry,
        },
        "listings": [
            {
                "market": listing.market,
                "code": listing.code,
                "currency": listing.currency,
                "latest_quote": (
                    {
                        "price": latest_quotes[listing.id].price,
                        "quote_date": latest_quotes[listing.id].quote_date.isoformat(),
                        "pe": latest_quotes[listing.id].pe,
                        "pb": latest_quotes[listing.id].pb,
                        "source": "tencent",
                    }
                    if listing.id in latest_quotes
                    else None
                ),
            }
            for listing in listings
        ],
        "macro": latest_macro_values(session),
        "macro_observations": [
            {
                "key": row.key,
                "value": row.value,
                "as_of": row.as_of.isoformat(),
                "source": row.source,
            }
            for row in macro_rows[:20]
        ],
        "constraints": {
            "missing_data": "任何估值必需数据缺失或联网失败时立即终止，不生成候选估值",
            "source": "优先使用 evidence.json 与本目录 common/ 数据",
            "output": "只输出 schema 1.2 结构化数据卡，排名与 presentation 必须同源同值",
        },
    }


def _prompt(
    instrument: Instrument,
    evidence: dict[str, Any],
    analysis_date: date,
    card_name: str,
    *,
    has_previous_card: bool,
) -> str:
    markets = ", ".join(item["code"] for item in evidence["listings"])
    market_names = {str(item["market"]) for item in evidence["listings"]}
    if not market_names:
        markets = "未提供，请按标的名检索上市代码"
        section_contract = (
            "先确认标的上市市场；若 A/H 两地上市，默认完整调研两个市场，"
            "必须使用 dashboard-a/h、quality/common、cycle/common、"
            "cross_market/common、valuation-a/h、position-a/h、"
            "expected-return-a/h、risks-a/h、conclusion-a/h、"
            "sources/common、disclaimer/common；单市场才使用单市场章节契约。"
        )
    elif {"A", "H"}.issubset(market_names):
        section_contract = (
            "A+H 必须使用 dashboard-a/h、quality/common、cycle/common、"
            "cross_market/common、valuation-a/h、position-a/h、"
            "expected-return-a/h、risks-a/h、conclusion-a/h、"
            "sources/common、disclaimer/common；"
            "cross_market 只比较溢价，禁止出现单市场估值、情景、仓位或收益。"
        )
    elif market_names & {"A", "H"}:
        section_contract = (
            "已给出 A 或 H 单边代码，但仍须核实是否存在另一地上市；"
            "若为 A/H 两地上市，默认完整调研两个市场并使用 A/H 分市场契约；"
            "仅确认单市场时才使用 dashboard、quality、cycle、valuation、"
            "position、expected_return、risks、conclusion、sources、disclaimer。"
        )
    else:
        section_contract = (
            "单市场使用 dashboard、quality、cycle、valuation、position、"
            "expected_return、risks、conclusion、sources、disclaimer。"
        )
    path_hint = (
        f"上一版估值路径：{instrument.path}\n"
        if has_previous_card
        else "这是首次估值，请独立判断 stable/cyclical/financial/etf 路径。\n"
    )
    return f"""使用 value-investing skill 完成一次完整估值。

首先完整读取该 skill 的 SKILL.md 和本次任务需要的方法参考文档，然后只在当前工作目录内操作。

标的：{instrument.name}
市场代码：{markets}
分析日期：{analysis_date.isoformat()}
{path_hint}

证据文件：
- evidence.json：最新行情、宏观数据和任务约束
- previous_card.json：上一版结构化数据卡，仅作对比，不要求保持相同结论
- common/：通用宏观缓存

要求：
1. 按 skill 的方法重新判断质地、产业周期和市场结构，并独立重估。
2. 任何估值必需数据缺失、来源不可访问或无法交叉核验时立即终止，不得生成估算卡。
3. 只生成 schema 1.2 结构化数据卡 data/{card_name}，不要生成单标的 HTML 文件。
4. 数据卡必须包含完整的 presentation.sections；质量章只使用既有两栏 grid：
   左侧五个 scores，右侧只放结果、评价两列表格；不要再重复维度名。
5. 产业周期章开头必须是 industry_lifecycle，stage 只能是导入/爆发期、
   平台增长期、成熟期、衰退期，并同步顶层 cycle_stage。path 为 cyclical 时，
   第二个 block 必须是 industry_cycle，position/phase/direction 同步顶层
   cycle_position 和固定阶段映射；
   非周期行业可以省略第二张图。
6. model_analysis 与 valuation 至少各有一个核心 formula，cross_market 可选；
   质量、产业周期、仓位、预期收益不得出现公式。latex 只写符号公式，
   substitution 单独写数字代入与结果，explanation 用一段自然语言说明符号
   含义和取值依据。
7. 章节契约：{section_contract}
8. 每个 section 的 market 必须与内容一致，禁止把 A/H 价格、仓位或收益混在同一章节。
9. 成功时 manifest.warnings 必须为空；排名字段与 presentation 同源同值并包含完整详情。
10. 不要修改当前目录之外的文件，不要访问生产数据库。
11. 最终 manifest 只报告状态、数据卡路径、核心摘要和警告。
"""


def _manifest_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "data_card_path", "summary", "warnings"],
        "properties": {
            "status": {"type": "string", "enum": ["ok", "needs_review", "failed"]},
            "data_card_path": {"type": "string"},
            "summary": {"type": "string"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
    }


def _record_result(ai_run: AiRun, result: CodexResult) -> None:
    ai_run.cli_version = result.version
    ai_run.exit_code = result.exit_code
    ai_run.output_path = str(result.manifest_path)
    if result.stderr_path.is_file():
        stderr = result.stderr_path.read_text(encoding="utf-8", errors="replace")
        ai_run.stderr = stderr[-20_000:]
    ai_run.metadata_json = {
        **ai_run.metadata_json,
        "stdout_path": str(result.stdout_path),
        "stderr_path": str(result.stderr_path),
        "timed_out": result.timed_out,
    }
