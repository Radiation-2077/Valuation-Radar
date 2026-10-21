<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NEmpty,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NH1,
  NH2,
  NP,
  NSelect,
  NSpace,
  NSpin,
  NStatistic,
  NSwitch,
  NTag,
  NText,
  NTimePicker,
  useMessage,
  type DataTableColumns,
} from "naive-ui";
import { computed, h, reactive, watch } from "vue";
import { useRouter } from "vue-router";

import {
  createRefreshJob,
  decideReview,
  fetchJobs,
  fetchReviews,
  fetchSchedule,
  updateSchedule,
} from "@/api/client";
import type { Job, Schedule, SchedulePatch } from "@/api/types";
import { formatDateTime } from "@/lib/format";

const queryClient = useQueryClient();
const router = useRouter();
const message = useMessage();
const scheduleQuery = useQuery({ queryKey: ["schedule"], queryFn: fetchSchedule });
const jobsQuery = useQuery({
  queryKey: ["jobs"],
  queryFn: fetchJobs,
  refetchInterval: 3_000,
});
const reviewsQuery = useQuery({
  queryKey: ["reviews"],
  queryFn: fetchReviews,
  refetchInterval: 5_000,
});

const form = reactive<SchedulePatch>({
  enabled: true,
  frequency: "trading_daily",
  run_time: "18:30",
  calendar_mode: "CN",
  stale_after_days: 7,
});

watch(
  () => scheduleQuery.data.value,
  (schedule?: Schedule) => {
    if (!schedule) return;
    Object.assign(form, {
      enabled: schedule.enabled,
      frequency: schedule.frequency,
      run_time: schedule.run_time,
      calendar_mode: schedule.calendar_mode,
      stale_after_days: schedule.stale_after_days,
    });
  },
  { immediate: true },
);

const saveMutation = useMutation({
  mutationFn: updateSchedule,
  onSuccess: async (schedule) => {
    queryClient.setQueryData(["schedule"], schedule);
    await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    message.success("更新设置已保存");
  },
});
const refreshMutation = useMutation({
  mutationFn: createRefreshJob,
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    message.success("行情刷新任务已加入队列");
  },
});
const reviewMutation = useMutation({
  mutationFn: ({ reportId, decision }: { reportId: number; decision: "approve" | "reject" }) =>
    decideReview(reportId, decision),
  onSuccess: async (result) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["reviews"] }),
      queryClient.invalidateQueries({ queryKey: ["ranking"] }),
    ]);
    message.success(result.ranking_rebuilt ? "候选估值已发布并重算排名" : "候选估值已拒绝");
  },
});

const jobs = computed(() => jobsQuery.data.value?.items ?? []);
const reviews = computed(() => reviewsQuery.data.value?.items ?? []);
const activeJob = computed(() =>
  jobs.value.find((job) => ["queued", "running"].includes(job.status)),
);
const latestSucceeded = computed(() =>
  jobs.value.find((job) => ["succeeded", "partial"].includes(job.status)),
);

const frequencyOptions = [
  { label: "每个交易日", value: "trading_daily" },
  { label: "每周五", value: "weekly" },
  { label: "仅手动", value: "manual" },
];
const calendarOptions = [
  { label: "A 股交易日", value: "CN" },
  { label: "H 股交易日", value: "HK" },
  { label: "任一市场开市", value: "ANY" },
];
const staleOptions = [3, 7, 14, 30].map((value) => ({
  label: `${value} 天`,
  value,
}));

function jobLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "执行中",
    succeeded: "已完成",
    partial: "部分完成",
    failed: "失败",
    cancelled: "已取消",
  };
  return labels[status] ?? status;
}

function statusType(status: string): "default" | "success" | "warning" | "error" | "info" {
  if (status === "succeeded") return "success";
  if (status === "partial") return "warning";
  if (status === "failed") return "error";
  if (["running", "queued"].includes(status)) return "info";
  return "default";
}

function jobTypeLabel(value: string): string {
  return value === "valuation_refresh" ? "Codex 重估" : "行情刷新";
}

function phaseLabel(value: string): string {
  const labels: Record<string, string> = {
    queued: "排队",
    fetching: "取数",
    valuing: "模型估值",
    awaiting_review: "待复核",
    completed: "完成",
    failed: "失败",
    cancelled: "取消",
  };
  return labels[value] ?? value;
}

