<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import {
  NAlert,
  NButton,
  NCard,
  NCollapse,
  NCollapseItem,
  NDescriptions,
  NDescriptionsItem,
  NGrid,
  NGridItem,
  NList,
  NListItem,
  NProgress,
  NSpin,
  NStatistic,
  NTag,
  useMessage,
} from "naive-ui";
import { computed, ref, watch, watchEffect } from "vue";

import { fetchValuation, requestRevaluation } from "@/api/client";
import type { ProfileCode } from "@/api/types";
import ReturnBreakdown from "@/components/ReturnBreakdown.vue";
import ScoreBars from "@/components/ScoreBars.vue";
import {
  formatDate,
  formatMoney,
  formatNumber,
  formatPercent,
  marketLabels,
  pathLabels,
} from "@/lib/format";

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

const fairPosition = computed(() => {
  const data = query.data.value;
  if (!data) return 0;
  const minimum = Math.min(data.fair_low, data.price);
  const maximum = Math.max(data.fair_high, data.price);
  return maximum === minimum ? 50 : ((data.price - minimum) / (maximum - minimum)) * 100;
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
      <div class="alert-content">
        <span>{{ query.error.value?.message }}</span>
        <NButton size="small" @click="query.refetch()">重试</NButton>
      </div>
    </NAlert>

    <template v-else-if="query.data.value">
      <header class="detail-hero">
        <div class="detail-identity">
          <p class="eyebrow">
            {{ pathLabels[query.data.value.path] ?? query.data.value.path }} /
            {{ query.data.value.industry }}
          </p>
          <div class="detail-title">
            <h1>{{ query.data.value.name }}</h1>
            <NTag :bordered="false">
              {{ marketLabels[query.data.value.market] ?? query.data.value.market }}
            </NTag>
            <small>{{ query.data.value.code }}</small>
          </div>
          <p class="detail-thesis">{{ query.data.value.conclusion.thesis }}</p>
        </div>
        <NCard class="verdict-panel" size="small" :bordered="false">
          <span class="verdict-label">当前结论</span>
          <strong>{{ query.data.value.verdict }}</strong>
          <div class="verdict-meta">
            <NTag :type="bandType(query.data.value.score.band)" :bordered="false">
              {{ query.data.value.score.band }} 档
            </NTag>
            <span>综合 {{ formatNumber(query.data.value.score.total, 1) }}</span>
            <span>置信 {{ query.data.value.conclusion.confidence }}</span>
          </div>
          <small>
            估值 {{ formatDate(query.data.value.analysis_date) }} · 行情
            {{ formatDate(query.data.value.price_date) }}
          </small>
          <NButton
            class="revalue-button"
            secondary
            :loading="revaluationMutation.isPending.value"
            @click="revaluationMutation.mutate(query.data.value.instrument_id)"
          >
            请求 Codex 重新估值
          </NButton>
        </NCard>
      </header>

      <NGrid responsive="screen" class="kpi-grid" cols="1 s:2 l:4" :x-gap="12" :y-gap="12">
        <NGridItem v-for="kpi in kpis" :key="kpi.label">
          <NCard size="small" :bordered="false">
            <NStatistic
              :label="kpi.label"
              :value="kpi.value"
              :value-style="{ color: kpi.negative ? '#ee8c78' : undefined }"
            />
          </NCard>
        </NGridItem>
      </NGrid>

      <NGrid responsive="screen" class="detail-grid" cols="1 l:2" :x-gap="12" :y-gap="12">
        <NGridItem>
          <NCard class="fair-panel" :bordered="false">
            <div class="panel-heading">
              <div><p class="eyebrow">VALUATION BAND</p><h2>价格相对合理区间</h2></div>
              <NTag size="small" :bordered="false">
                基线 {{ formatPercent(query.data.value.safety_margin_pct) }}
              </NTag>
            </div>
            <NProgress
              type="line"
              :percentage="fairPosition"
              :height="10"
              :show-indicator="false"
            />
            <NGrid cols="3" :x-gap="12">
              <NGridItem>
                <NStatistic label="合理下限" :value="formatMoney(query.data.value.fair_low, query.data.value.currency)" />
              </NGridItem>
              <NGridItem>
                <NStatistic label="合理中枢" :value="formatMoney(query.data.value.fair_mid, query.data.value.currency)" />
              </NGridItem>
              <NGridItem>
                <NStatistic label="合理上限" :value="formatMoney(query.data.value.fair_high, query.data.value.currency)" />
              </NGridItem>
            </NGrid>
            <NGrid class="valuation-metrics" cols="2 m:4" :x-gap="12" :y-gap="12">
              <NGridItem>
                <NStatistic label="PE" :value="formatNumber(query.data.value.valuation.pe)" />
              </NGridItem>
              <NGridItem>
                <NStatistic label="PB" :value="formatNumber(query.data.value.valuation.pb)" />
              </NGridItem>
              <NGridItem>
                <NStatistic
                  label="税后股息率"
                  :value="formatPercent(query.data.value.valuation.dividend_yield_after_tax)"
                />
              </NGridItem>
              <NGridItem>
                <NStatistic
                  label="估值分位"
                  :value="formatPercent(query.data.value.valuation.percentile, 0)"
                />
              </NGridItem>
            </NGrid>
          </NCard>
        </NGridItem>
        <NGridItem>
          <NCard class="score-panel" :bordered="false">
            <div class="panel-heading">
              <div><p class="eyebrow">FOUR DIMENSIONS</p><h2>评分拆解</h2></div>
              <NTag size="small" :bordered="false">
                {{ formatPercent(query.data.value.score.total) }}
              </NTag>
            </div>
            <ScoreBars :score="query.data.value.score" />
            <NAlert class="score-note" :bordered="false" type="warning">
              {{
                query.data.value.risk_flags.includes("依赖估值回归")
                  ? "收益偏依赖估值修复"
                  : "经营收益占比较高"
              }}
            </NAlert>
          </NCard>
        </NGridItem>
        <NGridItem>
          <NCard class="return-panel" :bordered="false">
            <div class="panel-heading">
              <div><p class="eyebrow">EXPECTED RETURN</p><h2>预期年化来自哪里</h2></div>
            </div>
            <ReturnBreakdown :data="query.data.value.expected_return" />
            <p class="panel-footnote">
              便宜只计一次：安全边际负责估值修复，基础收益只取股息、增长与汇率。
            </p>
          </NCard>
        </NGridItem>
        <NGridItem>
          <NCard class="quality-panel" :bordered="false">
            <div class="panel-heading">
              <div><p class="eyebrow">BUSINESS QUALITY</p><h2>质地与周期</h2></div>
            </div>
            <div class="quality-score">
              <NTag type="success" :bordered="false">{{ query.data.value.quality.rating }}★</NTag>
              <div>
                <strong>{{ query.data.value.quality.label }}</strong>
                <small>
                  护城河：{{ query.data.value.quality.moat }} · 质地分
                  {{ query.data.value.quality.score }}
                </small>
              </div>
            </div>
            <NDescriptions :column="1" size="small" :bordered="false">
              <NDescriptionsItem label="产业周期">{{ query.data.value.cycle.stage }}</NDescriptionsItem>
              <NDescriptionsItem label="周期位置">
                {{ formatNumber(query.data.value.cycle.position, 0) }}
              </NDescriptionsItem>
              <NDescriptionsItem label="估值路径">
                {{ pathLabels[query.data.value.path] ?? query.data.value.path }}
              </NDescriptionsItem>
              <NDescriptionsItem label="质地门槛">
                {{ query.data.value.quality.gate_pass ? "通过" : query.data.value.quality.gate_reason }}
              </NDescriptionsItem>
            </NDescriptions>
          </NCard>
        </NGridItem>
      </NGrid>

      <NGrid responsive="screen" class="lower-grid" cols="1 l:3" :x-gap="12" :y-gap="12">
        <NGridItem>
          <NCard class="position-panel" :bordered="false">
            <div class="panel-heading">
              <div><p class="eyebrow">POSITION PLAN</p><h2>仓位与执行</h2></div>
            </div>
            <NGrid cols="3" :x-gap="8">
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
            <p class="buy-points">{{ query.data.value.position.buy_points }}</p>
            <NAlert type="error" :bordered="false" title="悲观情景">
              {{ formatPercent(query.data.value.downside.max_drawdown_pct) }}
              {{ query.data.value.downside.scenario }}
            </NAlert>
          </NCard>
        </NGridItem>
        <NGridItem>
          <NCard class="risk-panel" :bordered="false">
            <div class="panel-heading">
              <div><p class="eyebrow">RISK MAP</p><h2>关键风险与反证</h2></div>
            </div>
            <NList>
              <NListItem v-for="risk in query.data.value.risks" :key="risk">{{ risk }}</NListItem>
            </NList>
          </NCard>
        </NGridItem>
        <NGridItem v-if="query.data.value.same_company.length">
          <NCard class="same-company-panel" :bordered="false">
            <div class="panel-heading">
              <div><p class="eyebrow">CROSS MARKET</p><h2>同一资产的其他市场</h2></div>
            </div>
            <NButton
              v-for="other in query.data.value.same_company"
              :key="other.valuation_market_id"
              block
              secondary
              class="same-company-button"
              @click="activeId = other.valuation_market_id"
            >
              {{ other.market }} · {{ other.code }} · {{ formatMoney(other.price, other.currency) }}
              · 安全边际 {{ formatPercent(other.safety_margin_pct) }}
            </NButton>
            <p class="panel-footnote">两地同持属于同一公司敞口，仓位需要合并计算。</p>
          </NCard>
        </NGridItem>
      </NGrid>

      <NCollapse v-if="query.data.value.missing.length" class="missing-section">
        <NCollapseItem :title="`数据缺口（${query.data.value.missing.length}）`" name="missing">
          <NList>
            <NListItem v-for="item in query.data.value.missing" :key="item">{{ item }}</NListItem>
          </NList>
        </NCollapseItem>
      </NCollapse>

      <NCard class="source-section" :bordered="false">
        <p class="eyebrow">TRACEABILITY</p>
        <h2>口径与来源</h2>
        <p>{{ query.data.value.notes }}</p>
      </NCard>
    </template>
  </div>
</template>
