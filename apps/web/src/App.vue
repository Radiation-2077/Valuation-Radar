<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink class="brand" to="/">
        <span class="brand-mark" aria-hidden="true">估</span>
        <span>
          <strong>估值雷达</strong>
          <small>VALUATION RADAR</small>
        </span>
      </RouterLink>
      <nav aria-label="主导航">
        <RouterLink to="/">性价比排名</RouterLink>
        <RouterLink to="/updates">更新中心</RouterLink>
      </nav>
      <span class="environment"><i></i> LOCAL DATA</span>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>
