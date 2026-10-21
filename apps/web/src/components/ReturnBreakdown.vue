<script setup lang="ts">
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
      <div class="return-track">
        <i
          :class="{ negative: item.value < 0 }"
          :style="{ width: `${(Math.abs(item.value) / maximum) * 100}%` }"
        ></i>
      </div>
      <strong :class="{ negative: item.value < 0 }">{{ formatPercent(item.value) }}</strong>
    </div>
    <div class="return-total">
      <span>合计年化</span>
      <strong>{{ formatPercent(data.total) }}</strong>
    </div>
  </div>
</template>
