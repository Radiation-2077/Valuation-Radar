<script setup lang="ts">
import { useMutation } from "@tanstack/vue-query";
import {
  NAlert,
  NButton,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  NSpace,
  useMessage,
} from "naive-ui";
import { ref, watch } from "vue";

import { createInstrument } from "@/api/client";
import type {
  InstrumentCreatePayload,
  InstrumentCreateResult,
} from "@/api/types";

const props = defineProps<{
  show: boolean;
}>();
const emit = defineEmits<{
  "update:show": [value: boolean];
  created: [value: InstrumentCreateResult];
}>();

const message = useMessage();
const name = ref("");
const code = ref("");
const assetType = ref<"stock" | "etf">("stock");
const error = ref("");
const mutation = useMutation({
  mutationFn: (payload: InstrumentCreatePayload) => createInstrument(payload),
  onSuccess: (result) => {
    message.success(
      `已添加 ${result.name}${result.code ? `（${result.code}）` : ""}，Codex 任务 #${result.job_id} 已排队`,
    );
    emit("created", result);
    emit("update:show", false);
  },
  onError: (reason: unknown) => {
    error.value = reason instanceof Error ? reason.message : String(reason);
  },
});

watch(
  () => props.show,
  (value) => {
    if (!value) return;
    error.value = "";
    mutation.reset();
  },
);

function submit() {
  error.value = "";
  const trimmedName = name.value.trim();
  const trimmedCode = code.value.trim();
  if (!trimmedName) {
    error.value = "请填写标的名称";
    return;
  }
  mutation.mutate({
    name: trimmedName,
    code: trimmedCode || undefined,
    asset_type: assetType.value,
  });
}
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    title="添加标的并请求 Codex 估值"
    style="width: min(520px, calc(100vw - 32px))"
    :mask-closable="!mutation.isPending.value"
    :closable="!mutation.isPending.value"
    @update:show="emit('update:show', $event)"
  >
    <NSpace vertical :size="16">
      <NAlert type="info" :bordered="false">
        添加后会立即创建估值任务。Codex 完成并通过严格校验后，结果进入待复核区。
      </NAlert>
      <NFormItem label="标的名称" required>
        <NInput
          v-model:value="name"
          placeholder="例如：招商银行"
          :disabled="mutation.isPending.value"
          @keyup.enter="submit"
        />
      </NFormItem>
      <NFormItem label="证券代码（可选）">
        <NInput
          v-model:value="code"
          placeholder="不记得可留空：600036.SH、sh600036、00700.HK"
          :disabled="mutation.isPending.value"
          @keyup.enter="submit"
        />
      </NFormItem>
      <NText depth="3">
        代码留空时由 Codex 按名称查询；两地上市默认完整调研 A、H 两个市场。
      </NText>
      <NFormItem label="资产类型" required>
        <NSelect
          v-model:value="assetType"
          :options="[
            { label: '股票', value: 'stock' },
            { label: 'ETF', value: 'etf' },
          ]"
          :disabled="mutation.isPending.value"
        />
      </NFormItem>
      <NAlert v-if="error" type="error" :bordered="false">{{ error }}</NAlert>
      <NSpace justify="end">
        <NButton
          :disabled="mutation.isPending.value"
          @click="emit('update:show', false)"
        >
          取消
        </NButton>
        <NButton
          type="primary"
          :loading="mutation.isPending.value"
          @click="submit"
        >
          添加并开始估值
        </NButton>
      </NSpace>
    </NSpace>
  </NModal>
</template>
