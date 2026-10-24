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
    <NSpace vertical :size="10">
      <MathFormula display-mode :latex="blockText(block, 'latex')" />
      <div v-if="blockText(block, 'substitution')" class="formula-substitution">
        <strong>代入数据</strong>
        <MathFormula display-mode :latex="blockText(block, 'substitution')" />
      </div>
      <NText v-if="blockText(block, 'caption')" depth="3">
        <RichText :text="blockText(block, 'caption')" />
      </NText>
      <div v-if="blockText(block, 'explanation')" class="formula-explanation">
        <RichText :text="blockText(block, 'explanation')" />
      </div>
    </NSpace>
  </NCard>
</template>
