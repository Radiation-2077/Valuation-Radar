<script setup lang="ts">
import { NCard, NH2, NText } from "naive-ui";
import { computed } from "vue";

import type { ReportDetailSection } from "@/api/types";
import ReportBlockRenderer from "@/components/ReportBlockRenderer.vue";
import { visibleReportSections } from "@/lib/report-detail";

const props = defineProps<{
  sections: ReportDetailSection[];
  market: string;
}>();

const sections = computed(() => visibleReportSections(props.sections, props.market));
</script>

<template>
  <NCard v-for="section in sections" :key="section.title">
    <NH2>{{ section.title }}</NH2>
    <ReportBlockRenderer :blocks="section.blocks" />
  </NCard>
  <NCard v-if="!sections.length">
    <NText depth="3">当前报告没有可用的结构化章节。</NText>
  </NCard>
</template>
