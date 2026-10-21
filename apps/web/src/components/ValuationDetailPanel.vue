<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { RefreshOutline } from "@vicons/ionicons5";
import {
  NAlert,
  NButton,
  NCard,
  NEllipsis,
  NGrid,
  NGridItem,
  NH1,
  NIcon,
  NList,
  NListItem,
  NSpace,
  NSpin,
  NStatistic,
  NTag,
  NText,
  useMessage,
} from "naive-ui";
import { computed, ref, watch, watchEffect } from "vue";

import { fetchValuation, requestRevaluation } from "@/api/client";
import type { ProfileCode } from "@/api/types";
import ReportDetailSections from "@/components/ReportDetailSections.vue";
import {
  formatDate,
  formatMoney,
  formatMoneyRange,
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
    { label: "现价", value: formatMoney(data.price, data.currency) },
    {
      label: "合理区间",
      value: formatMoneyRange(data.fair_low, data.fair_high, data.currency),
    },
    { label: "中性目标价", value: formatMoney(data.fair_mid, data.currency) },
    {
      label: "正常化 PE / PB",
      value: `${formatNumber(data.valuation.pe)} / ${formatNumber(data.valuation.pb)}`,
    },
    { label: "税后股息率", value: formatPercent(data.valuation.dividend_yield_after_tax) },
    { label: "目标仓位", value: formatPercent(data.position.target_pct, 0) },
  ];
});

const reportSections = computed(() => query.data.value?.report_detail.sections ?? []);
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
            <NTag :bordered="false">{{ query.data.value.cycle.stage }}</NTag>
          </NSpace>
          <div class="detail-title">
            <NH1>{{ query.data.value.name }}</NH1>
            <NTag :bordered="false">
              {{ marketLabels[query.data.value.market] ?? query.data.value.market }}
            </NTag>
            <NText depth="3">{{ query.data.value.code }}</NText>
          </div>
          <NEllipsis class="detail-thesis" :line-clamp="3" tooltip>
            {{ query.data.value.conclusion.thesis }}
          </NEllipsis>
        </div>
        <NCard class="verdict-panel" size="small">
          <NText depth="3">结论</NText>
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
            {{ formatDate(query.data.value.price_date) }} · 较中枢
            {{ formatPercent(query.data.value.effective_safety_margin_pct) }}
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

      <NGrid responsive="screen" cols="2 m:3 l:6" :x-gap="16" :y-gap="16">
        <NGridItem v-for="kpi in kpis" :key="kpi.label">
          <NCard size="small">
            <NStatistic :label="kpi.label" :value="kpi.value" />
          </NCard>
        </NGridItem>
      </NGrid>

      <ReportDetailSections
        v-if="reportSections.length"
        :sections="reportSections"
        :market="query.data.value.market"
      />
      <NAlert v-else type="warning" title="暂无结构化章节">
        该报告尚未完成结构化迁移，请重新运行估值或导入最新数据卡。
      </NAlert>

      <NCard v-if="query.data.value.missing.length">
        <NSpace vertical :size="12">
          <NText strong>结构化数据缺口</NText>
          <NList>
            <NListItem v-for="item in query.data.value.missing" :key="item">{{ item }}</NListItem>
          </NList>
        </NSpace>
      </NCard>
    </NSpace>
  </div>
</template>
