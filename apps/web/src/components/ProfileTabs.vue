<script setup lang="ts">
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
  <div class="profile-tabs" role="tablist" aria-label="风险偏好">
    <button
      v-for="profile in profiles"
      :key="profile.code"
      class="profile-tab"
      :class="{ active: profile.code === modelValue }"
      type="button"
      role="tab"
      :aria-selected="profile.code === modelValue"
      @click="emit('update:modelValue', profile.code)"
    >
      <span>{{ profile.label }}</span>
      <small>{{ profile.hint }}</small>
    </button>
  </div>
</template>
