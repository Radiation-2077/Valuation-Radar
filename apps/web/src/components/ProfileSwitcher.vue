<script setup lang="ts">
import { NButton, NButtonGroup } from "naive-ui";

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
  <NButtonGroup
    class="profile-switcher"
    size="medium"
    role="group"
    aria-label="风险偏好"
  >
    <NButton
      v-for="profile in profiles"
      :key="profile.code"
      :type="modelValue === profile.code ? 'primary' : 'default'"
      :secondary="modelValue !== profile.code"
      :aria-pressed="modelValue === profile.code"
      @click="emit('update:modelValue', profile.code)"
    >
      {{ profile.label }}
    </NButton>
  </NButtonGroup>
</template>
