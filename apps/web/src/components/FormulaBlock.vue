<script setup lang="ts">
import { NCard, NSpace, NText } from "naive-ui";

import type { ReportDetailBlock } from "@/api/types";
import MathFormula from "@/components/MathFormula.vue";
import RichText from "@/components/RichText.vue";
import { blockText } from "@/lib/report-detail";

defineProps<{
  block: ReportDetailBlock;
}>();
</script>

<template>
  <NCard size="small" :bordered="false">
    <NSpace vertical align="center" :size="8">
      <MathFormula display-mode :latex="blockText(block, 'latex')" />
      <NText v-if="blockText(block, 'caption')" depth="3">
        <RichText :text="blockText(block, 'caption')" />
      </NText>
    </NSpace>
  </NCard>
</template>
