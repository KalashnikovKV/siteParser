<script setup lang="ts">
import { computed } from "vue";
import type { PricePoint } from "../types";

const props = defineProps<{ points: PricePoint[] }>();

const path = computed(() => {
  const values = props.points
    .map((p) => p.price_cents)
    .filter((v): v is number => v != null);
  if (values.length < 2) return "";
  const w = 520;
  const h = 110;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((value, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((value - min) / span) * (h - 8) - 4;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
});

const delta = computed(() => {
  const values = props.points
    .map((p) => p.price_cents)
    .filter((v): v is number => v != null);
  if (values.length < 2) return "история ещё копится";
  const diff = (values[values.length - 1] - values[0]) / 100;
  if (diff === 0) return "без изменения с первого захода";
  const sign = diff > 0 ? "+" : "";
  return `${sign}${diff.toFixed(0)} € с первого захода`;
});
</script>

<template>
  <div>
    <svg v-if="path" class="price-svg" viewBox="0 0 520 120" preserveAspectRatio="none">
      <path :d="path" fill="none" stroke="#7dd3a8" stroke-width="3" />
    </svg>
    <div class="muted">{{ delta }}</div>
  </div>
</template>
