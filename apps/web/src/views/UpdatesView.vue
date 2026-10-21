<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, reactive, watch } from "vue";

import {
  createRefreshJob,
  fetchJobs,
  fetchSchedule,
  updateSchedule,
} from "@/api/client";
import type { Schedule, SchedulePatch } from "@/api/types";
import { formatDateTime } from "@/lib/format";

const queryClient = useQueryClient();
const scheduleQuery = useQuery({ queryKey: ["schedule"], queryFn: fetchSchedule });
const jobsQuery = useQuery({
  queryKey: ["jobs"],
  queryFn: fetchJobs,
  refetchInterval: 3_000,
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
  },
});

const refreshMutation = useMutation({
  mutationFn: createRefreshJob,
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["jobs"] });
  },
});

const jobs = computed(() => jobsQuery.data.value?.items ?? []);
const activeJob = computed(() =>
  jobs.value.find((job) => ["queued", "running"].includes(job.status)),
);
const latestSucceeded = computed(() =>
  jobs.value.find((job) => ["succeeded", "partial"].includes(job.status)),
);

function save() {
  saveMutation.mutate({ ...form });
}

function runNow() {
  refreshMutation.mutate();
}

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

function frequencyLabel(value: string): string {
  return (
    {
      trading_daily: "每个交易日",
      weekly: "每周五",
      manual: "仅手动",
    }[value] ?? value
  );
}

function calendarLabel(value: string): string {
  return (
    {
      CN: "A 股交易日",
      HK: "H 股交易日",
      ANY: "任一市场开市",
    }[value] ?? value
  );
}
</script>

