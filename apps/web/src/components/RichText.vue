<script setup lang="ts">
import { computed } from "vue";

import MathFormula from "@/components/MathFormula.vue";
import { parseInlineRichText } from "@/lib/report-rich-text";

const props = defineProps<{
  text: string;
}>();

const segments = computed(() => parseInlineRichText(props.text));
</script>

<template>
  <template v-for="(segment, index) in segments" :key="`${segment.type}-${index}`">
    <strong v-if="segment.type === 'strong'">{{ segment.value }}</strong>
    <code v-else-if="segment.type === 'code'">{{ segment.value }}</code>
    <MathFormula
      v-else-if="segment.type === 'inline_math'"
      :latex="segment.value"
    />
    <template v-else>{{ segment.value }}</template>
  </template>
</template>
