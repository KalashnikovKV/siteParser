<script setup lang="ts">
import { useBackgroundJob } from "./composables/useBackgroundJob";

const {
  stats,
  advisor,
  analyzeJob,
  detailsJob,
  adviseJob,
  analyzeBusy,
  detailsBusy,
  adviseBusy,
  error,
  dataTick,
  refreshStats,
  analyze,
  fetchDetails,
  advise,
} = useBackgroundJob();
</script>

<template>
  <header class="top">
    <div>
      <h1><router-link :to="{ name: 'list' }" style="color: inherit">Skelbiu PC</router-link></h1>
      <div class="muted">
        Категории, фильтры и топ модели — уже по локальной базе
      </div>
    </div>
    <div class="stats" v-if="stats">
      <div class="stat"><span class="muted">всего</span><b>{{ stats.total }}</b></div>
      <div class="stat"><span class="muted">с текстом</span><b>{{ stats.with_details }}</b></div>
      <div class="stat"><span class="muted">разобрано</span><b>{{ stats.analyzed }}</b></div>
      <div class="stat"><span class="muted">с апгрейдом</span><b>{{ stats.with_potential }}</b></div>
      <div class="stat"><span class="muted">модель</span><b>{{ stats.advised }}</b></div>
      <button class="primary" :disabled="detailsBusy" @click="fetchDetails">
        {{
          detailsBusy
            ? `описания ${detailsJob?.done ?? 0}/${detailsJob?.total ?? "?"}`
            : "докачать описания"
        }}
      </button>
      <button :disabled="analyzeBusy" @click="analyze">
        {{ analyzeBusy ? "считаю…" : "пересчитать" }}
      </button>
      <button
        :disabled="adviseBusy"
        :title="advisor?.error || advisor?.model || ''"
        @click="advise"
      >
        {{ adviseBusy ? `модель ${adviseJob?.done ?? 0}/${adviseJob?.total ?? "?"}` : "обновить топ модели" }}
      </button>
    </div>
  </header>
  <p v-if="advisor && !advisor.available" class="muted">
    модель недоступна: {{ advisor.error }}
  </p>
  <p v-if="error" class="err">{{ error }}</p>
  <router-view v-slot="{ Component }">
    <keep-alive include="ListView">
      <component :is="Component" :data-tick="dataTick" @changed="refreshStats" />
    </keep-alive>
  </router-view>
</template>
