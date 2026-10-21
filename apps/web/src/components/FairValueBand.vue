<script setup lang="ts">
import { computed } from "vue";

import { formatMoney } from "@/lib/format";

const props = defineProps<{
  low: number;
  mid: number;
  high: number;
  price: number;
  currency: string;
}>();

const domain = computed(() => {
  const min = Math.min(props.low, props.price) * 0.92;
  const max = Math.max(props.high, props.price) * 1.04;
  return { min, max, span: max - min || 1 };
});

function position(value: number): number {
  return Math.max(0, Math.min(100, ((value - domain.value.min) / domain.value.span) * 100));
}

const rangeStyle = computed(() => ({
  left: `${position(props.low)}%`,
  right: `${100 - position(props.high)}%`,
}));

const midStyle = computed(() => ({ left: `${position(props.mid)}%` }));
const priceStyle = computed(() => ({ left: `${position(props.price)}%` }));
</script>

<template>
  <div class="fair-band">
    <div class="fair-track">
      <span class="fair-range" :style="rangeStyle"></span>
      <i class="fair-mid" :style="midStyle"></i>
      <span class="fair-price" :style="priceStyle">
        <small>现价</small>
        <strong>{{ formatMoney(price, currency) }}</strong>
      </span>
    </div>
    <div class="fair-labels">
      <span>{{ formatMoney(low, currency) }}</span>
      <strong>中枢 {{ formatMoney(mid, currency) }}</strong>
      <span>{{ formatMoney(high, currency) }}</span>
    </div>
  </div>
</template>
