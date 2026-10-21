<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { RefreshOutline } from "@vicons/ionicons5";
import {
  NAlert,
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NGrid,
  NGridItem,
  NH1,
  NH2,
  NIcon,
  NList,
  NListItem,
  NProgress,
  NSpace,
  NSpin,
  NStatistic,
  NTable,
  NTag,
  NText,
  NTbody,
  NTd,
  NTh,
  NThead,
  NTr,
  useMessage,
} from "naive-ui";
import { computed, ref, watch, watchEffect } from "vue";

import { fetchValuation, requestRevaluation } from "@/api/client";
import type { ProfileCode, ValuationDetail } from "@/api/types";
import MetricGauge from "@/components/MetricGauge.vue";
import ReturnContributionChart from "@/components/ReturnContributionChart.vue";
import ScoreBars from "@/components/ScoreBars.vue";
import ValuationRangeChart from "@/components/ValuationRangeChart.vue";
import {
  formatDate,
  formatMoney,
  formatNumber,
  formatPercent,
  marketLabels,
  pathLabels,
} from "@/lib/format";

interface CrossMarket {
  id: number;
  market: string;
  code: string;
  currency: string;
  price: number;
  fairLow: number;
  fairMid: number;
  fairHigh: number;
  safetyMargin: number | null;
  pe: number | null;
  pb: number | null;
  dividend: number | null;
  percentile: number | null;
  expectedTotal: number | null;
  maxDrawdown: number | null;
  targetPct: number | null;
  verdict: string;
}

interface CrossRow {
  label: string;
  value: (market: CrossMarket) => string;
}

const props = defineProps<{
  valuationMarketId: number;
  profile: ProfileCode;
}>();
const emit = defineEmits<{
  close: [];
}>();

const queryClient = useQueryClient();
const message = useMessage();
const activeId = ref(props.valuationMarketId);
const valuationId = computed(() => activeId.value);
const profile = computed(() => props.profile);

watch(
  () => props.valuationMarketId,
  (value) => {
    activeId.value = value;
  },
);

const query = useQuery({
  queryKey: computed(() => ["valuation", valuationId.value, profile.value]),
  queryFn: () => fetchValuation(valuationId.value, profile.value),
  enabled: computed(() => Number.isFinite(valuationId.value)),
});
const revaluationMutation = useMutation({
  mutationFn: (instrumentId: number) => requestRevaluation(instrumentId),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    message.success("Codex 重估任务已加入队列，完成后进入待复核");
  },
});

watchEffect(() => {
  if (query.data.value) {
    document.title = `${query.data.value.name} ${query.data.value.market} · 估值雷达`;
  }
});

const bandType = (band: string): "success" | "info" | "warning" | "error" => {
  if (band === "S") return "success";
  if (band === "A") return "info";
  if (band === "B") return "warning";
  return "error";
};

const kpis = computed(() => {
  const data = query.data.value;
  if (!data) return [];
  return [
    {
      label: "当前安全边际",
      value: formatPercent(data.effective_safety_margin_pct),
      negative: (data.effective_safety_margin_pct ?? 0) < 0,
    },
    {
      label: "预期年化",
      value: formatPercent(data.expected_return.total),
      negative: false,
    },
    {
      label: "悲观回撤",
      value: formatPercent(data.downside.max_drawdown_pct),
      negative: true,
    },
    {
      label: "建议目标仓位",
      value: formatPercent(data.position.target_pct, 0),
      negative: false,
    },
  ];
});

const gauges = computed(() => {
  const data = query.data.value;
  if (!data) return [];
  return [
    {
      label: "安全边际",
      value: data.gauges.safety_margin ?? 0,
      displayValue: formatPercent(data.effective_safety_margin_pct),
      color: "#57d6b1",
    },
    {
      label: "估值历史分位",
      value: data.gauges.percentile ?? 0,
      displayValue: formatPercent(data.valuation.percentile, 0),
      color: "#80c7ff",
    },
    {
      label: "股息率吸引力",
      value: data.gauges.dividend ?? 0,
      displayValue: formatPercent(data.valuation.dividend_yield_after_tax),
      color: "#e8b86d",
    },
    {
      label: "确定性",
      value: data.gauges.certainty ?? 0,
      displayValue: data.conclusion.confidence,
      color: "#80c7ff",
    },
  ];
});

