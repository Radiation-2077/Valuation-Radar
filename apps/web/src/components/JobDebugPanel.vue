<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";
import {
  NAlert,
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NSpin,
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  NText,
  NTimeline,
  NTimelineItem,
} from "naive-ui";
import { computed, ref } from "vue";

import { fetchJobDebug } from "@/api/client";
import { formatCodexJsonl } from "@/lib/debug-output";
import { formatDateTime } from "@/lib/format";

const props = defineProps<{
  jobId: number;
}>();

const debugQuery = useQuery({
  queryKey: ["job-debug", props.jobId],
  queryFn: () => fetchJobDebug(props.jobId),
  refetchInterval: (query) =>
    ["queued", "running"].includes(query.state.data?.job.status ?? "") ? 1_500 : false,
});
const readableOutput = computed(() =>
  formatCodexJsonl(debugQuery.data.value?.stdout ?? ""),
);
const manualRefreshing = ref(false);

async function refreshDebug() {
  manualRefreshing.value = true;
  try {
    await debugQuery.refetch();
  } finally {
    manualRefreshing.value = false;
  }
}

function eventType(status: string): "default" | "success" | "error" | "info" | "warning" {
  if (status === "failed" || status === "rejected") return "error";
  if (status === "cancelled") return "warning";
  if (status === "succeeded" || status === "completed") return "success";
  if (status === "running") return "info";
  return "default";
}
</script>

<template>
  <NCard size="small" :bordered="false">
    <div v-if="debugQuery.isPending.value">
      <NSpin size="small" />
    </div>
    <NAlert v-else-if="debugQuery.isError.value" type="error" title="Debug 信息读取失败">
      {{ debugQuery.error.value?.message }}
    </NAlert>
    <NSpace v-else-if="debugQuery.data.value" vertical :size="16">
      <NSpace align="center" justify="space-between">
        <NText strong>任务 #{{ debugQuery.data.value.job.id }} Debug</NText>
        <NSpace align="center">
          <NButton
            size="tiny"
            secondary
            :loading="manualRefreshing"
            @click="refreshDebug"
          >
            刷新 Debug
          </NButton>
          <NTag
            size="small"
            :bordered="false"
            :type="eventType(debugQuery.data.value.job.status)"
          >
            {{ debugQuery.data.value.job.status }} · {{ debugQuery.data.value.job.phase }}
          </NTag>
        </NSpace>
      </NSpace>

      <NAlert v-if="debugQuery.data.value.job.error" type="error" :bordered="false">
        {{ debugQuery.data.value.job.error }}
      </NAlert>

      <NSpace vertical :size="8">
        <NText strong>事件流</NText>
        <div v-if="debugQuery.data.value.events.length" class="debug-events">
          <NTimeline>
            <NTimelineItem
              v-for="event in debugQuery.data.value.events"
              :key="`${event.at}-${event.phase}-${event.message}`"
              :type="eventType(event.phase)"
              :time="formatDateTime(event.at)"
            >
              {{ event.message }}
            </NTimelineItem>
          </NTimeline>
        </div>
        <NEmpty v-else size="small" description="暂无结构化事件" />
      </NSpace>

      <NCard
        v-for="run in debugQuery.data.value.ai_runs"
        :key="run.id"
        size="small"
        :bordered="false"
      >
        <NSpace vertical :size="10">
          <NSpace align="center" justify="space-between">
            <NText strong>Codex 运行 #{{ run.id }}</NText>
            <NTag size="small" :bordered="false" :type="eventType(run.status)">
              {{ run.status }}
            </NTag>
          </NSpace>
          <NDescriptions :column="2" size="small" label-placement="top">
            <NDescriptionsItem label="CLI">
              {{ run.cli_version || "—" }}
            </NDescriptionsItem>
            <NDescriptionsItem label="退出码">
              {{ run.exit_code ?? "运行中" }}
            </NDescriptionsItem>
          </NDescriptions>
        </NSpace>
      </NCard>

      <NSpace vertical :size="8">
        <NText strong>Codex 实时输出</NText>
        <NTabs v-if="debugQuery.data.value.stdout" type="line" :animated="false">
          <NTabPane name="readable" tab="可读输出">
            <pre class="debug-log" aria-label="Codex 可读输出">{{ readableOutput || "正在等待可读事件…" }}</pre>
          </NTabPane>
          <NTabPane name="raw" tab="原始 JSONL">
            <pre class="debug-log" aria-label="Codex 原始 JSONL">{{ debugQuery.data.value.stdout }}</pre>
          </NTabPane>
        </NTabs>
        <NEmpty v-else size="small" description="暂无 stdout 输出" />
      </NSpace>

      <NSpace vertical :size="8">
        <NText strong>STDERR</NText>
        <pre
          v-if="debugQuery.data.value.stderr"
          class="debug-log debug-log--stderr"
          aria-label="Codex STDERR"
        >{{ debugQuery.data.value.stderr }}</pre>
        <NEmpty v-else size="small" description="暂无 stderr 输出" />
      </NSpace>
    </NSpace>
  </NCard>
</template>
