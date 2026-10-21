<script setup lang="ts">
import { NCard, NGrid, NGridItem, NStatistic } from "naive-ui";

import type { Freshness } from "@/api/types";
import { formatDate, formatDateTime } from "@/lib/format";

defineProps<{
  freshness: Freshness;
  counts: Record<string, number>;
}>();
</script>

<template>
  <NCard class="status-card" :bordered="false" size="small">
    <NGrid responsive="screen" cols="1 s:2 m:4" :x-gap="20" :y-gap="12">
      <NGridItem>
        <NStatistic label="排名计算" :value="formatDateTime(freshness.ranking_as_of)" />
      </NGridItem>
      <NGridItem>
        <NStatistic label="最新估值" :value="formatDate(freshness.latest_analysis_date)" />
      </NGridItem>
      <NGridItem>
        <NStatistic label="最新行情" :value="formatDate(freshness.latest_price_date)" />
      </NGridItem>
      <NGridItem>
        <NStatistic label="排序单元" :value="counts.all ?? 0" />
      </NGridItem>
    </NGrid>
  </NCard>
</template>
