<script setup lang="ts">
import {
  NConfigProvider,
  NDialogProvider,
  NMessageProvider,
  NMenu,
  NTag,
  darkTheme,
  dateZhCN,
  zhCN,
  type GlobalThemeOverrides,
} from "naive-ui";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { RouterLink, RouterView } from "vue-router";

const route = useRoute();
const router = useRouter();
const menuOptions = [
  { label: "性价比排名", key: "/" },
  { label: "更新中心", key: "/updates" },
];
const activeMenu = computed(() => (route.path === "/updates" ? "/updates" : "/"));

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#57d6b1",
    primaryColorHover: "#72e4c3",
    primaryColorPressed: "#42bd9b",
    primaryColorSuppl: "#57d6b1",
    infoColor: "#80c7ff",
    warningColor: "#e8b86d",
    errorColor: "#ee8c78",
    successColor: "#57d6b1",
    bodyColor: "#07131f",
    cardColor: "#0d2030",
    modalColor: "#0a1a27",
    popoverColor: "#0d2030",
    textColorBase: "#dce7ef",
    textColor1: "#dce7ef",
    textColor2: "#a9bac6",
    textColor3: "#8296a5",
    borderColor: "rgba(158, 190, 210, 0.18)",
    dividerColor: "rgba(158, 190, 210, 0.14)",
    borderRadius: "10px",
  },
  Drawer: {
    color: "#081622",
  },
  DataTable: {
    thColor: "transparent",
    tdColor: "transparent",
    tdColorHover: "rgba(87, 214, 177, 0.04)",
    borderColor: "rgba(158, 190, 210, 0.12)",
  },
};
</script>

<template>
  <NConfigProvider
    :theme="darkTheme"
    :locale="zhCN"
    :date-locale="dateZhCN"
    :theme-overrides="themeOverrides"
  >
    <NDialogProvider>
      <NMessageProvider>
        <div class="app-shell">
          <header class="app-header">
            <RouterLink class="brand" to="/">
              <span class="brand-mark" aria-hidden="true">估</span>
              <span>
                <strong>估值雷达</strong>
                <small>VALUATION RADAR</small>
              </span>
            </RouterLink>
            <NMenu
              mode="horizontal"
              :options="menuOptions"
              :value="activeMenu"
              @update:value="(key: string) => router.push(key)"
            />
            <NTag class="environment" size="small" :bordered="false" type="success">
              <span class="environment-dot"></span> LOCAL DATA
            </NTag>
          </header>
          <main>
            <RouterView />
          </main>
        </div>
      </NMessageProvider>
    </NDialogProvider>
  </NConfigProvider>
</template>
