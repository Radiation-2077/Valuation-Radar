<script setup lang="ts">
import { NRadioButton, NRadioGroup } from "naive-ui";

import type { ProfileCode } from "@/api/types";

defineProps<{
  modelValue: ProfileCode;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: ProfileCode];
}>();

const profiles: Array<{ code: ProfileCode; label: string; hint: string }> = [
  { code: "conservative", label: "稳健保守", hint: "风险与确定性优先" },
  { code: "balanced", label: "均衡", hint: "默认基准" },
  { code: "aggressive", label: "进取", hint: "基础收益优先" },
];
</script>

<template>
  <NRadioGroup
    :value="modelValue"
    name="risk-profile"
    class="profile-tabs"
    @update:value="(value: ProfileCode) => emit('update:modelValue', value)"
  >
    <NRadioButton v-for="profile in profiles" :key="profile.code" :value="profile.code">
      <span>{{ profile.label }}</span>
      <small>{{ profile.hint }}</small>
    </NRadioButton>
  </NRadioGroup>
</template>
