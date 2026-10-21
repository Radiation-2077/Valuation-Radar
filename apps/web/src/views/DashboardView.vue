<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";
import {
  NAlert,
  NButton,
  NCard,
  NCollapse,
  NCollapseItem,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NFormItem,
  NGrid,
  NGridItem,
  NSelect,
  NSpin,
  NSwitch,
  NTag,
  type DataTableColumns,
} from "naive-ui";
import { computed, h, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { fetchRanking } from "@/api/client";
import type { ProfileCode, RankingItem, RankingResponse } from "@/api/types";
import FreshnessBar from "@/components/FreshnessBar.vue";
import ProfileTabs from "@/components/ProfileTabs.vue";
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
const profile = computed<ProfileCode>(() => {
  const value = String(route.query.profile ?? "balanced");
  return ["conservative", "balanced", "aggressive"].includes(value)
    ? (value as ProfileCode)
    : "balanced";
});
const market = ref<string | null>(null);
const path = ref<string | null>(null);
const industry = ref<string | null>(null);
const staleOnly = ref(false);
const selectedValuationId = ref<number | null>(null);
const detailOpen = ref(false);

const filters = computed(() => ({
  profile: profile.value,
  market: market.value || undefined,
  path: path.value || undefined,
  industry: industry.value || undefined,
  staleOnly: staleOnly.value,
}));

const query = useQuery<RankingResponse>({
  queryKey: computed(() => ["ranking", filters.value]),
  queryFn: () => fetchRanking(filters.value),
});

const marketOptions = computed(() =>
  (query.data.value?.available_markets ?? []).map((value) => ({
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

const bandType = (band: string): "success" | "info" | "warning" | "error" => {
  if (band === "S") return "success";
  if (band === "A") return "info";
  if (band === "B") return "warning";
  return "error";
};

const rankingColumns = computed<DataTableColumns<RankingItem>>(() => [
  {
    title: "排名",
    key: "rank",
    width: 68,
    render: (row) => h("span", { class: "rank-number" }, String(row.rank ?? "—")),
  },
  {
    title: "标的",
    key: "name",
    minWidth: 190,
    render: (row) =>
      h("div", [
        h("strong", { class: "security-name" }, row.name),
        h("span", { class: "security-code" }, `${row.market} · ${row.code}`),
        h(
          "div",
          row.risk_flags.slice(0, 2).map((flag) =>
            h(
              NTag,
              { size: "tiny", bordered: false, style: "margin-right:4px;margin-top:4px" },
              { default: () => flag },
            ),
          ),
        ),
      ]),
  },
  {
    title: "行业 / 路径",
    key: "industry",
    minWidth: 145,
    render: (row) =>
      h("div", [
        h("span", row.industry),
        h("small", { class: "cell-sub" }, pathLabels[row.path] ?? row.path),
      ]),
  },
  {
    title: "现价",
    key: "price",
    width: 108,
    render: (row) => formatMoney(row.price, row.currency),
  },
  {
    title: "安全边际",
    key: "safety_margin_pct",
    width: 108,
    render: (row) =>
      h(
        "span",
        { class: (row.safety_margin_pct ?? 0) >= 0 ? "positive" : "negative" },
        formatPercent(row.safety_margin_pct),
      ),
  },
  {
    title: "预期年化",
    key: "expected_return",
    width: 105,
    render: (row) => formatPercent(row.expected_return.total),
  },
  {
    title: "最大回撤",
    key: "drawdown",
    width: 105,
    render: (row) => formatPercent(row.max_drawdown_pct),
  },
  {
    title: "综合分",
    key: "score",
    width: 120,
    render: (row) =>
      h("div", { class: "table-score-cell" }, [
        h("span", { class: "table-score" }, formatNumber(row.score.total, 1)),
        h(
          NTag,
          { size: "tiny", bordered: false, type: bandType(row.score.band) },
          { default: () => row.score.band },
        ),
      ]),
  },
  {
    title: "数据",
    key: "analysis_date",
    width: 90,
    render: (row) =>
      h(
        "span",
        { class: row.stale_days > 7 ? "stale-text" : "" },
        formatDate(row.analysis_date),
      ),
  },
]);

function selectProfile(value: ProfileCode) {
  router.replace({ query: { ...route.query, profile: value } });
}

function openValuation(id: number) {
  selectedValuationId.value = id;
  detailOpen.value = true;
}

function closeValuation() {
  detailOpen.value = false;
}

function clearFilters() {
  market.value = null;
  path.value = null;
  industry.value = null;
  staleOnly.value = false;
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
  <div class="dashboard">
    <section class="dashboard-hero">
      <div>
        <p class="eyebrow">DECISION SYSTEM / LIVE RANK</p>
        <h1>把估值结论，压缩成可执行的排序。</h1>
        <p class="hero-copy">
          同一把尺子比较安全边际、基础收益、抗跌性与稳定性。价格变化不会改写历史估值，只会改变它今天的位置。
        </p>
      </div>
      <div class="hero-side">
        <span class="section-index">01</span>
        <small>风险调整后的性价比</small>
      </div>
    </section>

    <div class="control-row">
      <ProfileTabs :model-value="profile" @update:model-value="selectProfile" />
      <NButton tertiary size="small" @click="clearFilters">清除筛选</NButton>
    </div>

    <div v-if="query.isPending.value" class="loading-state">
      <NSpin size="large" />
      <span>正在读取估值与排名…</span>
    </div>

    <NAlert v-else-if="query.isError.value" type="error" title="排名暂时不可用">
      <div class="alert-content">
        <span>{{ query.error.value?.message }}</span>
        <NButton size="small" @click="query.refetch()">重新加载</NButton>
      </div>
    </NAlert>

    <template v-else-if="query.data.value">
      <FreshnessBar
        :freshness="query.data.value.freshness"
        :counts="query.data.value.counts"
      />

      <section class="top-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">TOP PICKS</p>
            <h2>当前最值得看的三条</h2>
          </div>
          <NTag :bordered="false">
            {{ query.data.value.profile_label }}权重 · 算法 {{ query.data.value.algorithm_version }}
          </NTag>
        </div>
        <div class="top-grid">
          <TopPickCard
            v-for="item in query.data.value.top_three"
            :key="item.valuation_market_id"
            :item="item"
            @select="openValuation"
          />
        </div>
      </section>

      <section class="analysis-grid">
        <NCard class="scatter-panel" :bordered="false">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">RISK / RETURN MAP</p>
              <h2>性价比象限</h2>
            </div>
            <NTag :bordered="false" size="small">气泡越大，安全边际越高</NTag>
          </div>
          <RankingScatter
            :items="[...query.data.value.main_board, ...query.data.value.etfs]"
            @select="openValuation"
          />
        </NCard>

        <NCard class="filter-panel" :bordered="false">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">NARROW THE POOL</p>
              <h2>筛选池子</h2>
            </div>
          </div>
          <NGrid :cols="1" :y-gap="12">
            <NGridItem>
              <NFormItem label="市场" :show-feedback="false">
                <NSelect
                  v-model:value="market"
                  :options="marketOptions"
                  clearable
                  placeholder="全部市场"
                />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="估值路径" :show-feedback="false">
                <NSelect
                  v-model:value="path"
                  :options="pathOptions"
                  clearable
                  placeholder="全部路径"
                />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="行业" :show-feedback="false">
                <NSelect
                  v-model:value="industry"
                  :options="industryOptions"
                  clearable
                  filterable
                  placeholder="全部行业"
                />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="只看估值偏旧" :show-feedback="false">
                <NSwitch v-model:value="staleOnly" />
              </NFormItem>
            </NGridItem>
          </NGrid>
          <div class="pool-counts">
            <div><small>主榜</small><strong>{{ query.data.value.counts.main_board }}</strong></div>
            <div><small>ETF</small><strong>{{ query.data.value.counts.etfs }}</strong></div>
            <div><small>观察</small><strong>{{ query.data.value.counts.excluded }}</strong></div>
          </div>
        </NCard>
      </section>

      <NCard class="ranking-panel" :bordered="false">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">FULL RANKING</p>
            <h2>完整性价比排名</h2>
          </div>
          <NTag :bordered="false" size="small">点击行在同页展开详情</NTag>
        </div>
        <NDataTable
          v-if="query.data.value.main_board.length"
          class="ranking-table"
          size="small"
          :columns="rankingColumns"
          :data="query.data.value.main_board"
          :row-props="rowProps"
          :bordered="false"
          :single-line="false"
          :pagination="false"
          :scroll-x="1240"
        />
        <NEmpty v-else description="当前筛选没有主榜标的" />
      </NCard>

      <NCard v-if="query.data.value.etfs.length" class="ranking-panel" :bordered="false">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">ETF BOARD</p>
            <h2>ETF 独立观察</h2>
          </div>
        </div>
        <div class="etf-grid">
          <NCard
            v-for="item in query.data.value.etfs"
            :key="item.valuation_market_id"
            size="small"
            hoverable
            class="etf-card"
            @click="openValuation(item.valuation_market_id)"
          >
            <NTag :type="bandType(item.score.band)" size="small" :bordered="false">
              {{ item.score.band }} 档
            </NTag>
            <strong>{{ item.name }}</strong>
            <span>{{ item.code }}</span>
            <small>预期年化 {{ formatPercent(item.expected_return.total) }}</small>
          </NCard>
        </div>
      </NCard>

      <NCollapse v-if="query.data.value.excluded.length" class="excluded-section">
        <NCollapseItem
          :title="`排除 / 观察区（${query.data.value.excluded.length}）`"
          name="excluded"
        >
          <NButton
            v-for="item in query.data.value.excluded"
            :key="item.valuation_market_id"
            block
            text
            class="excluded-row"
            @click="openValuation(item.valuation_market_id)"
          >
            <span>{{ item.name }} {{ item.market }}</span>
            <small>{{ item.excluded_reasons.join("；") }}</small>
          </NButton>
        </NCollapseItem>
      </NCollapse>
    </template>

    <NDrawer
      v-model:show="detailOpen"
      placement="right"
      width="min(1120px, 94vw)"
      :trap-focus="true"
      @after-leave="selectedValuationId = null"
    >
      <NDrawerContent :native-scrollbar="false" closable body-content-style="padding: 0 28px 60px">
        <ValuationDetailPanel
          v-if="selectedValuationId"
          :valuation-market-id="selectedValuationId"
          :profile="profile"
          @close="closeValuation"
        />
      </NDrawerContent>
    </NDrawer>
  </div>
</template>
