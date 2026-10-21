<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";
import {
  NAlert,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NInput,
  NSpin,
  NSpace,
  NTag,
  NText,
  NTimeline,
  NTimelineItem,
} from "naive-ui";

import { fetchJobDebug } from "@/api/client";
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
        <NTag
          size="small"
          :bordered="false"
          :type="eventType(debugQuery.data.value.job.status)"
        >
          {{ debugQuery.data.value.job.status }} · {{ debugQuery.data.value.job.phase }}
        </NTag>
      </NSpace>

      <NAlert v-if="debugQuery.data.value.job.error" type="error" :bordered="false">
        {{ debugQuery.data.value.job.error }}
      </NAlert>

      <NSpace vertical :size="8">
        <NText strong>事件流</NText>
        <NTimeline v-if="debugQuery.data.value.events.length">
          <NTimelineItem
            v-for="event in debugQuery.data.value.events"
            :key="`${event.at}-${event.phase}-${event.message}`"
            :type="eventType(event.phase)"
            :time="formatDateTime(event.at)"
          >
            {{ event.message }}
          </NTimelineItem>
        </NTimeline>
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
        <NText strong>STDOUT / JSONL</NText>
        <NInput
          v-if="debugQuery.data.value.stdout"
          :value="debugQuery.data.value.stdout"
          type="textarea"
          readonly
          :autosize="{ minRows: 8, maxRows: 18 }"
        />
        <NEmpty v-else size="small" description="暂无 stdout 输出" />
      </NSpace>

      <NSpace vertical :size="8">
        <NText strong>STDERR</NText>
        <NInput
          v-if="debugQuery.data.value.stderr"
          :value="debugQuery.data.value.stderr"
          type="textarea"
          readonly
          :autosize="{ minRows: 5, maxRows: 14 }"
        />
        <NEmpty v-else size="small" description="暂无 stderr 输出" />
      </NSpace>
    </NSpace>
  </NCard>
</template>
