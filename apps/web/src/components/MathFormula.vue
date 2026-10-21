<script setup lang="ts">
import katex from "katex";
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    latex: string;
    displayMode?: boolean;
  }>(),
  {
    displayMode: false,
  },
);

const rendered = computed(() =>
  katex.renderToString(props.latex, {
    displayMode: props.displayMode,
    throwOnError: false,
    strict: "ignore",
    trust: false,
  }),
);
</script>

<template>
  <span
    :class="['math-formula', { 'math-formula--display': displayMode }]"
    v-html="rendered"
  />
</template>
