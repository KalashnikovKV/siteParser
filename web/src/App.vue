<script setup lang="ts">
import { computed } from "vue";
import JobButton from "./components/JobButton.vue";
import { useBackgroundJob } from "./composables/useBackgroundJob";
import { formatDateTime, formatInt } from "./lib/format";

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
  notice,
  dataTick,
  dismiss,
  refreshStats,
  analyze,
  fetchDetails,
  advise,
} = useBackgroundJob();

interface Tile {
  label: string;
  value: number;
  of?: number;
  hint: string;
  warn?: boolean;
}

const tiles = computed<Tile[]>(() => {
  const s = stats.value;
  if (!s) return [];
  const list: Tile[] = [
    {
      label: "в продаже",
      value: s.on_sale,
      hint: `Стационарные ПК в продаже. Всего в базе ${formatInt(s.total)} — остальные сняты с продажи или это ноутбуки. Растёт только после сбора новых объявлений.`,
    },
    {
      label: "свежие описания",
      value: s.details_fresh,
      of: s.on_sale,
      hint: `Текст скачан за последние ${s.detail_ttl_days} дн. Без текста: ${formatInt(s.details_missing)}, устарели: ${formatInt(s.details_stale)}.`,
    },
    {
      label: "с апгрейдом",
      value: s.with_potential,
      hint: "В продаже и с запасом под апгрейд по правилам",
    },
    {
      label: "советов модели",
      value: s.advised,
      hint: "Объявлений, которые разобрала локальная модель",
    },
  ];
  if (s.unanalyzed > 0) {
    list.push({
      label: "ждут пересчёта",
      value: s.unanalyzed,
      hint: "Новые объявления без оценки — нажми «Пересчитать»",
      warn: true,
    });
  }
  return list;
});

const details = computed(() => {
  const s = stats.value;
  if (!s || s.details_missing > 0) {
    return {
      label: "Докачать описания",
      hint: s
        ? `Скачать тексты: без текста ${formatInt(s.details_missing)}, устарели ${formatInt(s.details_stale)}`
        : "Скачать тексты объявлений, где их нет или они устарели",
    };
  }
  return {
    label: "Обновить описания",
    hint: `У всех объявлений есть текст. Скачать заново устаревшие (старше ${s.detail_ttl_days} дн.): ${formatInt(s.details_stale)}`,
  };
});

const advisorState = computed(() => {
  const a = advisor.value;
  if (!a) return { tone: "idle", text: "модель: проверяю…", title: "" };
  if (a.available) return { tone: "ok", text: a.model || a.backend, title: "модель готова" };
  return { tone: "off", text: "модель недоступна", title: a.error || "" };
});

const lastRun = computed(() => {
  const run = stats.value?.last_run;
  if (!run) return "";
  return `последний сбор ${formatDateTime(run.finished_at || run.started_at)}`;
});
</script>

<template>
  <a class="skip-link" href="#main">к содержимому</a>
  <header class="app-header">
    <div class="app-header-inner">
      <div class="brand">
        <router-link :to="{ name: 'list' }" class="brand-link">
          <span class="brand-mark" aria-hidden="true">PC</span>
          <span>
            <span class="brand-name">Skelbiu PC</span>
            <span class="brand-sub">б/у компьютеры с запасом под апгрейд</span>
          </span>
        </router-link>
      </div>

      <dl v-if="tiles.length" class="tiles">
        <div v-for="tile in tiles" :key="tile.label" class="tile" :class="{ warn: tile.warn }" :title="tile.hint">
          <dt>{{ tile.label }}</dt>
          <dd class="num">
            {{ formatInt(tile.value) }}<span v-if="tile.of != null" class="tile-of"> из {{ formatInt(tile.of) }}</span>
          </dd>
        </div>
      </dl>

      <div class="header-side">
        <div class="status-line">
          <span class="status" :class="advisorState.tone" :title="advisorState.title">
            <span class="status-dot" aria-hidden="true"></span>
            {{ advisorState.text }}
          </span>
          <span v-if="lastRun" class="muted" title="Новые объявления собирает make scrape">{{ lastRun }}</span>
        </div>
        <div class="actions">
          <JobButton
            primary
            :label="details.label"
            busy-label="Описания"
            :busy="detailsBusy"
            :job="detailsJob"
            :hint="details.hint"
            @start="fetchDetails"
          />
          <JobButton
            label="Пересчитать"
            busy-label="Считаю"
            :busy="analyzeBusy"
            :job="analyzeJob"
            hint="Заново оценить все объявления правилами"
            @start="analyze"
          />
          <JobButton
            label="Обновить топ модели"
            busy-label="Модель"
            :busy="adviseBusy"
            :job="adviseJob"
            :hint="advisor?.error || advisor?.model || ''"
            @start="advise"
          />
        </div>
      </div>
    </div>
  </header>

  <main id="main" class="app-main" tabindex="-1">
    <div v-if="error || notice" class="alert" :class="error ? 'alert-error' : 'alert-info'" role="alert">
      <span>{{ error || notice }}</span>
      <button type="button" class="icon-button" aria-label="Скрыть сообщение" @click="dismiss">×</button>
    </div>
    <router-view v-slot="{ Component }">
      <keep-alive include="ListView">
        <component :is="Component" :data-tick="dataTick" @changed="refreshStats" />
      </keep-alive>
    </router-view>
  </main>
</template>
