<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import type { ProfileCode } from "@/api/types";
import ValuationDetailPanel from "@/components/ValuationDetailPanel.vue";

const route = useRoute();
const router = useRouter();
const valuationId = computed(() => Number(route.params.id));
const profile = computed<ProfileCode>(() => {
  const value = String(route.query.profile ?? "balanced");
  return ["conservative", "balanced", "aggressive"].includes(value)
    ? (value as ProfileCode)
    : "balanced";
});

function closeDetail() {
  router.push({ name: "dashboard", query: { profile: profile.value } });
}
</script>

<template>
  <div class="standalone-detail">
    <ValuationDetailPanel
      :valuation-market-id="valuationId"
      :profile="profile"
      @close="closeDetail"
    />
  </div>
</template>
