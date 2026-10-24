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
  NIcon,
  NModal,
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
import { EyeOutline, RefreshOutline, TrashOutline } from "@vicons/ionicons5";
import { computed, h, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import {
  clearJobs,
  createRefreshJob,
  decideReview,
  deleteJob,
  deleteRejectedReview,
  fetchJobs,
  fetchRejectedReviews,
  fetchReviews,
  fetchSchedule,
  pauseJob,
  requestRevaluation,
  resumeJob,
  updateSchedule,
} from "@/api/client";
import type { Job, Review, Schedule, SchedulePatch } from "@/api/types";
import JobDebugPanel from "@/components/JobDebugPanel.vue";
import ReviewPreviewModal from "@/components/ReviewPreviewModal.vue";
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
const rejectedReviewsQuery = useQuery({
  queryKey: ["reviews", "rejected"],
  queryFn: fetchRejectedReviews,
  refetchInterval: 10_000,
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
  onError: (error: Error) => {
    message.error(error.message || "行情刷新任务创建失败");
  },
});
const reviewMutation = useMutation({
  mutationFn: ({ reportId, decision }: { reportId: number; decision: "approve" | "reject" }) =>
    decideReview(reportId, decision),
  onSuccess: async (result) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["reviews"] }),
      queryClient.invalidateQueries({ queryKey: ["reviews", "rejected"] }),
      queryClient.invalidateQueries({ queryKey: ["ranking"] }),
      queryClient.invalidateQueries({ queryKey: ["valuation"] }),
    ]);
    previewReview.value = null;
    message.success(result.ranking_rebuilt ? "候选估值已发布并重算排名" : "候选估值已拒绝");
  },
});
const deleteReviewMutation = useMutation({
  mutationFn: deleteRejectedReview,
  onSuccess: async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["reviews", "rejected"] }),
      queryClient.invalidateQueries({ queryKey: ["jobs"] }),
    ]);
    message.success("已删除拒绝候选");
  },
  onError: (error: Error) => {
    message.error(error.message || "拒绝候选删除失败");
  },
});
const revaluationMutation = useMutation({
  mutationFn: requestRevaluation,
  onSuccess: async (job) => {
    await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    message.success(`Codex 估值任务 #${job.id} 已加入队列`);
  },
  onError: (error: Error) => {
    message.error(error.message || "Codex 估值任务创建失败");
  },
});
const resumeMutation = useMutation({
  mutationFn: resumeJob,
  onSuccess: async (job) => {
    await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    message.success(`任务 #${job.id} 已恢复并重新排队`);
  },
  onError: (error: Error) => {
    message.error(error.message || "任务恢复失败");
  },
});
const pauseMutation = useMutation({
  mutationFn: pauseJob,
  onSuccess: async (job) => {
    await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    message.success(`任务 #${job.id} 已暂停`);
  },
  onError: (error: Error) => {
    message.error(error.message || "任务暂停失败");
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
const deleteJobMutation = useMutation({
  mutationFn: deleteJob,
  onSuccess: async (result) => {
    if (debugJobId.value === result.job_id) {
      debugJobId.value = null;
    }
    deleteJobTarget.value = null;
    await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    message.success(
      result.terminated
        ? `任务 #${result.job_id} 已终止并删除`
        : `任务 #${result.job_id} 已删除`,
    );
  },
  onError: (error: Error) => {
    message.error(error.message || "任务删除失败");
  },
});

const jobs = computed(() => jobsQuery.data.value?.items ?? []);
const reviews = computed(() => reviewsQuery.data.value?.items ?? []);
const rejectedReviews = computed(
  () => rejectedReviewsQuery.data.value?.items ?? [],
);
const previewReview = ref<Review | null>(null);
const previewMode = ref<"pending" | "rejected">("pending");
const reviewDecisionLoading = computed<"approve" | "reject" | null>(() =>
  reviewMutation.isPending.value
    ? reviewMutation.variables.value?.decision ?? null
    : null,
);
const deleteJobTarget = ref<Job | null>(null);
const activeJob = computed(() =>
  jobs.value.find((job) => ["queued", "running", "cancelling"].includes(job.status)),
);
const latestSucceeded = computed(() =>
  jobs.value.find((job) => ["succeeded", "partial"].includes(job.status)),
);
const latestJob = computed(() => {
  return [...jobs.value].sort(
    (left, right) => jobActivityTime(right) - jobActivityTime(left),
  )[0];
});
const latestJobTime = computed(() => {
  const latest = latestJob.value;
  return latest?.finished_at ?? latest?.started_at ?? latest?.created_at ?? null;
});
const debugJobId = ref<number | null>(null);
const expandedRowKeys = computed(() => (debugJobId.value === null ? [] : [debugJobId.value]));
const clock = ref(Date.now());
let clockTimer: ReturnType<typeof setInterval> | undefined;

onMounted(() => {
  clockTimer = setInterval(() => {
    clock.value = Date.now();
  }, 1_000);
});

onBeforeUnmount(() => {
  if (clockTimer) clearInterval(clockTimer);
});

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
    interrupted: "已中断",
    paused: "已暂停",
    cancelling: "终止中",
  };
  return labels[status] ?? status;
}

function statusType(status: string): "default" | "success" | "warning" | "error" | "info" {
  if (status === "succeeded") return "success";
  if (status === "partial") return "warning";
  if (status === "failed") return "error";
  if (["interrupted", "paused", "cancelling"].includes(status)) return "warning";
  if (["running", "queued"].includes(status)) return "info";
  return "default";
}

function jobTypeLabel(value: string): string {
  return value === "valuation_refresh" ? "Codex 估值" : "行情刷新";
}

function instrumentLabel(job: Job): string {
  if (job.job_type !== "valuation_refresh") return "—";
  const instrument = job.details.instrument;
  return typeof instrument === "string" && instrument.trim()
    ? instrument
    : "—";
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
    review_approved: "已同意",
    review_rejected: "已拒绝",
    completed: "完成",
    failed: "失败",
    cancelled: "取消",
    interrupted: "中断",
    paused: "暂停",
    cancelling: "终止中",
  };
  return labels[value] ?? value;
}

