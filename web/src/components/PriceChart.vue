<script setup lang="ts">
import { computed } from "vue";
import { formatDateTime, formatEur } from "../lib/format";
import type { PricePoint } from "../types";

const props = defineProps<{ points: PricePoint[] }>();

const W = 520;
const H = 120;

const series = computed(() =>
  props.points.filter((p): p is PricePoint & { price_cents: number } => p.price_cents != null),
);

const chart = computed(() => {
  const values = series.value.map((p) => p.price_cents);
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const line = values
    .map((value, i) => {
      const x = (i / (values.length - 1)) * W;
      const y = H - ((value - min) / span) * (H - 16) - 8;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return { line, area: `${line} L${W},${H} L0,${H} Z`, min: min / 100, max: max / 100 };
});

const delta = computed(() => {
  const values = series.value.map((p) => p.price_cents);
  if (values.length < 2) return "история ещё копится";
  const diff = (values[values.length - 1] - values[0]) / 100;
  if (diff === 0) return "без изменения с первого захода";
  return `${diff > 0 ? "+" : "−"}${formatEur(Math.abs(diff))} с первого захода`;
});
</script>

<template>
  <figure class="price-chart">
    <svg
      v-if="chart"
      class="price-svg"
      :viewBox="`0 0 ${W} ${H}`"
      preserveAspectRatio="none"
      role="img"
      :aria-label="`цена от ${formatEur(chart.min)} до ${formatEur(chart.max)}`"
    >
      <path class="price-area" :d="chart.area" />
      <path class="price-line" :d="chart.line" vector-effect="non-scaling-stroke" />
    </svg>
    <figcaption class="muted small">
      {{ delta }}
      <template v-if="chart"> · мин {{ formatEur(chart.min) }} · макс {{ formatEur(chart.max) }}</template>
      <template v-if="series.length"> · с {{ formatDateTime(series[0].seen_at) }}</template>
    </figcaption>
  </figure>
</template>
