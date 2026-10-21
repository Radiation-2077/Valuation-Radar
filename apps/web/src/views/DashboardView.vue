<script setup lang="ts">
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NFormItem,
  NGrid,
  NGridItem,
  NH1,
  NH2,
  NIcon,
  NPopover,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  NText,
  type DataTableColumns,
} from "naive-ui";
import { FunnelOutline } from "@vicons/ionicons5";
import { computed, h, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { fetchRanking } from "@/api/client";
import type { ProfileCode, RankingItem, RankingResponse } from "@/api/types";
import ProfileSwitcher from "@/components/ProfileSwitcher.vue";
import RankingScatter from "@/components/RankingScatter.vue";
import TopPickCard from "@/components/TopPickCard.vue";
import ValuationDetailPanel from "@/components/ValuationDetailPanel.vue";
import {
  formatDate,
  formatMoney,
  formatNumber,
  formatPercent,
  marketLabels,
  pathLabels,
} from "@/lib/format";

const route = useRoute();
const router = useRouter();
const queryClient = useQueryClient();
const PROFILE_ORDER: ProfileCode[] = ["conservative", "balanced", "aggressive"];
const profile = computed<ProfileCode>(() => {
  const value = String(route.query.profile ?? "balanced");
  return ["conservative", "balanced", "aggressive"].includes(value)
    ? (value as ProfileCode)
    : "balanced";
});
const market = ref<string | null>(null);
const path = ref<string | null>(null);
const industry = ref<string | null>(null);
const filtersOpen = ref(false);
const selectedValuationId = ref<number | null>(null);
const detailOpen = ref(false);
const slideDirection = ref<"left" | "right">("left");
const slideTransition = computed(() => `profile-slide-${slideDirection.value}`);

const filters = computed(() => ({
  profile: profile.value,
  market: market.value || undefined,
  path: path.value || undefined,
  industry: industry.value || undefined,
}));
const activeFilterCount = computed(
  () => [market.value, path.value, industry.value].filter(Boolean).length,
);
const query = useQuery<RankingResponse>({
  queryKey: computed(() => ["ranking", filters.value]),
  queryFn: () => fetchRanking(filters.value),
  staleTime: 30_000,
});

const marketOptions = computed(() =>
  (query.data.value?.available_markets ?? [])
    .filter((value) => value !== "CN")
    .map((value) => ({
      label: marketLabels[value] ?? value,
      value,
    })),
);
const pathOptions = computed(() =>
  (query.data.value?.available_paths ?? []).map((value) => ({
    label: pathLabels[value] ?? value,
    value,
  })),
);
const industryOptions = computed(() =>
  (query.data.value?.available_industries ?? []).map((value) => ({
    label: value,
    value,
  })),
);

watch(marketOptions, (options) => {
  if (market.value && !options.some((option) => option.value === market.value)) {
    market.value = null;
  }
});

const bandType = (band: string): "success" | "info" | "warning" | "error" => {
  if (band === "S") return "success";
  if (band === "A") return "info";
  if (band === "B") return "warning";
  return "error";
};

const columns = computed<DataTableColumns<RankingItem>>(() => [
  { title: "排名", key: "rank", width: 72 },
  {
    title: "标的",
    key: "name",
    minWidth: 170,
    render: (row) =>
      h(NSpace, { vertical: true, size: 2 }, {
        default: () => [
          h(NText, { strong: true }, { default: () => row.name }),
          h(NText, { depth: 3 }, { default: () => `${row.market} · ${row.code}` }),
        ],
      }),
  },
  {
    title: "行业 / 路径",
    key: "industry",
    render: (row) => `${row.industry} / ${pathLabels[row.path] ?? row.path}`,
  },
  {
    title: "现价",
    key: "price",
    render: (row) => formatMoney(row.price, row.currency),
  },
  {
    title: "安全边际",
    key: "margin",
    render: (row) =>
      h(
        NText,
        { type: (row.safety_margin_pct ?? 0) >= 0 ? "success" : "error" },
        { default: () => formatPercent(row.safety_margin_pct) },
      ),
  },
  {
    title: "预期年化",
    key: "expected",
    render: (row) => formatPercent(row.expected_return.total),
  },
  {
    title: "最大回撤",
    key: "drawdown",
    render: (row) => formatPercent(row.max_drawdown_pct),
  },
  {
    title: "综合分",
    key: "score",
    render: (row) =>
      h(NSpace, { align: "center", size: 6 }, {
        default: () => [
          h(NText, { strong: true }, { default: () => formatNumber(row.score.total, 1) }),
          h(
            NTag,
            { size: "small", type: bandType(row.score.band), bordered: false },
            { default: () => row.score.band },
          ),
        ],
      }),
  },
  {
    title: "数据日期",
    key: "date",
    render: (row) =>
      h(
        NText,
        { type: row.stale_days > 7 ? "warning" : undefined },
        { default: () => formatDate(row.analysis_date) },
      ),
  },
]);

const excludedColumns = computed<DataTableColumns<RankingItem>>(() => [
  {
    title: "标的",
    key: "name",
    minWidth: 160,
    render: (row) =>
      h(NSpace, { vertical: true, size: 2 }, {
        default: () => [
          h(NText, { strong: true }, { default: () => row.name }),
          h(NText, { depth: 3 }, { default: () => `${row.market} · ${row.code}` }),
        ],
      }),
  },
  {
    title: "行业 / 路径",
    key: "industry",
    minWidth: 140,
    render: (row) => `${row.industry} / ${pathLabels[row.path] ?? row.path}`,
  },
  {
    title: "综合分",
    key: "score",
    width: 100,
    render: (row) => formatNumber(row.score.total, 1),
  },
  {
    title: "数据日期",
    key: "date",
    width: 100,
    render: (row) => formatDate(row.analysis_date),
  },
  {
    title: "排除 / 观察原因",
    key: "reason",
    minWidth: 420,
    render: (row) =>
      h(
        NText,
        { depth: 3, style: "white-space:normal;line-height:1.65" },
        { default: () => row.excluded_reasons.join("；") },
      ),
  },
]);

const etfColumns = computed<DataTableColumns<RankingItem>>(() => [
  {
    title: "ETF",
    key: "name",
    minWidth: 170,
    render: (row) =>
      h(NSpace, { vertical: true, size: 2 }, {
        default: () => [
          h(NText, { strong: true }, { default: () => row.name }),
          h(NText, { depth: 3 }, { default: () => row.code }),
        ],
      }),
  },
  {
    title: "行业 / 路径",
    key: "industry",
    minWidth: 150,
    render: (row) => `${row.industry} / ${pathLabels[row.path] ?? row.path}`,
  },
  {
    title: "现价",
    key: "price",
    width: 100,
    render: (row) => formatMoney(row.price, row.currency),
  },
  {
    title: "安全边际",
    key: "margin",
    width: 110,
    render: (row) =>
      h(
        NText,
        { type: (row.safety_margin_pct ?? 0) >= 0 ? "success" : "error" },
        { default: () => formatPercent(row.safety_margin_pct) },
      ),
  },
  {
    title: "预期年化",
    key: "expected",
    width: 110,
    render: (row) => formatPercent(row.expected_return.total),
  },
  {
    title: "最大回撤",
    key: "drawdown",
    width: 110,
    render: (row) => formatPercent(row.max_drawdown_pct),
  },
  {
    title: "综合分",
    key: "score",
    width: 105,
    render: (row) =>
      h(NSpace, { align: "center", size: 6 }, {
        default: () => [
          h(NText, { strong: true }, { default: () => formatNumber(row.score.total, 1) }),
          h(
            NTag,
            { size: "small", type: bandType(row.score.band), bordered: false },
            { default: () => row.score.band },
          ),
        ],
      }),
  },
  {
    title: "数据日期",
    key: "date",
    width: 100,
    render: (row) => formatDate(row.analysis_date),
  },
]);

async function selectProfile(value: ProfileCode) {
  if (value === profile.value) return;

  const currentIndex = PROFILE_ORDER.indexOf(profile.value);
  const nextIndex = PROFILE_ORDER.indexOf(value);
  slideDirection.value = nextIndex > currentIndex ? "left" : "right";

  const targetFilters = { ...filters.value, profile: value };
  try {
    await queryClient.prefetchQuery({
      queryKey: ["ranking", targetFilters],
      queryFn: () => fetchRanking(targetFilters),
      staleTime: 30_000,
    });
  } finally {
    router.replace({ query: { ...route.query, profile: value } });
  }
}

function openValuation(id: number) {
  selectedValuationId.value = id;
  detailOpen.value = true;
}

function clearFilters() {
  market.value = null;
  path.value = null;
  industry.value = null;
}

function rowProps(row: RankingItem) {
  return {
    style: "cursor:pointer",
    tabindex: 0,
    onClick: () => openValuation(row.valuation_market_id),
    onKeydown: (event: KeyboardEvent) => {
      if (event.key === "Enter") openValuation(row.valuation_market_id);
    },
  };
}
</script>

<template>
  <NSpace vertical class="dashboard-stack" :size="24">
    <NSpace vertical :size="8">
      <NTag
        v-if="query.data.value?.freshness.stale_units"
        class="dashboard-stale-tag"
        type="warning"
        :bordered="false"
      >
        {{ query.data.value.freshness.stale_units }} 条估值超过
        {{ query.data.value.freshness.stale_after_days }} 天
      </NTag>
      <NH1 class="dashboard-title">风险调整后的性价比</NH1>
    </NSpace>

    <NSpace class="toolbar" align="center" justify="end" :wrap="true" :size="8">
      <ProfileSwitcher :model-value="profile" @update:model-value="selectProfile" />
      <NPopover
        v-model:show="filtersOpen"
        trigger="click"
        placement="bottom-end"
        :width="420"
      >
        <template #trigger>
          <NButton
            size="medium"
            secondary
            :aria-expanded="filtersOpen"
          >
            <template #icon>
              <NIcon :component="FunnelOutline" />
            </template>
            筛选
            <NTag v-if="activeFilterCount" size="tiny" :bordered="false">
              {{ activeFilterCount }}
            </NTag>
          </NButton>
        </template>
        <NSpace class="filter-popover" vertical :size="12">
          <NFormItem label="市场" :show-feedback="false">
            <NSelect
              v-model:value="market"
              :options="marketOptions"
              clearable
              placeholder="全部市场"
            />
          </NFormItem>
          <NFormItem label="估值路径" :show-feedback="false">
            <NSelect
              v-model:value="path"
              :options="pathOptions"
              clearable
              placeholder="全部路径"
            />
          </NFormItem>
          <NFormItem label="行业" :show-feedback="false">
            <NSelect
              v-model:value="industry"
              :options="industryOptions"
              clearable
              filterable
              placeholder="全部行业"
            />
          </NFormItem>
          <NButton
            v-if="activeFilterCount"
            block
            tertiary
            @click="clearFilters"
          >
            清除筛选
          </NButton>
        </NSpace>
      </NPopover>
    </NSpace>

    <NSpin v-if="query.isPending.value" size="large" />
    <NAlert v-else-if="query.isError.value" type="error" title="排名暂时不可用">
      <NSpace justify="space-between" align="center">
        <span>{{ query.error.value?.message }}</span>
        <NButton size="small" @click="query.refetch()">重新加载</NButton>
      </NSpace>
    </NAlert>

    <div v-else class="profile-stage">
      <Transition :name="slideTransition">
        <NSpace
          v-if="query.data.value"
          :key="profile"
          class="profile-content-layer"
          :data-profile="profile"
          vertical
          :size="20"
        >
      <NCard class="top3-card">
        <NSpace vertical :size="20">
          <NSpace class="card-heading" align="center" justify="space-between" :wrap="true">
            <NH2>性价比Top3</NH2>
            <NTag :bordered="false">
              {{ query.data.value.profile_label }}权重 · 算法 {{ query.data.value.algorithm_version }}
            </NTag>
          </NSpace>
          <NEmpty
            v-if="!query.data.value.top_three.length"
            description="当前市场没有主榜标的，请查看下方 ETF 独立观察"
          />
          <NGrid v-else responsive="screen" class="top-picks-grid" cols="1 m:3">
            <NGridItem
              v-for="(item, index) in query.data.value.top_three"
              :key="item.valuation_market_id"
            >
              <TopPickCard :item="item" :position="index + 1" @select="openValuation" />
            </NGridItem>
          </NGrid>
        </NSpace>
      </NCard>

      <NCard class="analysis-card">
        <NSpace vertical :size="20">
          <NSpace class="card-heading" align="center" justify="space-between" :wrap="true">
            <NH2>性价比象限</NH2>
            <NSpace align="center" :size="8">
              <NTag size="small" :bordered="false">气泡越大，安全边际越高</NTag>
              <NTag size="small" :bordered="false">主榜 {{ query.data.value.counts.main_board }}</NTag>
              <NTag size="small" :bordered="false">ETF {{ query.data.value.counts.etfs }}</NTag>
              <NTag size="small" :bordered="false">观察 {{ query.data.value.counts.excluded }}</NTag>
            </NSpace>
          </NSpace>
          <RankingScatter
            :items="[...query.data.value.main_board, ...query.data.value.etfs]"
            @select="openValuation"
          />
        </NSpace>
      </NCard>

      <NCard class="ranking-card">
        <NSpace vertical :size="16">
          <NSpace class="card-heading" align="center" justify="space-between">
            <NH2>完整性价比排名</NH2>
            <NTag size="small" :bordered="false">点击行在同页展开详情</NTag>
          </NSpace>
          <div v-if="query.data.value.main_board.length" class="table-shell">
            <NDataTable
              class="ranking-table"
              size="small"
              :columns="columns"
              :data="query.data.value.main_board"
              :row-props="rowProps"
              :bordered="false"
              :bottom-bordered="false"
              :single-line="false"
              :pagination="false"
              :scroll-x="1120"
            />
          </div>
          <NEmpty v-else description="当前市场没有主榜标的，请查看 ETF 独立观察" />
        </NSpace>
      </NCard>

      <NCard v-if="query.data.value.etfs.length" class="ranking-card">
        <NSpace vertical :size="16">
          <NSpace class="card-heading" align="center" justify="space-between">
            <NH2>ETF 独立观察</NH2>
            <NTag size="small" :bordered="false">{{ query.data.value.etfs.length }} 条</NTag>
          </NSpace>
          <div class="table-shell">
            <NDataTable
              class="etf-table"
              size="small"
              :columns="etfColumns"
              :data="query.data.value.etfs"
              :row-props="rowProps"
              :bordered="false"
              :bottom-bordered="false"
              :single-line="false"
              :pagination="false"
              :scroll-x="980"
            />
          </div>
        </NSpace>
      </NCard>

      <NCard v-if="query.data.value.excluded.length" class="ranking-card">
        <NSpace vertical :size="16">
          <NSpace class="card-heading" align="center" justify="space-between">
            <NH2>排除 / 观察区</NH2>
            <NTag size="small" :bordered="false">
              {{ query.data.value.excluded.length }} 条
            </NTag>
          </NSpace>
          <div class="table-shell">
            <NDataTable
              class="excluded-table"
              size="small"
              :columns="excludedColumns"
              :data="query.data.value.excluded"
              :row-props="rowProps"
              :bordered="false"
              :bottom-bordered="false"
              :single-line="false"
              :pagination="false"
              :scroll-x="980"
            />
          </div>
        </NSpace>
      </NCard>
        </NSpace>
      </Transition>
    </div>

    <NDrawer
      v-model:show="detailOpen"
      class="detail-drawer"
      placement="right"
      :trap-focus="true"
      @after-leave="selectedValuationId = null"
    >
      <NDrawerContent :native-scrollbar="false" closable>
        <ValuationDetailPanel
          v-if="selectedValuationId"
          :valuation-market-id="selectedValuationId"
          :profile="profile"
          @close="detailOpen = false"
        />
      </NDrawerContent>
    </NDrawer>
  </NSpace>
</template>