function currentMarket(data: ValuationDetail): CrossMarket {
  return {
    id: data.valuation_market_id,
    market: data.market,
    code: data.code,
    currency: data.currency,
    price: data.price,
    fairLow: data.fair_low,
    fairMid: data.fair_mid,
    fairHigh: data.fair_high,
    safetyMargin: data.effective_safety_margin_pct,
    pe: data.valuation.pe,
    pb: data.valuation.pb,
    dividend: data.valuation.dividend_yield_after_tax,
    percentile: data.valuation.percentile,
    expectedTotal: data.expected_return.total,
    maxDrawdown: data.downside.max_drawdown_pct ?? null,
    targetPct: data.position.target_pct ?? null,
    verdict: data.verdict,
  };
}

const crossMarkets = computed<CrossMarket[]>(() => {
  const data = query.data.value;
  if (!data) return [];
  const markets = [
    currentMarket(data),
    ...data.same_company.map((market) => ({
      id: market.valuation_market_id,
      market: market.market,
      code: market.code,
      currency: market.currency,
      price: market.price,
      fairLow: market.fair_low,
      fairMid: market.fair_mid,
      fairHigh: market.fair_high,
      safetyMargin: market.safety_margin_pct,
      pe: market.pe,
      pb: market.pb,
      dividend: market.dividend_yield_after_tax,
      percentile: market.percentile,
      expectedTotal: market.expected_total,
      maxDrawdown: market.max_drawdown_pct,
      targetPct: market.target_pct,
      verdict: market.verdict,
    })),
  ];
  return markets.sort((left, right) => left.market.localeCompare(right.market));
});

const crossRows: CrossRow[] = [
  { label: "现价", value: (market) => formatMoney(market.price, market.currency) },
  {
    label: "合理区间",
    value: (market) =>
      `${formatMoney(market.fairLow, market.currency)} – ${formatMoney(market.fairHigh, market.currency)}`,
  },
  { label: "安全边际", value: (market) => formatPercent(market.safetyMargin) },
  {
    label: "PE / PB",
    value: (market) => `${formatNumber(market.pe)} / ${formatNumber(market.pb)}`,
  },
  { label: "税后股息率", value: (market) => formatPercent(market.dividend) },
  { label: "历史估值分位", value: (market) => formatPercent(market.percentile, 0) },
  { label: "预期年化", value: (market) => formatPercent(market.expectedTotal) },
  { label: "悲观回撤", value: (market) => formatPercent(market.maxDrawdown) },
  { label: "目标仓位", value: (market) => formatPercent(market.targetPct, 0) },
];

const nominalAhPremium = computed(() => {
  const data = query.data.value;
  if (!data) return null;
  const aMarket = crossMarkets.value.find((market) => market.market === "A");
  const hMarket = crossMarkets.value.find((market) => market.market === "H");
  const rawRate = data.macro.hkd_cny;
  const rate = typeof rawRate === "number" ? rawRate : Number(rawRate);
  if (!aMarket || !hMarket || !Number.isFinite(rate) || rate <= 0) return null;
  return (aMarket.price / (hMarket.price * rate) - 1) * 100;
});
</script>

