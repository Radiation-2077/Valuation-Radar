<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";
import {
  NAlert,
  NButton,
  NCard,
  NGrid,
  NGridItem,
  NIcon,
  NModal,
  NSpace,
  NSpin,
  NStatistic,
  NTag,
  NText,
} from "naive-ui";
import { CheckmarkCircleOutline, CloseCircleOutline } from "@vicons/ionicons5";
import { computed } from "vue";

import { fetchValuation } from "@/api/client";
import type { Review } from "@/api/types";
import ReportDetailSections from "@/components/ReportDetailSections.vue";
import {
  formatDateTime,
  formatMoney,
  formatMoneyRange,
  formatNumber,
  formatPercent,
} from "@/lib/format";

const props = defineProps<{
  review: Review;
  mode: "pending" | "rejected";
  decisionLoading?: "approve" | "reject" | null;
}>();
const emit = defineEmits<{
  close: [];
  decide: [decision: "approve" | "reject"];
}>();

const previewQuery = useQuery({
  queryKey: ["review-preview", props.review.report_id],
  queryFn: () =>
    Promise.all(
      props.review.markets.map((market) =>
        fetchValuation(market.valuation_market_id, "balanced"),
      ),
    ),
});

const title = computed(() =>
  props.mode === "pending" ? "候选估值预览" : "已拒绝候选预览",
);

function close() {
  if (!props.decisionLoading) emit("close");
}
</script>

<template>
  <NModal
    :show="true"
    preset="card"
    :title="title"
    :bordered="false"
    :mask-closable="!decisionLoading"
    :close-on-esc="!decisionLoading"
    :closable="!decisionLoading"
    class="review-preview-modal"
    style="width: min(1120px, 94vw)"
    @update:show="(show: boolean) => { if (!show) close(); }"
  >
    <div class="review-preview-shell">
      <div class="review-preview-body">
        <NSpace vertical :size="16">
          <NSpace align="center" justify="space-between">
            <NSpace vertical :size="4">
              <NText strong class="review-preview-name">{{ review.name }}</NText>
              <NText depth="3">
                {{ formatDateTime(review.generated_at) }} · 置信度 {{ review.confidence }}
              </NText>
            </NSpace>
            <NTag
              :type="mode === 'pending' ? 'warning' : 'error'"
              :bordered="false"
            >
              {{ mode === "pending" ? "待复核" : "已拒绝" }}
            </NTag>
          </NSpace>

          <NAlert type="info" title="投资 thesis" :bordered="false">
            {{ review.thesis }}
          </NAlert>

          <div v-if="previewQuery.isPending.value" class="loading-state">
            <NSpin size="large" />
            <span>正在加载完整候选估值…</span>
          </div>
          <NAlert
            v-else-if="previewQuery.isError.value"
            type="error"
            title="候选详情读取失败"
          >
            {{ previewQuery.error.value?.message }}
          </NAlert>
          <NSpace v-else-if="previewQuery.data.value" vertical :size="20">
            <NCard
              v-for="detail in previewQuery.data.value"
              :key="detail.valuation_market_id"
              size="small"
              :bordered="false"
            >
              <NSpace vertical :size="16">
                <NSpace align="center" justify="space-between">
                  <NSpace align="center" :size="10">
                    <NText strong>{{ detail.market }} · {{ detail.code }}</NText>
                    <NTag :bordered="false">{{ detail.cycle.stage }}</NTag>
                  </NSpace>
                  <NText strong>{{ detail.verdict }}</NText>
                </NSpace>

                <NGrid responsive="screen" cols="1 s:2 m:4" :x-gap="12" :y-gap="12">
                  <NGridItem>
                    <NStatistic
                      label="现价"
                      :value="formatMoney(detail.price, detail.currency)"
                    />
                  </NGridItem>
                  <NGridItem>
                    <NStatistic
                      label="合理区间"
                      :value="formatMoneyRange(
                        detail.fair_low,
                        detail.fair_high,
                        detail.currency,
                      )"
                    />
                  </NGridItem>
                  <NGridItem>
                    <NStatistic
                      label="当前安全边际"
                      :value="formatPercent(detail.effective_safety_margin_pct)"
                    />
                  </NGridItem>
                  <NGridItem>
                    <NStatistic
                      label="综合评分"
                      :value="formatNumber(detail.score.total, 1)"
                    />
                  </NGridItem>
                </NGrid>

                <ReportDetailSections
                  v-if="detail.report_detail.sections?.length"
                  :sections="detail.report_detail.sections"
                  :market="detail.market"
                />
                <NAlert v-else type="warning" title="暂无结构化章节">
                  候选报告没有可预览的结构化章节。
                </NAlert>
              </NSpace>
            </NCard>
          </NSpace>
        </NSpace>
      </div>

      <div class="review-preview-actions">
        <NSpace justify="end" align="center">
          <template v-if="mode === 'pending'">
            <NButton
              type="error"
              secondary
              :disabled="Boolean(decisionLoading)"
              :loading="decisionLoading === 'reject'"
              @click="emit('decide', 'reject')"
            >
              <template #icon>
                <NIcon :component="CloseCircleOutline" />
              </template>
              拒绝候选
            </NButton>
            <NButton
              type="primary"
              :disabled="Boolean(decisionLoading)"
              :loading="decisionLoading === 'approve'"
              @click="emit('decide', 'approve')"
            >
              <template #icon>
                <NIcon :component="CheckmarkCircleOutline" />
              </template>
              批准并发布
            </NButton>
          </template>
          <NButton v-else secondary @click="close">关闭预览</NButton>
        </NSpace>
      </div>
    </div>
  </NModal>
</template>
