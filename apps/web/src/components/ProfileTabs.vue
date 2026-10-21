<script setup lang="ts">
import { NTabPane, NTabs } from "naive-ui";

import type { ProfileCode } from "@/api/types";

defineProps<{
  modelValue: ProfileCode;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: ProfileCode];
}>();

const profiles: Array<{ code: ProfileCode; label: string }> = [
  { code: "conservative", label: "稳健保守" },
  { code: "balanced", label: "均衡" },
  { code: "aggressive", label: "进取" },
];
</script>

<template>
  <NTabs
    type="line"
    animated
    :value="modelValue"
    :pane-wrapper-style="{ display: 'none' }"
    @update:value="(value: string) => emit('update:modelValue', value as ProfileCode)"
  >
    <NTabPane
      v-for="profile in profiles"
      :key="profile.code"
      :name="profile.code"
      :tab="profile.label"
    >
      <template #tab>{{ profile.label }}</template>
    </NTabPane>
  </NTabs>
</template>