<template>
  <div class="updates-view">
    <section class="updates-hero">
      <div>
        <p class="eyebrow">DATA OPERATIONS / 02</p>
        <h1>让排名停留在最近一次收盘。</h1>
        <p class="hero-copy">
          调度器只负责在交易日投递任务，worker 负责取数、入库和重算排名。任务失败时不会清空上一份可信结果。
        </p>
      </div>
      <div class="hero-side">
        <span class="section-index">02</span>
        <small>数据更新与运行状态</small>
      </div>
    </section>

    <div v-if="scheduleQuery.isPending.value" class="loading-state">
      <span class="loader"></span>
      正在读取调度设置…
    </div>
    <div v-else-if="scheduleQuery.isError.value" class="error-panel">
      <strong>调度设置读取失败</strong>
      <p>{{ scheduleQuery.error.value?.message }}</p>
    </div>

    <template v-else-if="scheduleQuery.data.value">
      <section class="ops-status-grid">
        <article :class="{ active: form.enabled }">
          <small>自动更新</small>
          <strong>{{ form.enabled ? "已开启" : "已暂停" }}</strong>
          <span>{{ frequencyLabel(String(form.frequency)) }}</span>
        </article>
        <article>
          <small>下次计划</small>
          <strong>{{ formatDateTime(scheduleQuery.data.value.next_run_at) }}</strong>
          <span>{{ calendarLabel(String(form.calendar_mode)) }}</span>
        </article>
        <article>
          <small>最近成功</small>
          <strong>{{ formatDateTime(latestSucceeded?.finished_at) }}</strong>
          <span>{{ latestSucceeded ? jobLabel(latestSucceeded.status) : "尚未运行" }}</span>
        </article>
        <article>
          <small>当前任务</small>
          <strong>{{ activeJob ? jobLabel(activeJob.status) : "空闲" }}</strong>
          <span>{{ activeJob ? `#${activeJob.id} · ${activeJob.phase}` : "等待下一轮" }}</span>
        </article>
      </section>

      <section class="updates-layout">
        <article class="panel schedule-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">SCHEDULE</p>
              <h2>收盘后更新设置</h2>
            </div>
            <label class="switch-control">
              <input v-model="form.enabled" type="checkbox" />
              <span></span>
              <b>{{ form.enabled ? "ON" : "OFF" }}</b>
            </label>
          </div>

          <div class="schedule-fields">
            <label>
              <span>更新频率</span>
              <select v-model="form.frequency">
                <option value="trading_daily">每个交易日</option>
                <option value="weekly">每周五</option>
                <option value="manual">仅手动</option>
              </select>
            </label>
            <label>
              <span>执行时间</span>
              <input v-model="form.run_time" type="time" />
            </label>
            <label>
              <span>交易日历</span>
              <select v-model="form.calendar_mode">
                <option value="CN">A 股交易日</option>
                <option value="HK">H 股交易日</option>
                <option value="ANY">任一市场开市</option>
              </select>
            </label>
            <label>
              <span>估值过期提醒</span>
              <select v-model.number="form.stale_after_days">
                <option :value="3">3 天</option>
                <option :value="7">7 天</option>
                <option :value="14">14 天</option>
                <option :value="30">30 天</option>
              </select>
            </label>
          </div>

          <div class="schedule-actions">
            <button
              class="primary-button"
              type="button"
              :disabled="saveMutation.isPending.value"
              @click="save"
            >
              {{ saveMutation.isPending.value ? "保存中…" : "保存设置" }}
            </button>
            <button
              class="ghost-button"
              type="button"
              :disabled="Boolean(activeJob) || refreshMutation.isPending.value"
              @click="runNow"
            >
              {{ activeJob ? "已有任务执行中" : refreshMutation.isPending.value ? "提交中…" : "立即刷新行情" }}
            </button>
            <span v-if="saveMutation.isSuccess.value" class="success-note">设置已保存</span>
            <span v-if="refreshMutation.isSuccess.value" class="success-note">刷新任务已加入队列</span>
          </div>
          <p class="schedule-note">
            自动更新会刷新行情、宏观缓存和当前排名。完整 Codex 重估按独立策略运行，不会未经校验覆盖当前估值。
          </p>
        </article>

        <aside class="panel schedule-summary">
          <p class="eyebrow">HOW IT RUNS</p>
          <h2>执行链路</h2>
          <ol>
            <li><span>01</span><div><strong>交易日检查</strong><small>休市日不投递</small></div></li>
            <li><span>02</span><div><strong>行情抓取</strong><small>腾讯 A/H 字段分离</small></div></li>
            <li><span>03</span><div><strong>写入快照</strong><small>保留原始响应</small></div></li>
            <li><span>04</span><div><strong>排名重算</strong><small>不改写历史估值</small></div></li>
          </ol>
          <p class="panel-footnote">
            当前时区：{{ scheduleQuery.data.value.timezone }}。计划时间按本机上海时区计算。
          </p>
        </aside>
      </section>

      <section class="panel jobs-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">JOB HISTORY</p>
            <h2>最近任务</h2>
          </div>
          <span class="panel-note">每 3 秒自动刷新状态</span>
        </div>
        <div v-if="jobs.length" class="table-wrap">
          <table class="jobs-table">
            <thead>
              <tr>
                <th>任务</th>
                <th>触发</th>
                <th>状态</th>
                <th>阶段</th>
                <th>行情写入</th>
                <th>开始</th>
                <th>耗时</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="job in jobs" :key="job.id">
                <td>#{{ job.id }} · {{ job.job_type }}</td>
                <td>{{ job.trigger === "manual" ? "手动" : "定时" }}</td>
                <td><span class="job-status" :class="`job-status--${job.status}`">{{ jobLabel(job.status) }}</span></td>
                <td>{{ job.phase }}</td>
                <td>{{ job.details.quotes_saved ?? "—" }}</td>
                <td>{{ formatDateTime(job.started_at ?? job.created_at) }}</td>
                <td>{{ job.finished_at && job.started_at ? `${Math.max(1, Math.round((new Date(`${job.finished_at}Z`).getTime() - new Date(`${job.started_at}Z`).getTime()) / 1000))} 秒` : "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-panel">还没有更新任务。可先点击“立即刷新行情”。</div>
      </section>
    </template>
  </div>
</template>
