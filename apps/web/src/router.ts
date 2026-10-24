import { createRouter, createWebHistory } from "vue-router";

import DashboardView from "./views/DashboardView.vue";
import UpdatesView from "./views/UpdatesView.vue";
import ValuationDetailView from "./views/ValuationDetailView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "dashboard",
      component: DashboardView,
      meta: { title: "性价比排名" },
    },
    {
      path: "/valuations/:id",
      name: "valuation",
      component: ValuationDetailView,
      meta: { title: "估值详情" },
    },
    {
      path: "/updates",
      name: "updates",
      component: UpdatesView,
      meta: { title: "更新中心" },
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/",
    },
  ],
  scrollBehavior: () => ({ top: 0 }),
});

export default router;
