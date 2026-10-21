<script setup lang="ts">
import { NList, NListItem } from "naive-ui";
import { computed } from "vue";

import type { ReportDetailBlock } from "@/api/types";
import RichText from "@/components/RichText.vue";

const props = defineProps<{
  block: ReportDetailBlock;
}>();

const items = computed(() => {
  const value = props.block.items;
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object" && typeof item.text === "string") {
        return item.text;
      }
      return "";
    })
    .filter(Boolean);
});
</script>

<template>
  <NList>
    <NListItem v-for="(item, index) in items" :key="`${index}-${item}`">
      <RichText :text="item" />
    </NListItem>
  </NList>
</template>