const jobColumns = computed<DataTableColumns<Job>>(() => [
  {
    title: "任务",
    key: "id",
    render: (job) => `#${job.id} · ${jobTypeLabel(job.job_type)}`,
  },
  {
    title: "触发",
    key: "trigger",
    render: (job) => (job.trigger === "manual" ? "手动" : "定时"),
  },
  {
    title: "状态",
    key: "status",
    render: (job) =>
      h(
        NTag,
        { size: "small", type: statusType(job.status), bordered: false },
        { default: () => jobLabel(job.status) },
      ),
  },
  {
    title: "阶段",
    key: "phase",
    render: (job) => phaseLabel(job.phase),
  },
  {
    title: "行情写入",
    key: "quotes_saved",
    render: (job) => String(job.details.quotes_saved ?? "—"),
  },
  {
    title: "开始",
    key: "started_at",
    render: (job) => formatDateTime(job.started_at ?? job.created_at),
  },
  {
    title: "耗时",
    key: "duration",
    render: (job) => {
      if (!job.started_at || !job.finished_at) return "—";
      const seconds = Math.max(
        1,
        Math.round(
          (new Date(`${job.finished_at}Z`).getTime() -
            new Date(`${job.started_at}Z`).getTime()) /
            1_000,
        ),
      );
      return `${seconds} 秒`;
    },
  },
]);

function save() {
  saveMutation.mutate({ ...form });
}

function runNow() {
  refreshMutation.mutate();
}

function openMarket(id: number) {
  router.push({ name: "valuation", params: { id }, query: { profile: "balanced" } });
}
</script>

