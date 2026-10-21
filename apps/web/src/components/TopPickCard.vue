<script setup lang="ts">
import { NCard, NEllipsis, NStatistic, NTag } from "naive-ui";

import type { RankingItem } from "@/api/types";
import { formatPercent } from "@/lib/format";

defineProps<{
  item: RankingItem;
}>();

const emit = defineEmits<{
  select: [id: number];
}>();

const bandType = (band: string): "success" | "info" | "warning" | "error" => {
  if (band === "S") return "success";
  if (band === "A") return "info";
  if (band === "B") return "warning";
  return "error";
};
</script>

<template>
  <NCard
    :class="['top-card', `rank-${item.rank}`]"
    hoverable
    role="button"
    tabindex="0"
    @click="emit('select', item.valuation_market_id)"
    @keydown.enter="emit('select', item.valuation_market_id)"
  >
    <span class="top-rank">0{{ item.rank }}</span>
    <NTag :type="bandType(item.score.band)" size="small" :bordered="false">
      {{ item.score.band }} 档
    </NTag>
    <div class="top-card-heading">
      <div>
        <h3>{{ item.name }}</h3>
        <p>{{ item.market }} · {{ item.code }}</p>
      </div>
      <strong class="top-score">{{ formatPercent(item.score.total, 1).replace("%", "") }}</strong>
    </div>
    <div class="top-metrics">
      <NStatistic label="安全边际" :value="formatPercent(item.safety_margin_pct)" />
      <NStatistic label="预期年化" :value="formatPercent(item.expected_return.total)" />
      <NStatistic label="最大回撤" :value="formatPercent(item.max_drawdown_pct)" />
    </div>
    <NEllipsis class="top-thesis" :line-clamp="4" tooltip>
      {{ item.thesis }}
    </NEllipsis>
    <NTag size="small" :bordered="false" type="success">{{ item.verdict }}</NTag>
  </NCard>
</template>
