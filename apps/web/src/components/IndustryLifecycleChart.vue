<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  stage: string;
}>();

const stages = [
  { label: "导入/爆发", fullLabel: "导入/爆发期", position: 12.5 },
  { label: "平台增长", fullLabel: "平台增长期", position: 37.5 },
  { label: "成熟", fullLabel: "成熟期", position: 62.5 },
  { label: "衰退", fullLabel: "衰退期", position: 87.5 },
];

const activeIndex = computed(() => {
  const index = stages.findIndex((item) => item.fullLabel === props.stage);
  return index < 0 ? 2 : index;
});

const activeStage = computed(() => stages[activeIndex.value]);
</script>

<template>
  <div
    class="industry-lifecycle-chart"
    role="img"
    :aria-label="`行业生命周期，当前处于${activeStage.fullLabel}`"
    :data-stage="stage"
  >
    <div class="lifecycle-track" />
    <div class="lifecycle-labels">
      <span
        v-for="(item, index) in stages"
        :key="item.label"
        :class="['lifecycle-label', { 'lifecycle-label--active': index === activeIndex }]"
        :data-label="item.label"
      >
        <template v-if="index === activeIndex">
          <span class="lifecycle-callout">当前：{{ activeStage.fullLabel }}</span>
          <i class="lifecycle-marker" aria-hidden="true" />
        </template>
        {{ item.label }}
      </span>
    </div>
  </div>
</template>
