<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";
import {
  NAlert,
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NGrid,
  NGridItem,
  NScrollbar,
  NSpin,
  NSpace,
  NTag,
  NText,
  NTimeline,
  NTimelineItem,
  type ScrollbarInst,
} from "naive-ui";
import { computed, nextTick, ref, watch } from "vue";

import { fetchJobDebug } from "@/api/client";
import type { AiRunDebug, CodexMilestone, TokenUsage } from "@/api/types";
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
const manualRefreshing = ref(false);
const codexEvents = ref<CodexMilestone[]>([]);
const codexScrollbar = ref<ScrollbarInst | null>(null);
const isCodexJob = computed(
  () => debugQuery.data.value?.job.job_type === "valuation_refresh",
);
const marketErrors = computed(() => {
  const errors = debugQuery.data.value?.job.details.errors;
  return Array.isArray(errors)
    ? errors.filter((item): item is string => typeof item === "string")
    : [];
});

watch(
  () => props.jobId,
  () => {
    codexEvents.value = [];
  },
  { immediate: true },
);

watch(
  () => debugQuery.data.value?.codex_events ?? [],
  async (incoming) => {
    const seen = new Set(
      codexEvents.value.map((event) => `${event.kind}\u0000${event.message}`),
    );
    for (const event of incoming) {
      const fingerprint = `${event.kind}\u0000${event.message}`;
      if (seen.has(fingerprint)) continue;
      codexEvents.value.push({
        ...event,
        sequence: codexEvents.value.length + 1,
      });
      seen.add(fingerprint);
    }
    await nextTick();
    codexScrollbar.value?.scrollTo({ top: 999_999 });
  },
  { immediate: true },
);

async function refreshDebug() {
  manualRefreshing.value = true;
  try {
    await debugQuery.refetch();
  } finally {
    manualRefreshing.value = false;
  }
}

function eventType(status: string): "default" | "success" | "error" | "info" | "warning" {
  if (status === "failed" || status === "rejected" || status === "error") return "error";
  if (status === "cancelled") return "warning";
  if (status === "succeeded" || status === "completed") return "success";
  if (status === "running" || status === "running_step") return "info";
  if (status === "success") return "success";
  if (status === "milestone") return "default";
  return "default";
}

function detailMetric(key: string): string {
  const value = debugQuery.data.value?.job.details[key];
  if (key === "latest_quote_at" && typeof value === "string") {
    return formatDateTime(value);
  }
  if (key === "ranking_reused" && typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (typeof value === "number" || typeof value === "string") {
    return String(value);
  }
  return "—";
}

function tokenCount(
  run: AiRunDebug,
  key: keyof TokenUsage,
): string {
  const value = run.token_usage?.[key];
  return typeof value === "number" ? value.toLocaleString("zh-CN") : "—";
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

      <NAlert
        type="info"
        :title="isCodexJob ? 'Codex 当前动作' : '当前动作'"
        :bordered="false"
      >
        {{ debugQuery.data.value.current_action }}
      </NAlert>

      <NGrid class="debug-streams" responsive="screen" cols="1 l:2" :x-gap="16" :y-gap="16">
        <NGridItem>
          <NSpace vertical :size="8">
            <NText strong>任务事件流</NText>
            <NScrollbar
              v-if="debugQuery.data.value.events.length"
              class="debug-events debug-events--task"
              :x-scrollable="false"
            >
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
            </NScrollbar>
            <NEmpty v-else size="small" description="暂无结构化事件" />
          </NSpace>
        </NGridItem>
        <NGridItem v-if="isCodexJob">
          <NSpace vertical :size="8">
            <NText strong>Codex 事件流</NText>
            <NScrollbar
              v-if="codexEvents.length"
              ref="codexScrollbar"
              class="debug-events debug-events--codex"
              :x-scrollable="false"
            >
              <NTimeline>
                <NTimelineItem
                  v-for="event in codexEvents"
                  :key="event.sequence"
                  :type="eventType(event.kind)"
                >
                  {{ event.message }}
                </NTimelineItem>
              </NTimeline>
            </NScrollbar>
            <NEmpty v-else size="small" description="暂无 Codex milestone" />
          </NSpace>
        </NGridItem>
        <NGridItem v-else>
          <NSpace vertical :size="8">
            <NText strong>刷新结果</NText>
            <NDescriptions :column="1" size="small" label-placement="left">
              <NDescriptionsItem label="覆盖标的">
                {{ detailMetric("listings") }}
              </NDescriptionsItem>
              <NDescriptionsItem label="有效行情">
                {{ detailMetric("quotes_fetched") }}
              </NDescriptionsItem>
              <NDescriptionsItem label="新增快照">
                {{ detailMetric("quotes_saved") }}
              </NDescriptionsItem>
              <NDescriptionsItem label="未变化">
                {{ detailMetric("quotes_unchanged") }}
              </NDescriptionsItem>
              <NDescriptionsItem label="宏观记录">
                {{ detailMetric("macro_observations") }}
              </NDescriptionsItem>
              <NDescriptionsItem label="排名重算">
                {{ detailMetric("ranking_runs") }}
              </NDescriptionsItem>
              <NDescriptionsItem label="最新行情">
                {{ detailMetric("latest_quote_at") }}
              </NDescriptionsItem>
            </NDescriptions>
            <NAlert v-if="marketErrors.length" type="warning" :bordered="false">
              {{ marketErrors.join("；") }}
            </NAlert>
          </NSpace>
        </NGridItem>
      </NGrid>

      <template v-if="isCodexJob">
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
              <NDescriptionsItem label="输入 Token">
                {{ tokenCount(run, "input_tokens") }}
              </NDescriptionsItem>
              <NDescriptionsItem label="缓存输入">
                {{ tokenCount(run, "cached_input_tokens") }}
              </NDescriptionsItem>
              <NDescriptionsItem label="输出 Token">
                {{ tokenCount(run, "output_tokens") }}
              </NDescriptionsItem>
              <NDescriptionsItem label="推理 Token">
                {{ tokenCount(run, "reasoning_output_tokens") }}
              </NDescriptionsItem>
            </NDescriptions>
          </NSpace>
        </NCard>
      </template>
    </NSpace>
  </NCard>
</template>
