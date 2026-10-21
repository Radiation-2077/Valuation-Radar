<script setup lang="ts">
import {
  NConfigProvider,
  NDialogProvider,
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
import { computed } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const menuOptions = [
  { label: "性价比排名", key: "/" },
  { label: "更新中心", key: "/updates" },
];
const activeMenu = computed(() => (route.path === "/updates" ? "/updates" : "/"));
</script>

<template>
  <NConfigProvider :theme="darkTheme" :locale="zhCN" :date-locale="dateZhCN">
    <NDialogProvider>
      <NMessageProvider>
        <NLayout class="app-layout">
          <NLayoutHeader bordered>
            <div class="header-layout">
              <RouterLink to="/">
                <NSpace align="center">
                  <NTag type="success" :bordered="false">估</NTag>
                  <strong>估值雷达</strong>
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
              <NTag type="success" :bordered="false">LOCAL DATA</NTag>
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
