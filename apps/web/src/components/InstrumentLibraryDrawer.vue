<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import {
  NAlert,
  NButton,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NIcon,
  NInput,
  NModal,
  NPopconfirm,
  NSpace,
  NSpin,
  NTag,
  NText,
  useMessage,
} from "naive-ui";
import { ArchiveOutline, RefreshOutline, TrashOutline } from "@vicons/ionicons5";
import { computed, ref, watch } from "vue";

import {
  archiveInstrument,
  fetchInstruments,
  purgeInstrument,
  restoreInstrument,
} from "@/api/client";
import type {
  Instrument,
  InstrumentLifecycleResult,
  InstrumentList,
  InstrumentPurgeResult,
} from "@/api/types";
import { formatDate, marketLabels, pathLabels } from "@/lib/format";

const props = defineProps<{
  show: boolean;
}>();
const emit = defineEmits<{
  "update:show": [value: boolean];
  changed: [];
}>();

const message = useMessage();
const queryClient = useQueryClient();
const purgeTarget = ref<Instrument | null>(null);
const purgeConfirmation = ref("");
const query = useQuery<InstrumentList>({
  queryKey: ["instruments"],
  queryFn: fetchInstruments,
  enabled: computed(() => props.show),
  staleTime: 5_000,
});
const instruments = computed(() =>
  [...(query.data.value?.items ?? [])].sort(
    (left, right) =>
      Number(Boolean(left.archived_at)) - Number(Boolean(right.archived_at)) ||
      left.name.localeCompare(right.name, "zh-CN"),
  ),
);
const activeCount = computed(
  () => instruments.value.filter((instrument) => !instrument.archived_at).length,
);
const archivedCount = computed(() => instruments.value.length - activeCount.value);

async function invalidateInstrumentState() {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["instruments"] }),
    queryClient.invalidateQueries({ queryKey: ["ranking"] }),
    queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  ]);
  emit("changed");
}

const archiveMutation = useMutation({
  mutationFn: archiveInstrument,
  onSuccess: async (result: InstrumentLifecycleResult) => {
    message.success(`${result.name} 已移出榜单，历史估值仍然保留`);
    await invalidateInstrumentState();
  },
  onError: (reason: unknown) => showError(reason),
});

const restoreMutation = useMutation({
  mutationFn: restoreInstrument,
  onSuccess: async (result: InstrumentLifecycleResult) => {
    message.success(`${result.name} 已恢复`);
    await invalidateInstrumentState();
  },
  onError: (reason: unknown) => showError(reason),
});

const purgeMutation = useMutation({
  mutationFn: purgeInstrument,
  onSuccess: async (result: InstrumentPurgeResult) => {
    message.success(
      `${result.name} 已彻底删除，移除 ${result.deleted_reports} 份估值和 ${result.deleted_jobs} 个任务`,
    );
    purgeTarget.value = null;
    purgeConfirmation.value = "";
    await invalidateInstrumentState();
  },
  onError: (reason: unknown) => showError(reason),
});

watch(
  () => props.show,
  (show) => {
    if (show) void query.refetch();
  },
);

function showError(reason: unknown) {
  message.error(reason instanceof Error ? reason.message : String(reason));
}

function openPurge(instrument: Instrument) {
  purgeTarget.value = instrument;
  purgeConfirmation.value = "";
  purgeMutation.reset();
}

function closePurge() {
  if (purgeMutation.isPending.value) return;
  purgeTarget.value = null;
  purgeConfirmation.value = "";
}

function confirmPurge() {
  if (!purgeTarget.value || purgeConfirmation.value !== purgeTarget.value.name) return;
  purgeMutation.mutate(purgeTarget.value);
}
</script>

