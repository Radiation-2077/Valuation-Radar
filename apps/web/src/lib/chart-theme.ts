export interface ChartThemeColors {
  text: string;
  muted: string;
  labelBackground: string;
  labelText: string;
  track: string;
  border: string;
  accent: string;
  warm: string;
  red: string;
  blue: string;
}

export function chartThemeColors(): ChartThemeColors {
  const root = document.documentElement;
  const style = getComputedStyle(root);
  const light = root.dataset.theme === "light";
  const value = (name: string, fallback: string) =>
    style.getPropertyValue(name).trim() || fallback;
  return {
    text: value("--ui-text-strong", light ? "#20343f" : "#e0eef6"),
    muted: value("--ui-chart-muted", light ? "#526b78" : "#a9bac6"),
    labelBackground: value(
      "--ui-chart-label-bg",
      light ? "rgba(255,255,255,.96)" : "rgba(7,19,31,.92)",
    ),
    labelText: value("--ui-chart-label-text", light ? "#172833" : "#dce7ef"),
    track: value(
      "--ui-chart-track",
      light ? "rgba(38,73,91,.12)" : "rgba(158,190,210,.14)",
    ),
    border: value(
      "--ui-line",
      light ? "rgba(38,73,91,.16)" : "rgba(158,190,210,.16)",
    ),
    accent: value("--ui-accent", light ? "#0e9f7d" : "#57d6b1"),
    warm: value("--ui-warm", light ? "#b77a1f" : "#e8b86d"),
    red: value("--ui-red", light ? "#c45645" : "#ee8c78"),
    blue: light ? "#3478c8" : "#80c7ff",
  };
}

export function observeChartTheme(render: () => void): () => void {
  const observer = new MutationObserver(render);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  return () => observer.disconnect();
}
