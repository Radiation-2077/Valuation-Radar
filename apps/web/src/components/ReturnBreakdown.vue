<script setup lang="ts">
import { NProgress, NStatistic } from "naive-ui";
import { computed } from "vue";

import { formatPercent } from "@/lib/format";

const props = defineProps<{
  data: Record<string, number | null>;
}>();

const items = computed(() =>
  [
    ["股息", "dividend"],
    ["盈利增长", "growth"],
    ["估值修复", "valuation"],
    ["汇率", "fx"],
  ].map(([label, key]) => ({ label, value: props.data[key] ?? 0 })),
);

const maximum = computed(() =>
  Math.max(10, ...items.value.map((item) => Math.abs(item.value))),
);
</script>

<template>
  <div class="return-breakdown">
    <div v-for="item in items" :key="item.label" class="return-row">
      <span>{{ item.label }}</span>
      <NProgress
        type="line"
        :percentage="(Math.abs(item.value) / maximum) * 100"
        :height="6"
        :show-indicator="false"
        :color="item.value < 0 ? '#ee8c78' : '#80c7ff'"
        rail-color="rgba(158, 190, 210, 0.10)"
      />
      <strong :class="{ negative: item.value < 0 }">{{ formatPercent(item.value) }}</strong>
    </div>
    <NStatistic class="return-total" label="合计年化" :value="formatPercent(data.total)" />
  </div>
</template>