<template>
  <NDrawer
    :show="show"
    class="instrument-library-drawer"
    placement="right"
    :z-index="1000"
    :trap-focus="true"
    @update:show="emit('update:show', $event)"
  >
    <NDrawerContent :native-scrollbar="false" title="标的库" closable>
      <NSpace vertical :size="16">
        <NAlert type="info" :bordered="false">
          “删除”会将标的移出榜单并停止后续更新，历史估值仍可恢复。彻底删除不可恢复。
        </NAlert>

        <NSpace align="center" :size="8">
          <NTag size="small" :bordered="false">当前 {{ activeCount }}</NTag>
          <NTag size="small" :bordered="false" type="warning">已归档 {{ archivedCount }}</NTag>
          <NButton
            size="small"
            quaternary
            :loading="query.isFetching.value"
            @click="query.refetch()"
          >
            刷新
          </NButton>
        </NSpace>

        <NSpin v-if="query.isPending.value" size="large" />
        <NAlert v-else-if="query.isError.value" type="error" :bordered="false">
          {{ query.error.value?.message }}
        </NAlert>
        <NEmpty v-else-if="!instruments.length" description="标的库还是空的" />

        <div v-else class="instrument-library-list">
          <article
            v-for="instrument in instruments"
            :key="instrument.id"
            :class="[
              'instrument-library-row',
              { 'instrument-library-row--archived': instrument.archived_at },
            ]"
          >
            <div class="instrument-library-main">
              <NSpace align="center" :size="8" :wrap="true">
                <NText strong>{{ instrument.name }}</NText>
                <NTag
                  size="small"
                  :type="instrument.archived_at ? 'warning' : 'success'"
                  :bordered="false"
                >
                  {{ instrument.archived_at ? "已归档" : "当前" }}
                </NTag>
                <NTag size="small" :bordered="false">
                  {{ instrument.asset_type === "etf" ? "ETF" : "股票" }}
                </NTag>
              </NSpace>
              <div class="instrument-library-markets">
                <span v-if="!instrument.listings.length">市场待 Codex 检索</span>
                <span v-for="listing in instrument.listings" :key="listing.code">
                  {{ marketLabels[listing.market] ?? listing.market }} · {{ listing.code }}
                </span>
              </div>
              <NText depth="3" class="instrument-library-meta">
                {{ instrument.industry || "行业待判定" }} ·
                {{ pathLabels[instrument.path] ?? instrument.path }} ·
                {{ instrument.report_count }} 份估值
                <template v-if="instrument.latest_analysis_date">
                  · 最近 {{ formatDate(instrument.latest_analysis_date) }}
                </template>
              </NText>
              <NText v-if="instrument.archived_at" depth="3" class="instrument-library-reason">
                归档原因：{{ instrument.archive_reason || "未填写" }}
              </NText>
            </div>

            <NSpace class="instrument-library-actions" :size="6">
              <template v-if="!instrument.archived_at">
                <NPopconfirm
                  positive-text="移出榜单"
                  negative-text="取消"
                  @positive-click="archiveMutation.mutate(instrument.id)"
                >
                  <template #trigger>
                    <NButton
                      size="small"
                      secondary
                      :aria-label="`删除 ${instrument.name}`"
                      :loading="
                        archiveMutation.isPending.value &&
                        archiveMutation.variables.value === instrument.id
                      "
                    >
                      <template #icon>
                        <NIcon :component="ArchiveOutline" />
                      </template>
                      删除
                    </NButton>
                  </template>
                  移出榜单并停止后续更新？历史估值会保留，可在标的库恢复。
                </NPopconfirm>
              </template>
              <template v-else>
                <NButton
                  size="small"
                  secondary
                  :aria-label="`恢复 ${instrument.name}`"
                  :loading="
                    restoreMutation.isPending.value &&
                    restoreMutation.variables.value === instrument.id
                  "
                  @click="restoreMutation.mutate(instrument.id)"
                >
                  <template #icon>
                    <NIcon :component="RefreshOutline" />
                  </template>
                  恢复
                </NButton>
                <NButton
                  size="small"
                  quaternary
                  type="error"
                  :aria-label="`彻底删除 ${instrument.name}`"
                  @click="openPurge(instrument)"
                >
                  <template #icon>
                    <NIcon :component="TrashOutline" />
                  </template>
                  彻底删除
                </NButton>
              </template>
            </NSpace>
          </article>
        </div>
      </NSpace>
    </NDrawerContent>
  </NDrawer>

  <NModal
    :show="Boolean(purgeTarget)"
    preset="card"
    title="彻底删除标的"
    style="width: min(520px, calc(100vw - 32px))"
    :mask-closable="!purgeMutation.isPending.value"
    :closable="!purgeMutation.isPending.value"
    @update:show="(show) => !show && closePurge()"
  >
    <NSpace vertical :size="16">
      <NAlert type="error" :bordered="false">
        将永久删除 {{ purgeTarget?.name }} 的全部估值、行情、排名和任务记录，此操作不可恢复。
      </NAlert>
      <NText>
        请输入完整标的名称
        <NText strong>{{ purgeTarget?.name }}</NText>
        以确认：
      </NText>
      <NInput
        v-model:value="purgeConfirmation"
        :placeholder="purgeTarget?.name"
        :disabled="purgeMutation.isPending.value"
        @keyup.enter="confirmPurge"
      />
      <NSpace justify="end">
        <NButton :disabled="purgeMutation.isPending.value" @click="closePurge">
          取消
        </NButton>
        <NButton
          type="error"
          :disabled="purgeConfirmation !== purgeTarget?.name"
          :loading="purgeMutation.isPending.value"
          @click="confirmPurge"
        >
          永久删除
        </NButton>
      </NSpace>
    </NSpace>
  </NModal>
</template>