<template>
  <div class="detail-panel">
    <NButton text class="back-link" @click="emit('close')">← 关闭详情</NButton>

    <div v-if="query.isPending.value" class="loading-state">
      <NSpin size="large" />
      <span>正在展开估值分析…</span>
    </div>
    <NAlert v-else-if="query.isError.value" type="error" title="无法读取估值详情">
      <NSpace align="center" justify="space-between">
        <span>{{ query.error.value?.message }}</span>
        <NButton size="small" @click="query.refetch()">重试</NButton>
      </NSpace>
    </NAlert>

    <NSpace v-else-if="query.data.value" vertical :size="20">
      <header class="detail-hero">
        <div class="detail-identity">
          <NTag :bordered="false">
            {{ pathLabels[query.data.value.path] ?? query.data.value.path }} /
            {{ query.data.value.industry }}
          </NTag>
          <div class="detail-title">
            <NH1>{{ query.data.value.name }}</NH1>
            <NTag :bordered="false">
              {{ marketLabels[query.data.value.market] ?? query.data.value.market }}
            </NTag>
            <NText depth="3">{{ query.data.value.code }}</NText>
          </div>
          <p class="detail-thesis">{{ query.data.value.conclusion.thesis }}</p>
        </div>
        <NCard class="verdict-panel" size="small">
          <NText depth="3">当前结论</NText>
          <strong>{{ query.data.value.verdict }}</strong>
          <NSpace class="verdict-meta" align="center">
            <NTag :type="bandType(query.data.value.score.band)" :bordered="false">
              {{ query.data.value.score.band }} 档
            </NTag>
            <NText depth="2">
              综合 {{ formatNumber(query.data.value.score.total, 1) }} · 置信
              {{ query.data.value.conclusion.confidence }}
            </NText>
          </NSpace>
          <NText depth="3">
            估值 {{ formatDate(query.data.value.analysis_date) }} · 行情
            {{ formatDate(query.data.value.price_date) }} · 估值旧
            {{ query.data.value.stale_days }} 天
          </NText>
          <NButton
            class="revalue-button"
            secondary
            :loading="revaluationMutation.isPending.value"
            @click="revaluationMutation.mutate(query.data.value.instrument_id)"
          >
            <template #icon>
              <NIcon :component="RefreshOutline" />
            </template>
            请求 Codex 重新估值
          </NButton>
        </NCard>
      </header>

      <NGrid responsive="screen" cols="1 s:2 l:4" :x-gap="16" :y-gap="16">
        <NGridItem v-for="kpi in kpis" :key="kpi.label">
          <NCard size="small">
            <NStatistic
              :label="kpi.label"
              :value="kpi.value"
              :value-style="{ color: kpi.negative ? '#ee8c78' : undefined }"
            />
          </NCard>
        </NGridItem>
      </NGrid>

      <NCard>
        <NSpace vertical :size="16">
          <NSpace class="card-heading" align="center" justify="space-between">
            <NH2>决策仪表盘</NH2>
            <NTag size="small" :bordered="false">
              {{ marketLabels[query.data.value.market] ?? query.data.value.market }} ·
              同一口径
            </NTag>
          </NSpace>
          <NGrid responsive="screen" cols="2 m:4" :x-gap="12" :y-gap="12">
            <NGridItem v-for="gauge in gauges" :key="gauge.label">
              <MetricGauge
                :label="gauge.label"
                :value="gauge.value"
                :display-value="gauge.displayValue"
                :color="gauge.color"
              />
            </NGridItem>
          </NGrid>
        </NSpace>
      </NCard>

      <NGrid responsive="screen" cols="1 l:2" :x-gap="16" :y-gap="16">
        <NGridItem>
          <NCard>
            <NSpace vertical :size="16">
              <NSpace class="card-heading" align="center" justify="space-between">
                <NH2>价格相对合理区间</NH2>
                <NTag size="small" :bordered="false">
                  基线 {{ formatPercent(query.data.value.safety_margin_pct) }}
                </NTag>
              </NSpace>
              <ValuationRangeChart
                :low="query.data.value.fair_low"
                :mid="query.data.value.fair_mid"
                :high="query.data.value.fair_high"
                :price="query.data.value.price"
                :currency="query.data.value.currency"
              />
              <NGrid cols="2 m:4" :x-gap="12" :y-gap="12">
                <NGridItem>
                  <NStatistic label="合理下限" :value="formatMoney(query.data.value.fair_low, query.data.value.currency)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="合理中枢" :value="formatMoney(query.data.value.fair_mid, query.data.value.currency)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="合理上限" :value="formatMoney(query.data.value.fair_high, query.data.value.currency)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="现值" :value="formatMoney(query.data.value.price, query.data.value.currency)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="PE" :value="formatNumber(query.data.value.valuation.pe)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="PB" :value="formatNumber(query.data.value.valuation.pb)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="税后股息率" :value="formatPercent(query.data.value.valuation.dividend_yield_after_tax)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="估值分位" :value="formatPercent(query.data.value.valuation.percentile, 0)" />
                </NGridItem>
              </NGrid>
            </NSpace>
          </NCard>
        </NGridItem>

        <NGridItem>
          <NCard>
            <NSpace vertical :size="16">
              <NSpace class="card-heading" align="center" justify="space-between">
                <NH2>四维评分拆解</NH2>
                <NTag :type="bandType(query.data.value.score.band)" :bordered="false">
                  {{ query.data.value.score.band }} 档 ·
                  {{ formatNumber(query.data.value.score.total, 1) }}
                </NTag>
              </NSpace>
              <ScoreBars :score="query.data.value.score" />
              <NAlert type="warning" :bordered="false">
                {{
                  query.data.value.risk_flags.includes("依赖估值回归")
                    ? "收益偏依赖估值修复"
                    : "经营收益占比较高"
                }}
              </NAlert>
            </NSpace>
          </NCard>
        </NGridItem>
      </NGrid>

      <NGrid responsive="screen" cols="1 l:2" :x-gap="16" :y-gap="16">
        <NGridItem>
          <NCard>
            <NSpace vertical :size="16">
              <NH2>标的质地</NH2>
              <NSpace align="center">
                <NTag type="success" :bordered="false">
                  {{ query.data.value.quality.rating }}★
                </NTag>
                <NText strong>{{ query.data.value.quality.label }}</NText>
                <NText depth="3">护城河：{{ query.data.value.quality.moat }}</NText>
              </NSpace>
              <NDescriptions :column="1" size="small">
                <NDescriptionsItem label="质地综合分">
                  {{ formatNumber(query.data.value.quality.score, 1) }}
                </NDescriptionsItem>
                <NDescriptionsItem label="质地门槛">
                  {{ query.data.value.quality.gate_pass ? "通过" : query.data.value.quality.gate_reason }}
                </NDescriptionsItem>
                <NDescriptionsItem label="风险标签">
                  {{ query.data.value.risk_flags.join(" / ") || "—" }}
                </NDescriptionsItem>
              </NDescriptions>
            </NSpace>
          </NCard>
        </NGridItem>

        <NGridItem>
          <NCard>
            <NSpace vertical :size="16">
              <NH2>产业周期</NH2>
              <NText>{{ query.data.value.cycle.stage }}</NText>
              <NProgress
                type="line"
                :percentage="query.data.value.cycle.position ?? 0"
                :height="8"
                :show-indicator="false"
              />
              <NSpace justify="space-between">
                <NText depth="3">周期位置</NText>
                <NText>{{ formatNumber(query.data.value.cycle.position, 0) }}</NText>
              </NSpace>
              <NDescriptions :column="1" size="small">
                <NDescriptionsItem label="估值路径">
                  {{ pathLabels[query.data.value.path] ?? query.data.value.path }}
                </NDescriptionsItem>
                <NDescriptionsItem label="市场">
                  {{ marketLabels[query.data.value.market] ?? query.data.value.market }}
                </NDescriptionsItem>
              </NDescriptions>
            </NSpace>
          </NCard>
        </NGridItem>
      </NGrid>

      <NCard v-if="crossMarkets.length > 1">
        <NSpace vertical :size="16">
          <NSpace class="card-heading" align="center" justify="space-between">
            <NH2>同一资产的跨市场对照</NH2>
            <NTag size="small" :bordered="false">A/H 仓位需合并计算</NTag>
          </NSpace>
          <NAlert
            v-if="nominalAhPremium !== null"
            type="info"
            :bordered="false"
            title="名义 A/H 溢价"
          >
            按当前价格与 HKD/CNY 计算：{{ formatPercent(nominalAhPremium) }}。名义溢价包含税负、贴现率、
            市场分割与流动性差异，不能直接当作 A 股高估或 H 股低估；结构性分解见估值口径说明。
          </NAlert>
          <NTable size="small" :bordered="false" :single-line="false">
            <NThead>
              <NTr>
                <NTh>指标</NTh>
                <NTh v-for="market in crossMarkets" :key="market.id">
                  {{ marketLabels[market.market] ?? market.market }} · {{ market.code }}
                </NTh>
              </NTr>
            </NThead>
            <NTbody>
              <NTr v-for="row in crossRows" :key="row.label">
                <NTd>{{ row.label }}</NTd>
                <NTd v-for="market in crossMarkets" :key="`${row.label}-${market.id}`">
                  {{ row.value(market) }}
                </NTd>
              </NTr>
              <NTr>
                <NTd>市场结论</NTd>
                <NTd v-for="market in crossMarkets" :key="`verdict-${market.id}`">
                  {{ market.verdict }}
                </NTd>
              </NTr>
            </NTbody>
          </NTable>
        </NSpace>
      </NCard>

      <NGrid responsive="screen" cols="1 l:2" :x-gap="16" :y-gap="16">
        <NGridItem>
          <NCard>
            <NSpace vertical :size="16">
              <NH2>仓位与执行</NH2>
              <NGrid cols="3" :x-gap="12">
                <NGridItem>
                  <NStatistic label="起步" :value="formatPercent(query.data.value.position.base_pct, 0)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="目标" :value="formatPercent(query.data.value.position.target_pct, 0)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="上限" :value="formatPercent(query.data.value.position.cap_pct, 0)" />
                </NGridItem>
              </NGrid>
              <NProgress
                type="line"
                :percentage="Math.min(100, (query.data.value.position.target_pct ?? 0) * 10)"
                :height="10"
                :show-indicator="false"
              />
              <NText>{{ query.data.value.position.buy_points }}</NText>
              <NAlert type="error" :bordered="false" title="悲观情景">
                {{ formatPercent(query.data.value.downside.max_drawdown_pct) }} ·
                {{ query.data.value.downside.scenario }}
              </NAlert>
            </NSpace>
          </NCard>
        </NGridItem>

        <NGridItem>
          <NCard>
            <NSpace vertical :size="16">
              <NSpace class="card-heading" align="center" justify="space-between">
                <NH2>预期年化来自哪里</NH2>
                <NStatistic label="合计" :value="formatPercent(query.data.value.expected_return.total)" />
              </NSpace>
              <ReturnContributionChart :data="query.data.value.expected_return" />
              <NText depth="3">
                便宜只计一次：安全边际负责估值修复，基础收益只取股息、增长与汇率。
              </NText>
            </NSpace>
          </NCard>
        </NGridItem>
      </NGrid>

      <NCard>
        <NSpace vertical :size="16">
          <NH2>风险提示</NH2>
          <NList>
            <NListItem v-for="risk in query.data.value.risks" :key="risk">{{ risk }}</NListItem>
          </NList>
          <NAlert type="warning" :bordered="false">
            最大回撤为悲观情景估计，不表示发生概率。
          </NAlert>
        </NSpace>
      </NCard>

      <NCard>
        <NSpace vertical :size="16">
          <NH2>关键结论</NH2>
          <NAlert type="success" :bordered="false" title="操作结论">
            {{ query.data.value.verdict }}。{{ query.data.value.conclusion.thesis }}
          </NAlert>
          <NDescriptions :column="1" size="small">
            <NDescriptionsItem label="置信度">
              {{ query.data.value.conclusion.confidence }}
            </NDescriptionsItem>
            <NDescriptionsItem label="分析日期">
              {{ formatDate(query.data.value.analysis_date) }}
            </NDescriptionsItem>
            <NDescriptionsItem label="行情日期">
              {{ formatDate(query.data.value.price_date) }}
            </NDescriptionsItem>
          </NDescriptions>
        </NSpace>
      </NCard>

      <NCard>
        <NSpace vertical :size="16">
          <NH2>数据缺口与口径</NH2>
          <NList v-if="query.data.value.missing.length">
            <NListItem v-for="item in query.data.value.missing" :key="item">{{ item }}</NListItem>
          </NList>
          <NText v-else>当前结构化数据未登记缺失项。</NText>
          <NText>{{ query.data.value.notes }}</NText>
          <NText depth="3">免责声明：本页面仅用于研究，不构成投资建议。</NText>
        </NSpace>
      </NCard>
    </NSpace>
  </div>
</template>
