<script setup lang="ts">
import {
  NConfigProvider,
  NDialogProvider,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NMenu,
  NMessageProvider,
  NSpace,
  NTag,
  darkTheme,
  dateZhCN,
  zhCN,
} from "naive-ui";
import { AnalyticsOutline, PulseOutline, SyncOutline } from "@vicons/ionicons5";
import { computed, h } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";

import { themeOverrides } from "@/theme";

const route = useRoute();
const router = useRouter();
const menuOptions = [
  {
    label: "性价比排名",
    key: "/",
    icon: () => h(NIcon, null, { default: () => h(AnalyticsOutline) }),
  },
  {
    label: "更新中心",
    key: "/updates",
    icon: () => h(NIcon, null, { default: () => h(SyncOutline) }),
  },
];
const activeMenu = computed(() => (route.path === "/updates" ? "/updates" : "/"));
</script>

<template>
  <NConfigProvider
    :theme="darkTheme"
    :theme-overrides="themeOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <NDialogProvider>
      <NMessageProvider>
        <NLayout class="app-layout">
          <NLayoutHeader bordered>
            <div class="header-layout">
              <RouterLink to="/">
                <NSpace align="center" class="brand">
                  <span class="brand-mark">估</span>
                  <span class="brand-copy">
                    <strong>估值雷达</strong>
                    <small>VALUATION RADAR</small>
                  </span>
                </NSpace>
              </RouterLink>
              <div class="header-menu">
                <NMenu
                  mode="horizontal"
                  :options="menuOptions"
                  :value="activeMenu"
                  @update:value="(key: string) => router.push(key)"
                />
              </div>
              <NTag type="success" :bordered="false" class="header-status">
                <NIcon :component="PulseOutline" />
                LOCAL DATA
              </NTag>
            </div>
          </NLayoutHeader>
          <NLayoutContent>
            <main class="page-content">
              <RouterView />
            </main>
          </NLayoutContent>
        </NLayout>
      </NMessageProvider>
    </NDialogProvider>
  </NConfigProvider>
</template>
