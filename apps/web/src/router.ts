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
    },
    {
      path: "/valuations/:id",
      name: "valuation",
      component: ValuationDetailView,
    },
    {
      path: "/updates",
      name: "updates",
      component: UpdatesView,
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/",
    },
  ],
  scrollBehavior: () => ({ top: 0 }),
});

export default router;