<template>
  <div class="updates-view">
    <NGrid responsive="screen" class="updates-hero" cols="1 m:2" align-items="end">
      <NGridItem>
        <NSpace vertical :size="10">
          <NTag :bordered="false">DATA OPERATIONS / 02</NTag>
          <NH1>让排名停留在最近一次收盘。</NH1>
          <NP depth="3">
            调度器只负责在交易日投递任务，worker 负责取数、入库和重算排名。任务失败时不会清空上一份可信结果。
          </NP>
        </NSpace>
      </NGridItem>
      <NGridItem>
        <NText depth="3">数据更新与运行状态</NText>
      </NGridItem>
    </NGrid>

    <div v-if="scheduleQuery.isPending.value" class="loading-state">
      <NSpin size="large" />
      <span>正在读取调度设置…</span>
    </div>
    <NAlert v-else-if="scheduleQuery.isError.value" type="error" title="调度设置读取失败">
      {{ scheduleQuery.error.value?.message }}
    </NAlert>

    <template v-else-if="scheduleQuery.data.value">
      <NGrid class="ops-status-grid" responsive="screen" cols="1 s:2 l:4" :x-gap="16" :y-gap="16">
        <NGridItem>
          <NCard size="small" :bordered="false">
            <NStatistic label="自动更新" :value="form.enabled ? '已开启' : '已暂停'" />
            <NTag :type="form.enabled ? 'success' : 'default'" size="small" :bordered="false">
              {{ frequencyOptions.find((item) => item.value === form.frequency)?.label }}
            </NTag>
          </NCard>
        </NGridItem>
        <NGridItem>
          <NCard size="small" :bordered="false">
            <NStatistic label="下次计划" :value="formatDateTime(scheduleQuery.data.value.next_run_at)" />
            <NTag size="small" :bordered="false">
              {{ calendarOptions.find((item) => item.value === form.calendar_mode)?.label }}
            </NTag>
          </NCard>
        </NGridItem>
        <NGridItem>
          <NCard size="small" :bordered="false">
            <NStatistic label="最近成功" :value="formatDateTime(latestSucceeded?.finished_at)" />
            <NTag size="small" :bordered="false">
              {{ latestSucceeded ? jobLabel(latestSucceeded.status) : "尚未运行" }}
            </NTag>
          </NCard>
        </NGridItem>
        <NGridItem>
          <NCard size="small" :bordered="false">
            <NStatistic label="当前任务" :value="activeJob ? jobLabel(activeJob.status) : '空闲'" />
            <NTag size="small" :bordered="false">
              {{ activeJob ? `#${activeJob.id} · ${phaseLabel(activeJob.phase)}` : "等待下一轮" }}
            </NTag>
          </NCard>
        </NGridItem>
      </NGrid>

      <NGrid class="updates-grid" responsive="screen" cols="1 l:2" :x-gap="16" :y-gap="16">
        <NGridItem>
        <NCard class="schedule-panel" :bordered="false">
          <NSpace vertical :size="16">
            <NSpace align="center" justify="space-between">
              <NH2>收盘后更新设置</NH2>
            <NSwitch v-model:value="form.enabled">
              <template #checked>ON</template>
              <template #unchecked>OFF</template>
            </NSwitch>
            </NSpace>

          <NForm label-placement="top" :show-feedback="false">
            <NGrid responsive="screen" cols="1 s:2" :x-gap="16" :y-gap="4">
              <NGridItem>
                <NFormItem label="更新频率">
                  <NSelect
                    v-model:value="form.frequency"
                    :options="frequencyOptions"
                    aria-label="更新频率"
                  />
                </NFormItem>
              </NGridItem>
              <NGridItem>
                <NFormItem label="执行时间">
                  <NTimePicker
                    :formatted-value="form.run_time ?? null"
                    format="HH:mm"
                    value-format="HH:mm"
                    aria-label="执行时间"
                    @update:formatted-value="
                      (value: string | null) => {
                        if (value) form.run_time = value;
                      }
                    "
                  />
                </NFormItem>
              </NGridItem>
              <NGridItem>
                <NFormItem label="交易日历">
                  <NSelect v-model:value="form.calendar_mode" :options="calendarOptions" />
                </NFormItem>
              </NGridItem>
              <NGridItem>
                <NFormItem label="估值过期提醒">
                  <NSelect v-model:value="form.stale_after_days" :options="staleOptions" />
                </NFormItem>
              </NGridItem>
            </NGrid>
          </NForm>

          <NSpace>
            <NButton
              type="primary"
              :loading="saveMutation.isPending.value"
              @click="save"
            >
              保存设置
            </NButton>
            <NButton
              secondary
              :loading="refreshMutation.isPending.value"
              :disabled="Boolean(activeJob)"
              @click="runNow"
            >
              {{ activeJob ? "已有任务执行中" : "立即刷新行情" }}
            </NButton>
          </NSpace>
          <NP depth="3">
            自动更新会刷新行情、宏观缓存和当前排名。完整 Codex 重估按独立策略运行，不会未经校验覆盖当前估值。
          </NP>
          </NSpace>
        </NCard>
        </NGridItem>

        <NGridItem>
        <NCard class="schedule-summary" :bordered="false">
          <NH2>执行链路</NH2>
          <NForm label-placement="left" :show-feedback="false">
            <NGrid :cols="1" :y-gap="12">
              <NGridItem><NTag :bordered="false">01 交易日检查</NTag></NGridItem>
              <NGridItem><NTag :bordered="false">02 行情抓取</NTag></NGridItem>
              <NGridItem><NTag :bordered="false">03 写入快照</NTag></NGridItem>
              <NGridItem><NTag :bordered="false">04 排名重算</NTag></NGridItem>
            </NGrid>
          </NForm>
          <NP depth="3">
            当前时区：{{ scheduleQuery.data.value.timezone }}。计划时间按上海时区计算。
          </NP>
        </NCard>
        </NGridItem>
      </NGrid>

      <NCard class="jobs-panel" :bordered="false">
        <NSpace vertical :size="16">
          <NSpace align="center" justify="space-between">
            <NH2>最近任务</NH2>
          <NTag :bordered="false" size="small">每 3 秒自动刷新</NTag>
          </NSpace>
        <NDataTable
          v-if="jobs.length"
          size="small"
          :columns="jobColumns"
          :data="jobs"
          :bordered="false"
          :single-line="false"
          :pagination="false"
        />
        <NEmpty v-else description="还没有更新任务" />
        </NSpace>
      </NCard>

      <NCard class="review-panel" :bordered="false">
        <NSpace vertical :size="16">
          <NSpace align="center" justify="space-between">
            <NH2>待复核 Codex 估值</NH2>
          <NTag :bordered="false" size="small">{{ reviews.length }} 个候选版本</NTag>
          </NSpace>
        <NSpace v-if="reviews.length" vertical :size="12">
          <NCard v-for="review in reviews" :key="review.report_id" size="small" :bordered="false">
            <NSpace vertical :size="12">
            <NSpace align="center" justify="space-between">
              <NSpace vertical :size="4">
                <NText strong>{{ review.name }}</NText>
                <NText depth="3">{{ formatDateTime(review.generated_at) }} · 置信度 {{ review.confidence }}</NText>
              </NSpace>
              <NTag type="warning" :bordered="false">REVIEW</NTag>
            </NSpace>
            <NP>{{ review.thesis }}</NP>
            <NSpace>
              <NButton
                v-for="market in review.markets"
                :key="market.valuation_market_id"
                size="tiny"
                tertiary
                @click="openMarket(market.valuation_market_id)"
              >
                {{ market.market }} · {{ market.code }} · {{ market.verdict }}
              </NButton>
            </NSpace>
            <NSpace>
              <NButton
                type="primary"
                size="small"
                :loading="reviewMutation.isPending.value"
                @click="reviewMutation.mutate({ reportId: review.report_id, decision: 'approve' })"
              >
                批准并发布
              </NButton>
              <NButton
                secondary
                size="small"
                :disabled="reviewMutation.isPending.value"
                @click="reviewMutation.mutate({ reportId: review.report_id, decision: 'reject' })"
              >
                拒绝候选
              </NButton>
            </NSpace>
            </NSpace>
          </NCard>
        </NSpace>
        <NEmpty v-else description="没有待复核候选" />
        </NSpace>
      </NCard>
    </template>
  </div>
</template>
