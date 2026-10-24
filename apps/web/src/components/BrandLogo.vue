<script setup lang="ts">
defineOptions({ inheritAttrs: false });
</script>

<template>
  <svg
    v-bind="$attrs"
    class="brand-logo"
    viewBox="0 0 48 48"
    aria-hidden="true"
    focusable="false"
  >
    <defs>
      <linearGradient id="brand-tile-gradient" x1="6" y1="4" x2="42" y2="45">
        <stop class="brand-logo__tile-start" offset="0" />
        <stop class="brand-logo__tile-end" offset="1" />
      </linearGradient>
      <linearGradient id="brand-value-gradient" x1="11" y1="33" x2="37" y2="15">
        <stop class="brand-logo__value-start" offset="0" />
        <stop class="brand-logo__value-end" offset="1" />
      </linearGradient>
      <radialGradient id="brand-signal-gradient">
        <stop class="brand-logo__signal-start" offset="0" />
        <stop class="brand-logo__signal-end" offset="1" />
      </radialGradient>
    </defs>

    <rect
      class="brand-logo__tile"
      x="2.5"
      y="2.5"
      width="43"
      height="43"
      rx="13"
      fill="url(#brand-tile-gradient)"
    />

    <g class="brand-logo__radar">
      <circle cx="24" cy="24" r="16.5" />
      <circle class="brand-logo__radar-inner" cx="24" cy="24" r="10.5" />
      <path d="M24 7.5v4M24 36.5v4M7.5 24h4M36.5 24h4" />
      <path class="brand-logo__sweep" d="M24 24L37 14.5A16.5 16.5 0 0 1 39.5 29Z" />
    </g>

    <path
      class="brand-logo__value"
      d="M11.5 33.5 19.5 25l6 3.2L37 15.5"
      fill="none"
      stroke="url(#brand-value-gradient)"
    />
    <circle class="brand-logo__signal-glow" cx="37" cy="15.5" r="6" />
    <circle class="brand-logo__signal-core" cx="37" cy="15.5" r="2.7" />
  </svg>
</template>