function serverTime(value: string): number {
  return new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`).getTime();
}

function jobActivityTime(job: Job): number {
  const value = job.finished_at ?? job.started_at ?? job.created_at;
  return serverTime(value);
}

function legacyExecutionSeconds(job: Job): number | null {
  const events = job.details.debug_events;
  if (!Array.isArray(events)) return null;
  const terminalPhases = new Set([
    "awaiting_review",
    "cancelled",
    "completed",
    "failed",
    "interrupted",
    "paused",
    "review_approved",
    "review_rejected",
  ]);
  let startedAt: number | null = null;
  let total = 0;
  let sawAttempt = false;
  for (const event of events) {
    if (
      typeof event !== "object" ||
      event === null ||
      !("at" in event) ||
      !("phase" in event)
    ) {
      continue;
    }
    const phase = typeof event.phase === "string" ? event.phase : "";
    const at = typeof event.at === "string" ? serverTime(event.at) : NaN;
    if (!Number.isFinite(at)) continue;
    if (
      "message" in event &&
      event.message === "任务开始执行"
    ) {
      startedAt = at;
      sawAttempt = true;
      continue;
    }
    if (startedAt !== null && terminalPhases.has(phase)) {
      total += Math.max(0, (at - startedAt) / 1_000);
      startedAt = null;
    }
  }
  return sawAttempt ? total : null;
}

function durationLabel(
  job: Job,
  now = clock.value,
  withCumulativePrefix = true,
): string {
  const savedSeconds = detailNumber(job, "execution_seconds");
  const legacySeconds =
    savedSeconds === null ? legacyExecutionSeconds(job) : null;
  let totalSeconds =
    savedSeconds ??
    legacySeconds ??
    (job.started_at && job.finished_at
      ? Math.max(
          0,
          (serverTime(job.finished_at) - serverTime(job.started_at)) / 1_000,
        )
      : 0);
  if (job.status === "running" && job.started_at) {
    totalSeconds += Math.max(
      0,
      (now - serverTime(job.started_at)) / 1_000,
    );
  }
  if (totalSeconds <= 0) return job.status === "queued" ? "等待中" : "—";
  const seconds = Math.floor(totalSeconds);
  const cumulative =
    savedSeconds !== null ||
    legacySeconds !== null ||
    Number(job.details.resume_count ?? 0) > 0;
  let label: string;
  if (seconds < 60) {
    label = `${seconds} 秒`;
  } else {
    const minutes = Math.floor(seconds / 60);
    const remaining = seconds % 60;
    if (minutes < 60) label = `${minutes} 分 ${remaining} 秒`;
    else label = `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`;
  }
  return cumulative && withCumulativePrefix ? `累计 ${label}` : label;
}

const jobColumns = computed<DataTableColumns<Job>>(() => {
  const currentTime = clock.value;
  return [
  {
    type: "expand",
    width: 40,
    renderExpand: renderDebugExpand,
  },
  {
    title: "ID",
    key: "id",
    width: 80,
    render: (job) => `#${job.id}`,
  },
  {
    title: "任务",
    key: "job_type",
    width: 130,
    render: (job) => jobTypeLabel(job.job_type),
  },
  {
    title: "标的",
    key: "instrument",
    width: 110,
    render: instrumentLabel,
  },
  {
    title: "触发",
    key: "trigger",
    width: 70,
    render: (job) => (job.trigger === "manual" ? "手动" : "定时"),
  },
  {
    title: "状态",
    key: "status",
    width: 100,
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
    width: 100,
    render: (job) => phaseLabel(job.phase),
  },
  {
    title: "行情写入",
    key: "quotes_saved",
    width: 240,
    render: quoteWriteLabel,
  },
  {
    title: "开始",
    key: "started_at",
    width: 145,
    render: (job) => formatDateTime(job.started_at ?? job.created_at),
  },
  {
    title: "累计耗时",
    key: "duration",
    width: 120,
    render: (job) =>
      h("span", { "data-job-duration": job.id }, durationLabel(job, currentTime)),
  },
  {
    title: "操作",
    key: "actions",
    width: 88,
    render: (job) => {
      if (job.job_type !== "valuation_refresh") {
        return h("span", { class: "job-action-empty" }, "—");
      }
      if (["queued", "running"].includes(job.status)) {
        return h(
          NButton,
          {
            size: "small",
            secondary: true,
            type: "warning",
            "aria-label": `暂停任务 #${job.id}`,
            loading:
              pauseMutation.isPending.value &&
              pauseMutation.variables.value === job.id,
            onClick: () => pauseMutation.mutate(job.id),
          },
          { default: () => "暂停" },
        );
      }
      if (!["failed", "cancelled", "interrupted", "paused"].includes(job.status)) {
        return h("span", { class: "job-action-empty" }, "—");
      }
      return h(
        NButton,
        {
          size: "small",
          secondary: true,
          type: "primary",
          "aria-label": `恢复任务 #${job.id}`,
          loading:
            resumeMutation.isPending.value &&
            resumeMutation.variables.value === job.id,
          onClick: () => resumeMutation.mutate(job.id),
        },
        { default: () => "恢复" },
      );
    },
  },
  {
    title: "删除",
    key: "delete",
    width: 58,
    render: (job) =>
      h(
        NButton,
        {
          quaternary: true,
          circle: true,
          size: "small",
          type: "error",
          "aria-label": `删除任务 #${job.id}`,
          onClick: () => requestDeleteJob(job),
        },
        { icon: () => h(NIcon, { component: TrashOutline }) },
      ),
  },
  ];
});

