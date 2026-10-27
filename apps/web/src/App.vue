<script setup lang="ts">
import {
  NConfigProvider,
  NDialogProvider,
  NButton,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NMenu,
  NMessageProvider,
  NPopover,
  NScrollbar,
  NSpace,
  NTooltip,
  darkTheme,
  dateZhCN,
  lightTheme,
  zhCN,
  type ScrollbarInst,
} from "naive-ui";
import {
  LinkOutline,
  MenuOutline,
  MoonOutline,
  SunnyOutline,
  SyncOutline,
  TrophyOutline,
} from "@vicons/ionicons5";
import {
  computed,
  h,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  watchEffect,
} from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";

import BrandLogo from "@/components/BrandLogo.vue";
import { routeDocumentTitle } from "@/lib/page-title";
import { darkThemeOverrides, lightThemeOverrides } from "@/theme";

const route = useRoute();
const router = useRouter();
const scrollbarRef = ref<ScrollbarInst | null>(null);
type ThemePreference = "system" | "light" | "dark";
const themeStorageKey = "valuation-radar-theme";
const savedTheme = localStorage.getItem(themeStorageKey);
const themePreference = ref<ThemePreference>(
  savedTheme === "light" || savedTheme === "dark" ? savedTheme : "system",
);
const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
const systemDark = ref(prefersDark.matches);
const isDark = computed(() =>
  themePreference.value === "system"
    ? systemDark.value
    : themePreference.value === "dark",
);
const activeTheme = computed(() => (isDark.value ? darkTheme : lightTheme));
const activeThemeOverrides = computed(() =>
  isDark.value ? darkThemeOverrides : lightThemeOverrides,
);
const connectionTooltipVisible = ref(false);
const mobileNavOpen = ref(false);
const menuOptions = [
  {
    label: "性价比排名",
    key: "/",
    icon: () => h(NIcon, null, { default: () => h(TrophyOutline) }),
  },
  {
    label: "更新中心",
    key: "/updates",
    icon: () => h(NIcon, null, { default: () => h(SyncOutline) }),
  },
];
const activeMenu = computed(() => {
  return route.path === "/updates" ? "/updates" : "/";
});

watch(
  () => route.fullPath,
  async () => {
    mobileNavOpen.value = false;
    await nextTick();
    scrollbarRef.value?.scrollTo({ top: 0 });
  },
);

watch(
  () => route.name,
  () => {
    document.title = routeDocumentTitle(route);
  },
  { immediate: true },
);

onMounted(() => {
  prefersDark.addEventListener("change", handleSystemThemeChange);
});

onBeforeUnmount(() => {
  prefersDark.removeEventListener("change", handleSystemThemeChange);
});

watchEffect(() => {
  document.documentElement.dataset.theme = isDark.value ? "dark" : "light";
  document.documentElement.style.colorScheme = isDark.value ? "dark" : "light";
});

function handleSystemThemeChange(event: MediaQueryListEvent) {
  systemDark.value = event.matches;
}

function toggleTheme() {
  themePreference.value = isDark.value ? "light" : "dark";
  localStorage.setItem(themeStorageKey, themePreference.value);
}

function navigateFromMenu(key: string) {
  mobileNavOpen.value = false;
  router.push(key);
}
</script>

<template>
  <NConfigProvider
    :theme="activeTheme"
    :theme-overrides="activeThemeOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <NDialogProvider>
      <NMessageProvider>
        <NLayout class="app-layout">
          <NLayoutHeader bordered>
            <div class="header-layout">
              <RouterLink to="/">
                <NSpace align="end" class="brand">
                  <BrandLogo class="brand-mark" />
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
              <div class="header-actions">
                <NTooltip
                  :show="connectionTooltipVisible"
                  trigger="manual"
                  placement="bottom"
                >
                  <template #trigger>
                    <span
                      class="header-status"
                      role="img"
                      tabindex="0"
                      aria-label="服务已连接"
                      @mouseenter="connectionTooltipVisible = true"
                      @mouseleave="connectionTooltipVisible = false"
                      @focus="connectionTooltipVisible = true"
                      @blur="connectionTooltipVisible = false"
                    >
                      <NIcon :component="LinkOutline" :size="20" aria-hidden="true" />
                    </span>
                  </template>
                  <span role="tooltip">服务已连接</span>
                </NTooltip>
                <NButton
                  quaternary
                  circle
                  class="theme-toggle"
                  :aria-label="isDark ? '切换到亮色模式' : '切换到暗色模式'"
                  :title="isDark ? '切换到亮色模式' : '切换到暗色模式'"
                  @click="toggleTheme"
                >
                  <template #icon>
                    <NIcon :component="isDark ? SunnyOutline : MoonOutline" :size="20" />
                  </template>
                </NButton>
                <div class="mobile-navigation">
                  <NPopover
                    v-model:show="mobileNavOpen"
                    trigger="click"
                    placement="bottom-end"
                    :show-arrow="false"
                    :width="196"
                  >
                    <template #trigger>
                      <NButton
                        quaternary
                        circle
                        class="mobile-nav-toggle"
                        :aria-label="mobileNavOpen ? '关闭导航菜单' : '打开导航菜单'"
                        aria-haspopup="menu"
                        :aria-expanded="mobileNavOpen"
                      >
                        <template #icon>
                          <NIcon :component="MenuOutline" :size="22" />
                        </template>
                      </NButton>
                    </template>
                    <NMenu
                      mode="vertical"
                      aria-label="主导航"
                      :options="menuOptions"
                      :value="activeMenu"
                      @update:value="navigateFromMenu"
                    />
                  </NPopover>
                </div>
              </div>
            </div>
          </NLayoutHeader>
          <NLayoutContent>
            <NScrollbar ref="scrollbarRef" class="app-scrollbar">
              <main class="page-content">
                <RouterView />
              </main>
            </NScrollbar>
          </NLayoutContent>
        </NLayout>
      </NMessageProvider>
    </NDialogProvider>
  </NConfigProvider>
</template>
