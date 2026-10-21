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
  NTag,
  NText,
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

interface MarketView {
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
  gauges: Record<string, number>;
  expectedReturn: Record<string, number | null>;
  downside: { max_drawdown_pct?: number | null; scenario?: string };
  position: {
    base_pct?: number;
    target_pct?: number;
    cap_pct?: number;
    buy_points?: string;
  };
  verdict: string;
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
    document.title = `${query.data.value.name} · 估值雷达`;
  }
});

const bandType = (band: string): "success" | "info" | "warning" | "error" => {
  if (band === "S") return "success";
  if (band === "A") return "info";
  if (band === "B") return "warning";
  return "error";
};

function currentMarket(data: ValuationDetail): MarketView {
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
    gauges: data.gauges,
    expectedReturn: data.expected_return,
    downside: data.downside,
    position: data.position,
    verdict: data.verdict,
  };
}

const markets = computed<MarketView[]>(() => {
  const data = query.data.value;
  if (!data) return [];
  return [
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
      gauges: market.gauges,
      expectedReturn: market.expected_return,
      downside: market.downside,
      position: market.position,
      verdict: market.verdict,
    })),
  ].sort((left, right) => left.market.localeCompare(right.market));
});

const heroKpis = computed(() => {
  const data = query.data.value;
  if (!data) return [];
  if (markets.value.length > 1) {
    return markets.value.flatMap((market) => [
      {
        label: `${marketLabels[market.market] ?? market.market}现价`,
        value: formatMoney(market.price, market.currency),
        color: undefined,
      },
      {
        label: `${marketLabels[market.market] ?? market.market}合理区间`,
        value: `${formatMoney(market.fairLow, market.currency)}–${formatMoney(market.fairHigh, market.currency)}`,
        color: undefined,
      },
      {
        label: `${marketLabels[market.market] ?? market.market}正常化PE`,
        value: formatNumber(market.pe),
        color: "#57d6b1",
      },
    ]);
  }
  return [
    {
      label: "当前安全边际",
      value: formatPercent(data.effective_safety_margin_pct),
      color: (data.effective_safety_margin_pct ?? 0) < 0 ? "#ee8c78" : "#57d6b1",
    },
    {
      label: "预期年化",
      value: formatPercent(data.expected_return.total),
      color: "#57d6b1",
    },
    {
      label: "悲观回撤",
      value: formatPercent(data.downside.max_drawdown_pct),
      color: "#ee8c78",
    },
    {
      label: "建议目标仓位",
      value: formatPercent(data.position.target_pct, 0),
      color: undefined,
    },
  ];
});

function marketGauges(market: MarketView) {
  return [
    {
      label: "安全边际",
      value: market.gauges.safety_margin ?? 0,
      displayValue: formatPercent(market.safetyMargin),
      color: "#57d6b1",
    },
    {
      label: "估值历史分位",
      value: market.gauges.percentile ?? 0,
      displayValue: formatPercent(market.percentile, 0),
      color: "#80c7ff",
    },
    {
      label: "股息率吸引力",
      value: market.gauges.dividend ?? 0,
      displayValue: formatPercent(market.dividend),
      color: "#e8b86d",
    },
    {
      label: "确定性",
      value: market.gauges.certainty ?? 0,
      displayValue: query.data.value?.conclusion.confidence ?? "—",
      color: "#80c7ff",
    },
  ];
}

