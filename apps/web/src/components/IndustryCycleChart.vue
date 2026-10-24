<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  position: number;
  phase?: string;
  direction?: string;
}>();

const phaseLabels = {
  recovery: "低谷回暖",
  upswing: "景气上行",
  pullback: "高位回落",
  downswing: "下行探底",
} as const;

const normalizedPosition = computed(() =>
  Math.max(0, Math.min(100, Number.isFinite(props.position) ? props.position : 0)),
);

const phaseLabel = computed(
  () =>
    phaseLabels[props.phase as keyof typeof phaseLabels] ?? "状态未判定",
);
const directionLabel = computed(() => {
  if (props.direction === "up") return "上行";
  if (props.direction === "down") return "下行";
  return "未判定";
});
const directionDisplay = computed(() =>
  props.direction === "up"
    ? "↑ 上行"
    : props.direction === "down"
      ? "↓ 下行"
      : "方向未判定",
);
const currentStatus = computed(() =>
  props.direction === "up"
    ? `↑ ${phaseLabel.value}`
    : props.direction === "down"
      ? `↓ ${phaseLabel.value}`
      : phaseLabel.value,
);
const markerX = computed(() => normalizedPosition.value * 10);
const markerY = computed(
  () =>
    130 -
    Math.sin(((normalizedPosition.value - 25) / 100) * Math.PI * 2) *
      90,
);
const calloutX = computed(() =>
  Math.max(62, Math.min(938, markerX.value)),
);
const calloutTop = computed(() =>
  Math.max(46, Math.min(204, markerY.value - 42)),
);
const curvePoints = computed(() =>
  Array.from({ length: 101 }, (_, index) => {
    const x = index * 10;
    const y = 130 - Math.sin(((index - 25) / 100) * Math.PI * 2) * 90;
    return `${x},${y}`;
  }).join(" "),
);
</script>

<template>
  <div
    class="industry-cycle-chart"
    role="img"
    :aria-label="`行业景气周期，当前${phaseLabel}，方向${directionLabel}`"
    :data-position="normalizedPosition"
    :data-phase="phase || 'unknown'"
    :data-direction="direction || 'unknown'"
  >
    <div class="cycle-chart-head">
      <span>行业周期位置</span>
      <strong>{{ directionDisplay }} · {{ phaseLabel }}</strong>
    </div>
    <div class="cycle-plot">
      <span class="cycle-extreme cycle-extreme--peak">顶峰</span>
      <span class="cycle-extreme cycle-extreme--trough">低谷</span>
      <div
        class="cycle-current-callout"
        :style="{
          left: `${calloutX / 10}%`,
          top: `${calloutTop}px`,
        }"
      >
        当前：{{ currentStatus }}
      </div>
      <svg
        class="industry-cycle-curve"
        viewBox="0 0 1000 260"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="cycle-peak-trough" x1="0" y1="0" x2="0" y2="1">
            <stop class="cycle-stop cycle-stop--peak" offset="0%" />
            <stop class="cycle-stop cycle-stop--trough" offset="100%" />
          </linearGradient>
        </defs>
        <polyline
          class="cycle-curve"
          :points="curvePoints"
          vector-effect="non-scaling-stroke"
        />
        <line
          class="cycle-current-guide"
          :x1="markerX"
          y1="28"
          :x2="markerX"
          y2="248"
          vector-effect="non-scaling-stroke"
        />
        <circle
          class="cycle-current-point"
          :cx="markerX"
          :cy="markerY"
          r="7"
          vector-effect="non-scaling-stroke"
        />
      </svg>
    </div>
  </div>
</template>
