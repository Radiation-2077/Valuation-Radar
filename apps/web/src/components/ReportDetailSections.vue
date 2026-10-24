<script setup lang="ts">
import { NCard, NH2, NSpace, NText } from "naive-ui";
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
  <NSpace class="report-section-stack" vertical :size="20">
    <NCard v-for="section in sections" :key="section.id || section.title">
      <NSpace class="report-section-body" vertical :size="20">
        <NH2>{{ section.title }}</NH2>
        <ReportBlockRenderer :blocks="section.blocks" />
      </NSpace>
    </NCard>
    <NCard v-if="!sections.length">
      <NText depth="3">当前报告没有可用的结构化章节。</NText>
    </NCard>
  </NSpace>
</template>
