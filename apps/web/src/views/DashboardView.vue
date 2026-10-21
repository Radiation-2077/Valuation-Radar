<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { fetchRanking } from "@/api/client";
import type { ProfileCode, RankingItem, RankingResponse } from "@/api/types";
import FreshnessBar from "@/components/FreshnessBar.vue";
import ProfileTabs from "@/components/ProfileTabs.vue";
import RankingScatter from "@/components/RankingScatter.vue";
import TopPickCard from "@/components/TopPickCard.vue";
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
const market = ref("");
const path = ref("");
const industry = ref("");
const staleOnly = ref(false);

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

function selectProfile(value: ProfileCode) {
  router.replace({ query: { ...route.query, profile: value } });
}

function openValuation(id: number) {
  router.push({
    name: "valuation",
    params: { id },
    query: { profile: profile.value },
  });
}

function clearFilters() {
  market.value = "";
  path.value = "";
  industry.value = "";
  staleOnly.value = false;
}

function topFlags(item: RankingItem): string[] {
  return item.risk_flags.slice(0, 2);
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
      <button class="ghost-button" type="button" @click="clearFilters">清除筛选</button>
    </div>

    <div v-if="query.isPending.value" class="loading-state">
      <span class="loader"></span>
      正在读取估值与排名…
    </div>

    <div v-else-if="query.isError.value" class="error-panel">
      <strong>排名暂时不可用</strong>
      <p>{{ query.error.value?.message }}</p>
      <button type="button" class="primary-button" @click="query.refetch()">重新加载</button>
    </div>

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
          <p>{{ query.data.value.profile_label }}权重 · 算法 {{ query.data.value.algorithm_version }}</p>
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
        <article class="panel scatter-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">RISK / RETURN MAP</p>
              <h2>性价比象限</h2>
            </div>
            <span class="panel-note">气泡越大，安全边际越高</span>
          </div>
          <RankingScatter
            :items="[...query.data.value.main_board, ...query.data.value.etfs]"
            @select="openValuation"
          />
        </article>

        <aside class="panel filter-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">NARROW THE POOL</p>
              <h2>筛选池子</h2>
            </div>
          </div>
          <label>
            <span>市场</span>
            <select v-model="market">
              <option value="">全部市场</option>
              <option
                v-for="value in query.data.value.available_markets"
                :key="value"
                :value="value"
              >
                {{ marketLabels[value] ?? value }}
              </option>
            </select>
          </label>
          <label>
            <span>估值路径</span>
            <select v-model="path">
              <option value="">全部路径</option>
              <option
                v-for="value in query.data.value.available_paths"
                :key="value"
                :value="value"
              >
                {{ pathLabels[value] ?? value }}
              </option>
            </select>
          </label>
          <label>
            <span>行业</span>
            <select v-model="industry">
              <option value="">全部行业</option>
              <option
                v-for="value in query.data.value.available_industries"
                :key="value"
                :value="value"
              >
                {{ value }}
              </option>
            </select>
          </label>
          <label class="toggle-row">
            <span>只看估值偏旧</span>
            <input v-model="staleOnly" type="checkbox" />
          </label>
          <div class="pool-counts">
            <div><small>主榜</small><strong>{{ query.data.value.counts.main_board }}</strong></div>
            <div><small>ETF</small><strong>{{ query.data.value.counts.etfs }}</strong></div>
            <div><small>观察</small><strong>{{ query.data.value.counts.excluded }}</strong></div>
          </div>
        </aside>
      </section>

      <section class="panel ranking-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">FULL RANKING</p>
            <h2>完整性价比排名</h2>
          </div>
          <span class="panel-note">点击任意标的查看估值详情</span>
        </div>
        <div v-if="query.data.value.main_board.length" class="table-wrap">
          <table class="ranking-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>标的</th>
                <th>行业 / 路径</th>
                <th>现价</th>
                <th>安全边际</th>
                <th>预期年化</th>
                <th>最大回撤</th>
                <th>综合分</th>
                <th>数据</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in query.data.value.main_board"
                :key="item.valuation_market_id"
                tabindex="0"
                @click="openValuation(item.valuation_market_id)"
                @keydown.enter="openValuation(item.valuation_market_id)"
              >
                <td><span class="rank-number">{{ item.rank }}</span></td>
                <td>
                  <strong class="security-name">{{ item.name }}</strong>
                  <span class="security-code">{{ item.market }} · {{ item.code }}</span>
                  <span v-for="flag in topFlags(item)" :key="flag" class="mini-tag">
                    {{ flag }}
                  </span>
                </td>
                <td>
                  <span>{{ item.industry }}</span>
                  <small class="cell-sub">{{ pathLabels[item.path] ?? item.path }}</small>
                </td>
                <td>{{ formatMoney(item.price, item.currency) }}</td>
                <td :class="{ positive: (item.safety_margin_pct ?? 0) >= 0 }">
                  {{ formatPercent(item.safety_margin_pct) }}
                </td>
                <td>{{ formatPercent(item.expected_return.total) }}</td>
                <td>{{ formatPercent(item.max_drawdown_pct) }}</td>
                <td>
                  <span class="table-score">{{ formatNumber(item.score.total, 1) }}</span>
                  <span class="band" :class="`band--${item.score.band.toLowerCase()}`">
                    {{ item.score.band }}
                  </span>
                </td>
                <td>
                  <span :class="{ 'stale-text': item.stale_days > 7 }">
                    {{ formatDate(item.analysis_date) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-panel">当前筛选没有主榜标的。</div>
      </section>

      <section v-if="query.data.value.etfs.length" class="panel ranking-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">ETF BOARD</p>
            <h2>ETF 独立观察</h2>
          </div>
        </div>
        <div class="etf-grid">
          <button
            v-for="item in query.data.value.etfs"
            :key="item.valuation_market_id"
            class="etf-card"
            type="button"
            @click="openValuation(item.valuation_market_id)"
          >
            <span class="band" :class="`band--${item.score.band.toLowerCase()}`">
              {{ item.score.band }}
            </span>
            <strong>{{ item.name }}</strong>
            <span>{{ item.code }}</span>
            <div>
              <small>预期年化</small>
              <b>{{ formatPercent(item.expected_return.total) }}</b>
            </div>
          </button>
        </div>
      </section>

      <details v-if="query.data.value.excluded.length" class="excluded-section">
        <summary>排除 / 观察区（{{ query.data.value.excluded.length }}）</summary>
        <button
          v-for="item in query.data.value.excluded"
          :key="item.valuation_market_id"
          type="button"
          @click="openValuation(item.valuation_market_id)"
        >
          <span>{{ item.name }} {{ item.market }}</span>
          <small>{{ item.excluded_reasons.join("；") }}</small>
        </button>
      </details>
    </template>
  </div>
</template>
