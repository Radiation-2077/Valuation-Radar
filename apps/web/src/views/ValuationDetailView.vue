<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";
import { computed, watchEffect } from "vue";
import { useRoute, useRouter } from "vue-router";

import { fetchValuation } from "@/api/client";
import type { ProfileCode } from "@/api/types";
import FairValueBand from "@/components/FairValueBand.vue";
import ReturnBreakdown from "@/components/ReturnBreakdown.vue";
import ScoreBars from "@/components/ScoreBars.vue";
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
const valuationId = computed(() => Number(route.params.id));
const profile = computed<ProfileCode>(() => {
  const value = String(route.query.profile ?? "balanced");
  return ["conservative", "balanced", "aggressive"].includes(value)
    ? (value as ProfileCode)
    : "balanced";
});

const query = useQuery({
  queryKey: computed(() => ["valuation", valuationId.value, profile.value]),
  queryFn: () => fetchValuation(valuationId.value, profile.value),
  enabled: computed(() => Number.isFinite(valuationId.value)),
});

watchEffect(() => {
  if (query.data.value) {
    document.title = `${query.data.value.name} ${query.data.value.market} · 估值雷达`;
  }
});

function goBack() {
  router.push({ name: "dashboard", query: { profile: profile.value } });
}

const kpis = computed(() => {
  const data = query.data.value;
  if (!data) return [];
  return [
    {
      label: "当前安全边际",
      value: formatPercent(data.effective_safety_margin_pct),
      className: (data.effective_safety_margin_pct ?? 0) >= 0 ? "positive" : "negative",
    },
    {
      label: "预期年化",
      value: formatPercent(data.expected_return.total),
      className: "positive",
    },
    {
      label: "悲观回撤",
      value: formatPercent(data.downside.max_drawdown_pct),
      className: "negative",
    },
    {
      label: "建议目标仓位",
      value: formatPercent(data.position.target_pct, 0),
      className: "",
    },
  ];
});
</script>

