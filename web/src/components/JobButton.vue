<script setup lang="ts">
import { computed } from "vue";
import type { JobStatus } from "../types";

const props = defineProps<{
  label: string;
  busyLabel: string;
  busy: boolean;
  job: JobStatus | null;
  primary?: boolean;
  hint?: string;
}>();
defineEmits<{ start: [] }>();

const counter = computed(() => {
  if (!props.busy || !props.job?.total) return "";
  return `${props.job.done}/${props.job.total}`;
});
</script>

<template>
  <button
    type="button"
    class="job-button"
    :class="{ primary, busy }"
    :disabled="busy"
    :aria-busy="busy"
    :title="hint"
    @click="$emit('start')"
  >
    <span class="job-label">
      {{ busy ? busyLabel : label }}
      <span v-if="counter" class="job-counter">{{ counter }}</span>
    </span>
    <progress
      v-if="busy"
      class="job-progress"
      :max="job?.total || undefined"
      :value="job?.total ? job.done : undefined"
      :aria-label="busyLabel"
    />
  </button>
</template>