function downsideText(market: MarketView): string {
  return market.downside.scenario ?? "未登记具体悲观情景";
}
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
          <NSpace :size="8" :wrap="true">
            <NTag :bordered="false">
              {{ pathLabels[query.data.value.path] ?? query.data.value.path }} /
              {{ query.data.value.industry }}
            </NTag>
            <NTag :bordered="false">
              {{ query.data.value.cycle.stage }}
            </NTag>
          </NSpace>
          <div class="detail-title">
            <NH1>{{ query.data.value.name }}</NH1>
            <NText depth="3">
              {{ markets.map((market) => market.code).join(" / ") }}
            </NText>
          </div>
          <p class="detail-thesis">{{ query.data.value.conclusion.thesis }}</p>
        </div>
        <NCard class="verdict-panel" size="small">
          <NText depth="3">分市场结论</NText>
          <NGrid :cols="markets.length > 1 ? 2 : 1" :x-gap="16" :y-gap="12">
            <NGridItem v-for="market in markets" :key="market.id">
              <NSpace vertical :size="4">
                <NText strong>
                  {{ market.market }} {{ market.verdict }}
                </NText>
                <NTag :type="bandType(query.data.value.score.band)" size="small" :bordered="false">
                  较中枢 {{ formatPercent(market.safetyMargin) }}
                </NTag>
              </NSpace>
            </NGridItem>
          </NGrid>
          <NText depth="3">
            综合 {{ formatNumber(query.data.value.score.total, 1) }} · 置信
            {{ query.data.value.conclusion.confidence }} · 估值
            {{ formatDate(query.data.value.analysis_date) }}
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

      <NGrid responsive="screen" cols="1 s:2 m:3" :x-gap="16" :y-gap="16">
        <NGridItem v-for="kpi in heroKpis" :key="kpi.label">
          <NCard size="small">
            <NStatistic
              :label="kpi.label"
              :value="kpi.value"
              :value-style="{ color: kpi.color }"
            />
          </NCard>
        </NGridItem>
      </NGrid>

      <NCard>
        <NSpace vertical :size="18">
          <NSpace class="card-heading" align="center" justify="space-between">
            <NH2>决策仪表盘</NH2>
            <NTag size="small" :bordered="false">
              质地、周期与确定性为同一资产共用
            </NTag>
          </NSpace>
          <div v-for="market in markets" :key="`gauges-${market.id}`">
            <NText strong>
              {{ marketLabels[market.market] ?? market.market }} {{ market.code }}
            </NText>
            <NGrid responsive="screen" cols="2 m:4" :x-gap="12" :y-gap="12">
              <NGridItem v-for="gauge in marketGauges(market)" :key="`${market.id}-${gauge.label}`">
                <MetricGauge
                  :label="gauge.label"
                  :value="gauge.value"
                  :display-value="gauge.displayValue"
                  :color="gauge.color"
                />
              </NGridItem>
            </NGrid>
            <NText depth="3">
              安全边际按 {{ formatMoney(market.fairMid, market.currency) }} 中枢计算；
              当前 PE {{ formatNumber(market.pe) }}、PB {{ formatNumber(market.pb) }}、
              税后股息率 {{ formatPercent(market.dividend) }}。
            </NText>
          </div>
        </NSpace>
      </NCard>

      <NGrid responsive="screen" cols="1 l:2" :x-gap="16" :y-gap="16">
        <NGridItem>
          <NCard>
            <NSpace vertical :size="16">
              <NH2>标的质地</NH2>
              <NSpace align="center">
                <NTag type="success" :bordered="false">{{ query.data.value.quality.rating }}★</NTag>
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
                <NDescriptionsItem label="分析日期">
                  {{ formatDate(query.data.value.analysis_date) }}
                </NDescriptionsItem>
                <NDescriptionsItem label="行情日期">
                  {{ formatDate(query.data.value.price_date) }}
                </NDescriptionsItem>
              </NDescriptions>
            </NSpace>
          </NCard>
        </NGridItem>
      </NGrid>

      <NGrid responsive="screen" cols="1 l:2" :x-gap="16" :y-gap="16">
        <NGridItem v-for="market in markets" :key="`valuation-${market.id}`">
          <NCard>
            <NSpace vertical :size="16">
              <NSpace class="card-heading" align="center" justify="space-between">
                <NH2>{{ marketLabels[market.market] ?? market.market }}估值</NH2>
                <NTag size="small" :bordered="false">{{ market.code }}</NTag>
              </NSpace>
              <ValuationRangeChart
                :low="market.fairLow"
                :mid="market.fairMid"
                :high="market.fairHigh"
                :price="market.price"
                :currency="market.currency"
              />
              <NGrid cols="2 m:4" :x-gap="12" :y-gap="12">
                <NGridItem>
                  <NStatistic label="现价" :value="formatMoney(market.price, market.currency)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="合理中枢" :value="formatMoney(market.fairMid, market.currency)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="安全边际" :value="formatPercent(market.safetyMargin)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="PE / PB" :value="`${formatNumber(market.pe)} / ${formatNumber(market.pb)}`" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="税后股息率" :value="formatPercent(market.dividend)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="估值分位" :value="formatPercent(market.percentile, 0)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="预期年化" :value="formatPercent(market.expectedReturn.total)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="最大回撤" :value="formatPercent(market.downside.max_drawdown_pct)" />
                </NGridItem>
              </NGrid>
              <NAlert type="warning" :bordered="false" title="悲观情景">
                {{ downsideText(market) }}
              </NAlert>
            </NSpace>
          </NCard>
        </NGridItem>
      </NGrid>

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

      <NGrid responsive="screen" cols="1 l:2" :x-gap="16" :y-gap="16">
        <NGridItem v-for="market in markets" :key="`position-${market.id}`">
          <NCard>
            <NSpace vertical :size="16">
              <NH2>{{ marketLabels[market.market] ?? market.market }}仓位与执行</NH2>
              <NGrid cols="3" :x-gap="12">
                <NGridItem>
                  <NStatistic label="起步" :value="formatPercent(market.position.base_pct, 0)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="目标" :value="formatPercent(market.position.target_pct, 0)" />
                </NGridItem>
                <NGridItem>
                  <NStatistic label="上限" :value="formatPercent(market.position.cap_pct, 0)" />
                </NGridItem>
              </NGrid>
              <NProgress
                type="line"
                :percentage="Math.min(100, (market.position.target_pct ?? 0) * 10)"
                :height="10"
                :show-indicator="false"
              />
              <NText>{{ market.position.buy_points }}</NText>
            </NSpace>
          </NCard>
        </NGridItem>
      </NGrid>

      <NGrid responsive="screen" cols="1 l:2" :x-gap="16" :y-gap="16">
        <NGridItem v-for="market in markets" :key="`return-${market.id}`">
          <NCard>
            <NSpace vertical :size="16">
              <NSpace class="card-heading" align="center" justify="space-between">
                <NH2>{{ marketLabels[market.market] ?? market.market }}预期收益</NH2>
                <NStatistic label="合计年化" :value="formatPercent(market.expectedReturn.total)" />
              </NSpace>
              <ReturnContributionChart :data="market.expectedReturn" />
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
          <NAlert
            v-for="market in markets"
            :key="`conclusion-${market.id}`"
            type="success"
            :bordered="false"
            :title="`${marketLabels[market.market] ?? market.market} ${market.verdict}`"
          >
            {{ formatMoney(market.price, market.currency) }}，较中枢
            {{ formatPercent(market.safetyMargin) }}；目标仓位
            {{ formatPercent(market.position.target_pct, 0) }}。
            {{ market.position.buy_points }}
          </NAlert>
          <NText depth="3">
            综合置信度 {{ query.data.value.conclusion.confidence }}。本页仅用于研究，不构成投资建议。
          </NText>
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
        </NSpace>
      </NCard>
    </NSpace>
  </div>
</template>