<template>
  <div class="detail-view">
    <button class="back-link" type="button" @click="goBack">← 返回排名</button>

    <div v-if="query.isPending.value" class="loading-state">
      <span class="loader"></span>
      正在展开估值分析…
    </div>
    <div v-else-if="query.isError.value" class="error-panel">
      <strong>无法读取估值详情</strong>
      <p>{{ query.error.value?.message }}</p>
      <button class="primary-button" type="button" @click="query.refetch()">重试</button>
    </div>

    <template v-else-if="query.data.value">
      <header class="detail-hero">
        <div class="detail-identity">
          <p class="eyebrow">
            {{ pathLabels[query.data.value.path] ?? query.data.value.path }} /
            {{ query.data.value.industry }}
          </p>
          <div class="detail-title">
            <h1>{{ query.data.value.name }}</h1>
            <span>{{ marketLabels[query.data.value.market] ?? query.data.value.market }}</span>
            <small>{{ query.data.value.code }}</small>
          </div>
          <p class="detail-thesis">{{ query.data.value.conclusion.thesis }}</p>
        </div>
        <div class="verdict-panel">
          <span class="verdict-label">当前结论</span>
          <strong>{{ query.data.value.verdict }}</strong>
          <div>
            <span class="band" :class="`band--${query.data.value.score.band.toLowerCase()}`">
              {{ query.data.value.score.band }} 档
            </span>
            <span>综合 {{ formatNumber(query.data.value.score.total, 1) }}</span>
            <span>置信 {{ query.data.value.conclusion.confidence }}</span>
          </div>
          <small>
            估值 {{ formatDate(query.data.value.analysis_date) }} · 行情
            {{ formatDate(query.data.value.price_date) }}
          </small>
        </div>
      </header>

      <section class="kpi-grid">
        <article v-for="kpi in kpis" :key="kpi.label">
          <small>{{ kpi.label }}</small>
          <strong :class="kpi.className">{{ kpi.value }}</strong>
        </article>
      </section>

      <section class="detail-grid">
        <article class="panel fair-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">VALUATION BAND</p>
              <h2>价格相对合理区间</h2>
            </div>
            <span class="panel-note">
              基线 {{ formatPercent(query.data.value.safety_margin_pct) }}
            </span>
          </div>
          <FairValueBand
            :low="query.data.value.fair_low"
            :mid="query.data.value.fair_mid"
            :high="query.data.value.fair_high"
            :price="query.data.value.price"
            :currency="query.data.value.currency"
          />
          <div class="valuation-metrics">
            <div>
              <small>PE</small>
              <strong>{{ formatNumber(query.data.value.valuation.pe) }}</strong>
            </div>
            <div>
              <small>PB</small>
              <strong>{{ formatNumber(query.data.value.valuation.pb) }}</strong>
            </div>
            <div>
              <small>税后股息率</small>
              <strong>{{ formatPercent(query.data.value.valuation.dividend_yield_after_tax) }}</strong>
            </div>
            <div>
              <small>估值分位</small>
              <strong>{{ formatPercent(query.data.value.valuation.percentile, 0) }}</strong>
            </div>
          </div>
        </article>

        <article class="panel score-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">FOUR DIMENSIONS</p>
              <h2>评分拆解</h2>
            </div>
            <span class="panel-note">{{ formatPercent(query.data.value.score.total) }} 综合分</span>
          </div>
          <ScoreBars :score="query.data.value.score" />
          <div class="score-note">
            <span>收益质量</span>
            <strong>
              {{
                query.data.value.risk_flags.includes("依赖估值回归")
                  ? "偏依赖估值修复"
                  : "经营收益占比较高"
              }}
            </strong>
          </div>
        </article>

        <article class="panel return-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">EXPECTED RETURN</p>
              <h2>预期年化来自哪里</h2>
            </div>
          </div>
          <ReturnBreakdown :data="query.data.value.expected_return" />
          <p class="panel-footnote">
            便宜只计一次：安全边际负责估值修复，基础收益只取股息、增长与汇率。
          </p>
        </article>

        <article class="panel quality-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">BUSINESS QUALITY</p>
              <h2>质地与周期</h2>
            </div>
          </div>
          <div class="quality-score">
            <span>{{ query.data.value.quality.rating }}★</span>
            <div>
              <strong>{{ query.data.value.quality.label }}</strong>
              <small>
                护城河：{{ query.data.value.quality.moat }} · 质地分
                {{ query.data.value.quality.score }}
              </small>
            </div>
          </div>
          <dl class="fact-list">
            <div><dt>产业周期</dt><dd>{{ query.data.value.cycle.stage }}</dd></div>
            <div>
              <dt>周期位置</dt>
              <dd>{{ formatNumber(query.data.value.cycle.position, 0) }}</dd>
            </div>
            <div>
              <dt>估值路径</dt>
              <dd>{{ pathLabels[query.data.value.path] ?? query.data.value.path }}</dd>
            </div>
            <div>
              <dt>质地门槛</dt>
              <dd>{{ query.data.value.quality.gate_pass ? "通过" : query.data.value.quality.gate_reason }}</dd>
            </div>
          </dl>
        </article>
      </section>

      <section class="detail-grid lower-grid">
        <article class="panel position-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">POSITION PLAN</p>
              <h2>仓位与执行</h2>
            </div>
          </div>
          <div class="position-values">
            <div>
              <small>起步</small>
              <strong>{{ formatPercent(query.data.value.position.base_pct, 0) }}</strong>
            </div>
            <div>
              <small>目标</small>
              <strong>{{ formatPercent(query.data.value.position.target_pct, 0) }}</strong>
            </div>
            <div>
              <small>上限</small>
              <strong>{{ formatPercent(query.data.value.position.cap_pct, 0) }}</strong>
            </div>
          </div>
          <p class="buy-points">{{ query.data.value.position.buy_points }}</p>
          <div class="downside-note">
            <small>悲观情景</small>
            <strong>{{ formatPercent(query.data.value.downside.max_drawdown_pct) }}</strong>
            <p>{{ query.data.value.downside.scenario }}</p>
          </div>
        </article>

        <article class="panel risk-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">RISK MAP</p>
              <h2>关键风险与反证</h2>
            </div>
          </div>
          <ol class="risk-list">
            <li v-for="risk in query.data.value.risks" :key="risk">{{ risk }}</li>
          </ol>
        </article>

        <article v-if="query.data.value.same_company.length" class="panel same-company-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">CROSS MARKET</p>
              <h2>同一资产的其他市场</h2>
            </div>
          </div>
          <button
            v-for="other in query.data.value.same_company"
            :key="other.valuation_market_id"
            type="button"
            @click="
              router.push({
                name: 'valuation',
                params: { id: other.valuation_market_id },
                query: { profile },
              })
            "
          >
            <span>{{ other.market }} · {{ other.code }}</span>
            <strong>{{ formatMoney(other.price, other.currency) }}</strong>
            <small>
              安全边际 {{ formatPercent(other.safety_margin_pct) }} · {{ other.verdict }}
            </small>
          </button>
          <p class="panel-footnote">两地同持属于同一公司敞口，仓位需要合并计算。</p>
        </article>
      </section>

      <details v-if="query.data.value.missing.length" class="missing-section">
        <summary>数据缺口（{{ query.data.value.missing.length }}）</summary>
        <ul>
          <li v-for="item in query.data.value.missing" :key="item">{{ item }}</li>
        </ul>
      </details>

      <section class="source-section">
        <div>
          <p class="eyebrow">TRACEABILITY</p>
          <h2>口径与来源</h2>
          <p>{{ query.data.value.notes }}</p>
        </div>
        <a
          v-if="query.data.value.report_url"
          class="primary-button"
          :href="query.data.value.report_url"
          target="_blank"
          rel="noopener"
        >
          查看原估值报告 ↗
        </a>
      </section>
    </template>
  </div>
</template>
