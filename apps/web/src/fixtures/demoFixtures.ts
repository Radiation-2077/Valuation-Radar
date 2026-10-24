import financialRaw from "./cards/financial-ah.json";

import type { ReportDetailBlock, ReportDetailSection } from "@/api/types";

export type DemoCaseKey = "financial-ah" | "stable" | "cyclical" | "etf";

interface DemoMarket {
  market: string;
  code: string;
  currency: string;
  [key: string]: unknown;
}

export interface DemoCard {
  schema_version: string;
  name: string;
  codes: Record<string, string>;
  asset_type: string;
  path: string;
  model_modules: string[];
  industry: string;
  cycle_stage: string;
  cycle_position: number;
  quality: {
    label: string;
    [key: string]: unknown;
  };
  conclusion: {
    thesis: string;
    [key: string]: unknown;
  };
  markets: DemoMarket[];
  presentation: {
    sections: ReportDetailSection[];
  };
  [key: string]: unknown;
}

export interface DemoCase {
  key: DemoCaseKey;
  label: string;
  description: string;
  card: DemoCard;
}

const baseCard = financialRaw as unknown as DemoCard;

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function remapMarketFields(value: unknown, from: string, to: string): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => remapMarketFields(item, from, to));
  }
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, item]) => {
      if ((key === "market" || key === "scope_market") && item === from) {
        return [key, to];
      }
      return [key, remapMarketFields(item, from, to)];
    }),
  );
}

function singleMarketCard(options: {
  name: string;
  assetType: "stock" | "etf";
  path: "stable" | "cyclical" | "etf";
  module: string;
  moduleTitle: string;
  industry: string;
  market: "A" | "CN";
  code: string;
  thesis: string;
  verdictLabel: string;
  longText?: string;
}): DemoCard {
  const card = clone(baseCard);
  const firstMarket = clone(card.markets[0]);
  firstMarket.market = options.market;
  firstMarket.code = options.code;
  firstMarket.currency = "CNY";
  card.markets = [firstMarket];
  card.codes = { [options.market]: options.code };
  card.name = options.name;
  card.asset_type = options.assetType;
  card.path = options.path;
  card.model_modules = [options.module];
  card.industry = options.industry;
  card.cycle_stage =
    options.path === "cyclical" ? "示例周期中段" : "示例成熟期";
  card.quality.label = "数据完整的示例质地";
  card.conclusion.thesis = options.thesis;
  card.conclusion.verdict = {
    code: options.verdictLabel === "观察" ? "watch" : "accumulate",
    label: options.verdictLabel,
  };

  card.presentation.sections = card.presentation.sections
    .filter(
      (section) =>
        section.role !== "cross_market" &&
        (section.market === "common" || section.market === "A"),
    )
    .map((source) => {
      const section = remapMarketFields(
        clone(source),
        "A",
        options.market,
      ) as ReportDetailSection;
      section.id = section.id?.replace("-a", `-${options.market.toLowerCase()}`);
      if (section.role === "model_analysis") {
        section.module = options.module;
        section.title = options.moduleTitle;
        if (options.longText) {
          const callout = section.blocks.at(-1);
          section.blocks = [
            {
              type: "paragraph",
              text: options.longText,
            },
            ...section.blocks.slice(0, -1),
            callout,
          ] as ReportDetailBlock[];
        }
      }
      return section;
    });
  if (options.path === "cyclical") {
    const cycle = card.presentation.sections.find(
      (section) => section.role === "cycle",
    );
    cycle?.blocks.splice(1, 0, {
      type: "industry_cycle",
      position: card.cycle_position,
      phase: "pullback",
      direction: "down",
    });
  }
  return card;
}

const stable = singleMarketCard({
  name: "示例稳定消费",
  assetType: "stock",
  path: "stable",
  module: "dividend_yield",
  moduleTitle: "股息与增长",
  industry: "稳定消费",
  market: "A",
  code: "600001.SH",
  thesis: "成熟消费业务现金流稳定，示例用于验证稳定增长路径和四档建仓节奏。",
  verdictLabel: "分批买入",
});

const cyclical = singleMarketCard({
  name: "示例周期制造",
  assetType: "stock",
  path: "cyclical",
  module: "normalized_earnings",
  moduleTitle: "正常化盈利与周期位置",
  industry: "周期制造",
  market: "A",
  code: "600002.SH",
  thesis: "示例用于验证周期路径、长文本表格和窄屏布局下的内容稳定性。",
  verdictLabel: "观察",
  longText:
    "这是一段用于布局压力测试的长文本，覆盖行业景气、库存周期、资本开支、价格传导和正常化利润之间的关系。模型必须把新增证据与价格变化分开表达，前端负责换行、折叠和移动端重排，不能因为单个单元格过长而撑坏整个页面。",
});

const etf = singleMarketCard({
  name: "示例宽基ETF",
  assetType: "etf",
  path: "etf",
  module: "index_percentile",
  moduleTitle: "指数估值分位",
  industry: "宽基 ETF",
  market: "CN",
  code: "510300",
  thesis: "示例用于验证 ETF 单市场结构、指数估值分位和定投式建仓计划。",
  verdictLabel: "观察",
});

export const DEMO_CASES: Record<DemoCaseKey, DemoCase> = {
  "financial-ah": {
    key: "financial-ah",
    label: "金融 A/H",
    description: "A/H 分市场、模型分析、溢价环图和全部 canonical block",
    card: clone(baseCard),
  },
  stable: {
    key: "stable",
    label: "稳定增长",
    description: "单市场稳定增长路径与股息收益拆解",
    card: stable,
  },
  cyclical: {
    key: "cyclical",
    label: "周期长文本",
    description: "单市场周期路径，包含长段落和长表格压力测试",
    card: cyclical,
  },
  etf: {
    key: "etf",
    label: "ETF",
    description: "ETF 单市场结构和指数估值模块",
    card: etf,
  },
};

export function isDemoCase(value: string): value is DemoCaseKey {
  return value in DEMO_CASES;
}