type WorkflowStatus = "wait" | "process" | "finish" | "error";

interface WorkflowStep {
  title: string;
  description: string;
  status: WorkflowStatus;
}

const workflowJob = computed(() => activeJob.value ?? latestJob.value);
interface WorkflowNotice {
  type: "error" | "warning" | "info";
  title: string;
  message: string;
}
const workflowNotice = computed<WorkflowNotice | null>(() => {
  const job = workflowJob.value;
  if (!job) return null;
  const errors = job.details.errors;
  const items = Array.isArray(errors)
    ? errors.filter((item): item is string => typeof item === "string")
    : [];
  const detail = items.length ? items.join("；") : job.error;
  if (job.status === "failed") {
    return {
      type: "error",
      title: "任务执行失败",
      message: detail || "任务执行失败，请查看任务日志。",
    };
  }
  if (job.status === "interrupted") {
    const phase = job.details.failed_phase;
    const phaseText = typeof phase === "string" ? phaseLabel(phase) : "执行";
    return {
      type: "warning",
      title:
        job.details.interruption_kind === "service_restart"
          ? "服务重启导致任务中断"
          : "任务执行中断",
      message: `任务在${phaseText}阶段中断，累计执行 ${durationLabel(job, clock.value, false)}；可点击“恢复”继续。`,
    };
  }
  if (job.status === "paused") {
    const phase = job.details.paused_from_phase;
    const phaseText = typeof phase === "string" ? phaseLabel(phase) : "当前";
    return {
      type: "warning",
      title: "任务已暂停",
      message: `任务在${phaseText}阶段暂停，累计执行 ${durationLabel(job, clock.value, false)}；可点击“恢复”继续。`,
    };
  }
  if (job.status === "cancelled") {
    return {
      type: "warning",
      title: "任务已取消",
      message: detail || "任务已取消。",
    };
  }
  if (job.status === "partial" && items.length) {
    return {
      type: "warning",
      title: "任务部分完成",
      message: items.join("；"),
    };
  }
  return null;
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
  const failed = ["failed", "cancelled", "interrupted"].includes(job.status);
  const paused = job.status === "paused";
  const completed = ["succeeded", "partial"].includes(job.status);

  return titles.map((title, index) => {
    let status: WorkflowStatus = "wait";
    if (completed || index < currentIndex) status = "finish";
    if (!completed && !paused && index === currentIndex) {
      status = failed ? "error" : "process";
    }
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
    typeof job.details.failed_phase === "string"
      ? job.details.failed_phase
      : typeof job.details.paused_from_phase === "string"
        ? job.details.paused_from_phase
        : job.phase;
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

function requestDeleteJob(job: Job) {
  deleteJobTarget.value = job;
}

function closeDeleteJob() {
  if (deleteJobMutation.isPending.value) return;
  deleteJobTarget.value = null;
}

function confirmDeleteJob() {
  const job = deleteJobTarget.value;
  if (!job) return;
  deleteJobMutation.mutate(job.id);
}

function openReviewPreview(review: Review, mode: "pending" | "rejected") {
  previewReview.value = review;
  previewMode.value = mode;
}

function decidePreview(decision: "approve" | "reject") {
  const review = previewReview.value;
  if (!review) return;
  reviewMutation.mutate({ reportId: review.report_id, decision });
}

function updateExpandedRowKeys(keys: Array<string | number>) {
  if (!keys.length) {
    debugJobId.value = null;
    return;
  }
  const numericKeys = keys.map(Number);
  debugJobId.value =
    numericKeys.find((key) => key !== debugJobId.value) ??
    numericKeys[numericKeys.length - 1];
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
            <NGrid class="schedule-form-grid" responsive="screen" cols="1 s:2" :x-gap="20" :y-gap="12">
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
            自动更新会刷新行情、宏观缓存和当前排名。完整 Codex 估值按独立策略运行，不会未经校验覆盖当前估值。
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
              v-if="workflowNotice"
              :type="workflowNotice.type"
              :title="workflowNotice.title"
            >
              {{ workflowNotice.message }}
            </NAlert>
          </NSpace>
        </NCard>
        </NGridItem>
      </NGrid>

      <NCard class="jobs-panel" :bordered="false">
        <NSpace vertical :size="16">
          <NSpace class="card-heading" align="center" justify="space-between">
            <NH2>最近任务</NH2>
            <NSpace align="center">
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
                type="info"
                size="small"
                secondary
                :aria-label="`预览 ${review.name}`"
                @click="openReviewPreview(review, 'pending')"
              >
                <template #icon>
                  <NIcon :component="EyeOutline" />
                </template>
                预览
              </NButton>
            </NSpace>
            </NSpace>
          </NCard>
        </NSpace>
        <NEmpty v-else description="没有待复核候选" />
        </NSpace>
      </NCard>

      <NCard
        v-if="rejectedReviews.length"
        class="review-panel rejected-review-panel"
        :bordered="false"
      >
        <NSpace vertical :size="16">
          <NSpace class="card-heading" align="center" justify="space-between">
            <NH2>已拒绝候选</NH2>
            <NTag :bordered="false" size="small">
              {{ rejectedReviews.length }} 个最近版本
            </NTag>
          </NSpace>
          <NSpace vertical :size="12">
            <NCard
              v-for="review in rejectedReviews"
              :key="review.report_id"
              size="small"
              :bordered="false"
            >
              <NSpace vertical :size="12">
                <NSpace align="center" justify="space-between">
                  <NSpace vertical :size="4">
                    <NText strong>{{ review.name }}</NText>
                    <NText depth="3">
                      {{ formatDateTime(review.generated_at) }} · 置信度
                      {{ review.confidence }}
                    </NText>
                  </NSpace>
                  <NTag type="error" :bordered="false">已拒绝</NTag>
                </NSpace>
                <NP>{{ review.thesis }}</NP>
                <NSpace align="center" justify="space-between">
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
                      size="small"
                      secondary
                      :aria-label="`预览 ${review.name}`"
                      @click="openReviewPreview(review, 'rejected')"
                    >
                      <template #icon>
                        <NIcon :component="EyeOutline" />
                      </template>
                      预览
                    </NButton>
                    <NPopconfirm
                      positive-text="开始估值"
                      negative-text="取消"
                      @positive-click="
                        revaluationMutation.mutate(review.instrument_id)
                      "
                    >
                      <template #trigger>
                        <NButton
                          size="small"
                          secondary
                          :aria-label="`重新估值 ${review.name}`"
                          :loading="
                            revaluationMutation.isPending.value &&
                            revaluationMutation.variables.value ===
                              review.instrument_id
                          "
                        >
                          <template #icon>
                            <NIcon :component="RefreshOutline" />
                          </template>
                          重新估值
                        </NButton>
                      </template>
                      将重新调用 Codex 生成候选估值，完成后进入待复核。
                    </NPopconfirm>
                    <NPopconfirm
                      positive-text="删除"
                      negative-text="取消"
                      @positive-click="
                        deleteReviewMutation.mutate(review.report_id)
                      "
                    >
                      <template #trigger>
                        <NButton
                          size="small"
                          type="error"
                          secondary
                          :aria-label="`删除已拒绝候选 ${review.name}`"
                          :loading="
                            deleteReviewMutation.isPending.value &&
                            deleteReviewMutation.variables.value ===
                              review.report_id
                          "
                        >
                          <template #icon>
                            <NIcon :component="TrashOutline" />
                          </template>
                          删除
                        </NButton>
                      </template>
                      永久删除该已拒绝候选及其估值明细？
                    </NPopconfirm>
                  </NSpace>
                </NSpace>
              </NSpace>
            </NCard>
          </NSpace>
        </NSpace>
      </NCard>
    </template>

    <NModal
      :show="Boolean(deleteJobTarget)"
      preset="card"
      title="确认删除任务"
      :bordered="false"
      :mask-closable="!deleteJobMutation.isPending.value"
      :close-on-esc="!deleteJobMutation.isPending.value"
      :closable="!deleteJobMutation.isPending.value"
      style="width: min(520px, 92vw)"
      @update:show="(show: boolean) => { if (!show) closeDeleteJob(); }"
    >
      <NSpace v-if="deleteJobTarget" vertical :size="14">
        <NText>
          将删除任务 #{{ deleteJobTarget.id }} ·
          {{ instrumentLabel(deleteJobTarget) }}。
        </NText>
        <NAlert
          v-if="['queued', 'running'].includes(deleteJobTarget.status)"
          type="warning"
          title="任务正在执行"
          :bordered="false"
        >
          确认后会立即终止 Codex 子进程，并删除该任务记录。此操作不可恢复。
        </NAlert>
        <NText type="error" strong>此操作不可恢复，确定永久删除吗？</NText>
      </NSpace>
      <template #footer>
        <NSpace justify="end">
          <NButton
            :disabled="deleteJobMutation.isPending.value"
            @click="closeDeleteJob"
          >
            取消
          </NButton>
          <NButton
            type="error"
            :loading="deleteJobMutation.isPending.value"
            @click="confirmDeleteJob"
          >
            确认删除
          </NButton>
        </NSpace>
      </template>
    </NModal>

    <ReviewPreviewModal
      v-if="previewReview"
      :review="previewReview"
      :mode="previewMode"
      :decision-loading="reviewDecisionLoading"
      @close="previewReview = null"
      @decide="decidePreview"
    />
  </div>
</template>
