import type { RouteLocationNormalizedLoaded } from "vue-router";

export const APP_TITLE = "估值雷达";

export function routeDocumentTitle(route: RouteLocationNormalizedLoaded): string {
  const sectionTitle = typeof route.meta.title === "string" ? route.meta.title : "";
  return sectionTitle ? `${sectionTitle} · ${APP_TITLE}` : APP_TITLE;
}

export function valuationDocumentTitle(name: string, market: string): string {
  return `${name} ${market} · ${APP_TITLE}`;
}
