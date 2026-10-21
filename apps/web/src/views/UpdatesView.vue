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
  NPopconfirm,
  NP,
  NSelect,
  NSpace,
  NSpin,
  NStatistic,
  NStep,
  NSteps,
  NSwitch,
  NTag,
  NText,
  NTimePicker,
  useMessage,
  type DataTableColumns,
} from "naive-ui";
import { computed, h, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import {
  clearJobs,
  createRefreshJob,
  decideReview,
  fetchJobs,
  fetchReviews,
  fetchSchedule,
  updateSchedule,
} from "@/api/client";
import type { Job, Schedule, SchedulePatch } from "@/api/types";
import JobDebugPanel from "@/components/JobDebugPanel.vue";
import { formatDateTime, formatRelativeTime } from "@/lib/format";

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
const clearMutation = useMutation({
  mutationFn: clearJobs,
  onSuccess: async (result) => {
    debugJobId.value = null;
    await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    message.success(`已清除 ${result.deleted} 条任务记录`);
  },
  onError: (error: Error) => {
    message.error(error.message);
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
const latestJobTime = computed(() => {
  const latest = jobs.value[0];
  return latest?.finished_at ?? latest?.started_at ?? latest?.created_at ?? null;
});
const debugJobId = ref<number | null>(null);
const expandedRowKeys = computed(() => (debugJobId.value === null ? [] : [debugJobId.value]));

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
    fetching: "行情抓取",
    saving_quotes: "写入行情",
    loading_macro: "更新宏观",
    rebuilding_ranking: "重算排名",
    finalizing: "收尾",
    valuing: "模型估值",
    validating: "校验候选",
    candidate_ready: "候选已入库",
    awaiting_review: "待复核",
    completed: "完成",
    failed: "失败",
    cancelled: "取消",
  };
  return labels[value] ?? value;
}

const jobColumns = computed<DataTableColumns<Job>>(() => [
  {
    type: "expand",
    renderExpand: renderDebugExpand,
  },
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
    render: quoteWriteLabel,
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
  {
    title: "调试",
    key: "debug",
    width: 96,
    render: (job) =>
      h(
        NButton,
        {
          size: "tiny",
          secondary: true,
          type: debugJobId.value === job.id ? "primary" : "default",
          onClick: () => toggleDebug(job.id),
        },
        { default: () => (debugJobId.value === job.id ? "收起 Debug" : "Debug 信息") },
      ),
  },
]);

type WorkflowStatus = "wait" | "process" | "finish" | "error";

interface WorkflowStep {
  title: string;
  description: string;
  status: WorkflowStatus;
}

const workflowJob = computed(() => activeJob.value ?? jobs.value[0]);
const workflowErrors = computed(() => {
  const job = workflowJob.value;
  if (!job) return [];
  const errors = job.details.errors;
  const items = Array.isArray(errors)
    ? errors.filter((item): item is string => typeof item === "string")
    : [];
  if (items.length) return items;
  return job.error ? [job.error] : [];
});
const workflowSteps = computed<WorkflowStep[]>(() => {
  const job = workflowJob.value;
  if (!job) {
    return [
      { title: "交易日检查", description: "等待更新任务", status: "wait" },
      { title: "行情抓取", description: "等待更新任务", status: "wait" },
      { title: "写入快照", description: "等待更新任务", status: "wait" },
      { title: "排名处理", description: "等待更新任务", status: "wait" },
    ];
  }

  const titles =
    job.job_type === "valuation_refresh"
      ? ["交易日检查", "模型估值", "候选校验", "等待复核"]
      : ["交易日检查", "行情抓取", "写入快照", "排名处理"];
  const descriptions =
    job.job_type === "valuation_refresh"
      ? valuationStepDescriptions(job)
      : marketStepDescriptions(job);
  const currentIndex = workflowIndex(job);
  const failed = ["failed", "cancelled"].includes(job.status);
  const completed = ["succeeded", "partial"].includes(job.status);

  return titles.map((title, index) => {
    let status: WorkflowStatus = "wait";
    if (completed || index < currentIndex) status = "finish";
    if (!completed && index === currentIndex) status = failed ? "error" : "process";
    return { title, description: descriptions[index], status };
  });
});

function detailNumber(job: Job, key: string): number | null {
  const value = job.details[key];
  return typeof value === "number" ? value : null;
}

function quoteWriteLabel(job: Job): string {
  if (job.job_type !== "market_refresh") return "—";
  const fetched = detailNumber(job, "quotes_fetched");
  const saved = detailNumber(job, "quotes_saved");
  const unchanged = detailNumber(job, "quotes_unchanged");
  if (fetched === null && saved === null && unchanged === null) return "—";
  return `抓取 ${fetched ?? "—"} · 新增 ${saved ?? "—"} · 未变化 ${unchanged ?? "—"}`;
}

function marketStepDescriptions(job: Job): string[] {
  const fetched = detailNumber(job, "quotes_fetched");
  const saved = detailNumber(job, "quotes_saved");
  const unchanged = detailNumber(job, "quotes_unchanged");
  const rankingRuns = detailNumber(job, "ranking_runs");
  const listingCount = detailNumber(job, "listings");
  const quoteAt = job.details.latest_quote_at;
  return [
    job.trigger === "manual" ? "手动触发，无需等待交易日窗口" : "已通过交易日计划检查",
    fetched === null
      ? listingCount === null
        ? "正在读取标的列表"
        : `覆盖 ${listingCount} 个上市标的`
      : `取得 ${fetched} 条有效行情`,
    saved === null
      ? "正在写入行情快照"
      : `新增 ${saved} · 未变化 ${unchanged ?? 0}`,
    rankingRuns
      ? `已重算 ${rankingRuns} 套排名`
      : job.details.ranking_reused === true
        ? "行情未变化，复用现有排名"
        : typeof quoteAt === "string"
          ? `最新行情 ${formatDateTime(quoteAt)}`
          : "正在检查排名",
  ];
}

function valuationStepDescriptions(job: Job): string[] {
  const instrument = job.details.instrument;
  return [
    "已创建单标的估值任务",
    typeof instrument === "string" ? `Codex 分析 ${instrument}` : "Codex 正在生成候选估值",
    job.details.review_required === true ? "候选数据卡已通过校验" : "等待候选数据卡",
    job.details.report_id ? `候选版本 #${String(job.details.report_id)}` : "尚未进入复核",
  ];
}

function workflowIndex(job: Job): number {
  const phase =
    typeof job.details.failed_phase === "string" ? job.details.failed_phase : job.phase;
  if (job.job_type === "valuation_refresh") {
    if (phase === "valuing") return 1;
    if (["validating", "candidate_ready"].includes(phase)) return 2;
    if (phase === "awaiting_review") return 3;
    if (phase === "completed") return 3;
    return 0;
  }
  if (phase === "queued") return 0;
  if (phase === "fetching") return 1;
  if (["saving_quotes", "loading_macro"].includes(phase)) return 2;
  if (["rebuilding_ranking", "finalizing", "completed"].includes(phase)) return 3;
  return 0;
}

function save() {
  saveMutation.mutate({ ...form });
}

function runNow() {
  refreshMutation.mutate();
}

function clearAllJobs() {
  clearMutation.mutate();
}

function toggleDebug(jobId: number) {
  debugJobId.value = debugJobId.value === jobId ? null : jobId;
}

function updateExpandedRowKeys(keys: Array<string | number>) {
  debugJobId.value = keys.length ? Number(keys[0]) : null;
}

function renderDebugExpand(job: Job) {
  return h(JobDebugPanel, { jobId: job.id });
}

function openMarket(id: number) {
  router.push({ name: "valuation", params: { id }, query: { profile: "balanced" } });
}
</script>

<template>
  <div class="updates-view">
    <NSpace vertical :size="8">
      <NTag class="latest-task-tag" type="info" :bordered="false">
        最近任务：{{ formatRelativeTime(latestJobTime) }}
      </NTag>
      <NH1 class="updates-title dashboard-title">数据更新与运行状态</NH1>
    </NSpace>

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
            <NSpace class="card-heading" align="center" justify="space-between">
              <NH2>收盘后更新设置</NH2>
            <NSwitch v-model:value="form.enabled" />
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
          <NSpace vertical :size="16">
            <NSpace class="card-heading" align="center" justify="space-between">
              <NH2>执行链路</NH2>
              <NTag
                v-if="workflowJob"
                size="small"
                :bordered="false"
                :type="statusType(workflowJob.status)"
              >
                #{{ workflowJob.id }} · {{ phaseLabel(workflowJob.phase) }}
              </NTag>
            </NSpace>
            <NSteps size="small" vertical>
              <NStep
                v-for="step in workflowSteps"
                :key="step.title"
                :title="step.title"
                :description="step.description"
                :status="step.status"
              />
            </NSteps>
            <NAlert
              v-if="workflowErrors.length"
              :type="workflowJob?.status === 'failed' ? 'error' : 'warning'"
              :title="workflowJob?.status === 'failed' ? '最近任务失败' : '任务存在部分告警'"
            >
              {{ workflowErrors.join("；") }}
            </NAlert>
          </NSpace>
          <NP depth="3">
            当前时区：{{ scheduleQuery.data.value.timezone }}。计划时间按上海时区计算。
          </NP>
        </NCard>
        </NGridItem>
      </NGrid>

      <NCard class="jobs-panel" :bordered="false">
        <NSpace vertical :size="16">
          <NSpace class="card-heading" align="center" justify="space-between">
            <NH2>最近任务</NH2>
            <NSpace align="center">
              <NTag :bordered="false" size="small">每 3 秒自动刷新</NTag>
              <NPopconfirm @positive-click="clearAllJobs">
                <template #trigger>
                  <NButton
                    size="small"
                    type="error"
                    secondary
                    :disabled="Boolean(activeJob)"
                    :loading="clearMutation.isPending.value"
                  >
                    清除所有
                  </NButton>
                </template>
                将删除全部已结束任务记录，此操作不可恢复。
              </NPopconfirm>
            </NSpace>
          </NSpace>
        <NDataTable
          v-if="jobs.length"
          size="small"
          :columns="jobColumns"
          :data="jobs"
          :row-key="(job: Job) => job.id"
          :expanded-row-keys="expandedRowKeys"
          @update:expanded-row-keys="updateExpandedRowKeys"
          :bordered="false"
          :bottom-bordered="false"
          :single-line="false"
          :pagination="false"
        />
        <NEmpty v-else description="还没有更新任务" />
        </NSpace>
      </NCard>

      <NCard class="review-panel" :bordered="false">
        <NSpace vertical :size="16">
          <NSpace class="card-heading" align="center" justify="space-between">
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
