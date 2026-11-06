<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { PAGE_SIZE, useListings } from "../composables/useListings";
import { PRESET_LABELS } from "../composables/useListQuery";
import {
  adviceClass,
  adviceLabel,
  formatEur,
  formatInt,
  formatScore,
  labelFrom,
  profitTone,
  scoreClass,
} from "../lib/format";
import type { QueryState } from "../types";

defineOptions({ name: "ListView" });

type TextKey = Exclude<keyof QueryState, "page">;

const props = defineProps<{ dataTick?: number }>();
const emit = defineEmits<{ changed: [] }>();
const router = useRouter();
const {
  query,
  items,
  picks,
  total,
  options,
  error,
  loading,
  resetPage,
  load,
  loadPicks,
  loadOptions,
  clearFilters,
  applyPreset,
  showAll,
} = useListings();

const PRESET_ORDER = ["picks", "upgrade", "cheap", "margin", "fresh"];
const SORT_OPTS: [string, string][] = [
  ["ai", "модель"],
  ["score", "потенциал"],
  ["profit", "маржа"],
  ["price_asc", "дешевле"],
  ["price_desc", "дороже"],
  ["seen", "свежие"],
];
const ADVICE_LABELS: Record<string, string> = {
  buy: "брать",
  inspect: "смотреть",
  skip: "пропуск",
  any: "уже смотрела",
};
const ADVANCED_KEYS: TextKey[] = [
  "city",
  "socket",
  "source",
  "potential",
  "min_score",
  "min_profit",
  "has_description",
];

const filtersOpen = ref(false);
const resultsTop = ref<HTMLElement | null>(null);

const hasActiveFilters = computed(() =>
  Boolean(
    query.q ||
      query.min_price ||
      query.max_price ||
      query.advice ||
      query.preset ||
      ADVANCED_KEYS.some((key) => query[key]),
  ),
);
const advancedCount = computed(() => ADVANCED_KEYS.filter((key) => query[key]).length);
const adviceCounts = computed(() => options.value.advice_counts || {});
const presetLabel = computed(() => labelFrom(PRESET_LABELS, query.preset));
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)));

const activeTags = computed(() => {
  const tags: { key: TextKey; label: string }[] = [];
  if (query.preset) tags.push({ key: "preset", label: presetLabel.value });
  if (query.q) tags.push({ key: "q", label: `«${query.q}»` });
  if (query.advice && !query.preset) {
    tags.push({ key: "advice", label: `модель: ${labelFrom(ADVICE_LABELS, query.advice)}` });
  }
  if (query.city) tags.push({ key: "city", label: query.city });
  if (query.socket) tags.push({ key: "socket", label: query.socket });
  if (query.min_price) tags.push({ key: "min_price", label: `от ${query.min_price} €` });
  if (query.max_price) tags.push({ key: "max_price", label: `до ${query.max_price} €` });
  if (query.potential === "true") tags.push({ key: "potential", label: "есть апгрейд" });
  if (query.potential === "false") tags.push({ key: "potential", label: "без запаса" });
  if (query.min_score) tags.push({ key: "min_score", label: `оценка ≥ ${query.min_score}` });
  if (query.min_profit) tags.push({ key: "min_profit", label: `маржа ≥ ${query.min_profit} €` });
  if (query.has_description === "true") tags.push({ key: "has_description", label: "есть текст" });
  if (query.has_description === "false") {
    tags.push({ key: "has_description", label: "только заголовок" });
  }
  if (query.source) tags.push({ key: "source", label: query.source });
  return tags;
});

function detailRoute(id: string) {
  return { name: "detail", params: { id } };
}

function openListing(id: string) {
  router.push(detailRoute(id));
}

function setSort(sort: string) {
  query.sort = sort;
  query.page = 1;
  if (query.preset) query.preset = "";
}

function removeTag(key: TextKey) {
  query[key] = "";
  query.page = 1;
}

function toggleAdvice(action: string) {
  query.preset = "";
  query.advice = query.advice === action ? "" : action;
  query.sort = "ai";
  query.page = 1;
}

function goToPage(page: number) {
  query.page = Math.min(Math.max(1, page), pageCount.value);
  resultsTop.value?.scrollIntoView({ block: "start" });
}

onMounted(() => emit("changed"));
watch(
  () => props.dataTick,
  (next, prev) => {
    if (prev != null && next !== prev) {
      load();
      loadPicks();
      loadOptions();
    }
  },
);
</script>

<template>
  <section v-if="picks?.items?.length" class="picks" aria-labelledby="picks-title">
    <div class="section-head">
      <div>
        <h2 id="picks-title">{{ picks.title }}</h2>
        <p class="muted">
          {{
            picks.source === "advice"
              ? "Лучшие по мнению модели: сначала «брать», потом «смотреть»"
              : "Модель ещё молчит — показываю топ по марже и запасу апгрейда"
          }}
        </p>
      </div>
      <button class="ghost" type="button" @click="applyPreset('picks')">весь топ модели →</button>
    </div>
    <div class="picks-row">
      <router-link
        v-for="item in picks.items"
        :key="'pick-' + item.id"
        class="pick-card"
        :to="detailRoute(item.id)"
      >
        <div class="pick-top">
          <span v-if="item.advice" :class="adviceClass(item.advice.action)">
            {{ adviceLabel(item.advice.action) }}
          </span>
          <span :class="scoreClass(item.score)" title="оценка правил">{{ formatScore(item.score) }}</span>
          <span class="pick-price num">{{ formatEur(item.price_eur) }}</span>
        </div>
        <strong class="pick-title">{{ item.title }}</strong>
        <div class="muted small">
          {{ item.socket || item.parts.chipset || "сокет ?" }} · {{ item.parts.cpu || "CPU ?" }}
        </div>
        <p v-if="item.advice?.summary" class="pick-summary">{{ item.advice.summary }}</p>
        <div class="pick-foot small">
          <span :class="profitTone(item.profit_eur)" class="num">маржа {{ formatEur(item.profit_eur) }}</span>
          <span v-if="item.advice" class="muted num">интерес {{ formatScore(item.advice.interest) }}</span>
        </div>
      </router-link>
    </div>
  </section>

  <nav class="categories" aria-label="Категории">
    <button
      type="button"
      class="chip"
      :class="{ active: !query.preset && !query.advice }"
      :aria-pressed="!query.preset && !query.advice"
      @click="showAll"
    >
      Все
    </button>
    <button
      v-for="name in PRESET_ORDER"
      :key="name"
      type="button"
      class="chip"
      :class="{ active: query.preset === name }"
      :aria-pressed="query.preset === name"
      @click="applyPreset(name)"
    >
      {{ PRESET_LABELS[name] }}
    </button>
    <span class="chip-sep" aria-hidden="true"></span>
    <button
      v-for="action in ['buy', 'inspect']"
      :key="action"
      type="button"
      class="chip"
      :class="{ active: query.advice === action && !query.preset }"
      :aria-pressed="query.advice === action && !query.preset"
      @click="toggleAdvice(action)"
    >
      модель: {{ ADVICE_LABELS[action] }}
      <span v-if="adviceCounts[action]" class="chip-count">{{ formatInt(adviceCounts[action]) }}</span>
    </button>
  </nav>

  <section class="filters panel" aria-label="Фильтры">
    <div class="filters-primary">
      <label class="field">
        <span>поиск</span>
        <input
          v-model.trim="query.q"
          type="search"
          maxlength="200"
          placeholder="CPU, плата, RTX, город…"
          @input="resetPage"
        />
      </label>
      <label class="field">
        <span>цена от, €</span>
        <input
          v-model="query.min_price"
          type="number"
          min="0"
          step="10"
          inputmode="numeric"
          placeholder="0"
          @input="resetPage"
        />
      </label>
      <label class="field">
        <span>цена до, €</span>
        <input
          v-model="query.max_price"
          type="number"
          min="0"
          step="10"
          inputmode="numeric"
          placeholder="∞"
          @input="resetPage"
        />
      </label>
      <button
        type="button"
        class="ghost filters-toggle"
        :aria-expanded="filtersOpen"
        aria-controls="more-filters"
        @click="filtersOpen = !filtersOpen"
      >
        {{ filtersOpen ? "скрыть фильтры" : "ещё фильтры" }}
        <span v-if="advancedCount && !filtersOpen" class="chip-count">{{ advancedCount }}</span>
      </button>
    </div>

    <div v-if="filtersOpen" id="more-filters" class="filters-grid">
      <label class="field">
        <span>город</span>
        <select v-model="query.city" @change="resetPage">
          <option value="">все</option>
          <option v-for="city in options.cities" :key="city" :value="city">{{ city }}</option>
        </select>
      </label>
      <label class="field">
        <span>сокет</span>
        <select v-model="query.socket" @change="resetPage">
          <option value="">все</option>
          <option v-for="socket in options.sockets" :key="socket" :value="socket">{{ socket }}</option>
        </select>
      </label>
      <label class="field">
        <span>запас под апгрейд</span>
        <select v-model="query.potential" @change="resetPage">
          <option value="">любой</option>
          <option value="true">есть апгрейд</option>
          <option value="false">без запаса</option>
        </select>
      </label>
      <label class="field">
        <span>совет модели</span>
        <select v-model="query.advice" @change="resetPage">
          <option value="">все</option>
          <option value="buy">брать</option>
          <option value="inspect">смотреть</option>
          <option value="skip">пропуск</option>
          <option value="any">уже смотрела</option>
        </select>
      </label>
      <label class="field">
        <span>оценка от</span>
        <input
          v-model="query.min_score"
          type="number"
          min="0"
          max="100"
          inputmode="numeric"
          placeholder="40"
          @input="resetPage"
        />
      </label>
      <label class="field">
        <span>маржа от, €</span>
        <input
          v-model="query.min_profit"
          type="number"
          step="10"
          inputmode="numeric"
          placeholder="0"
          @input="resetPage"
        />
      </label>
      <label class="field">
        <span>описание</span>
        <select v-model="query.has_description" @change="resetPage">
          <option value="">любое</option>
          <option value="true">есть текст</option>
          <option value="false">только заголовок</option>
        </select>
      </label>
      <label v-if="options.sources.length > 1" class="field">
        <span>источник</span>
        <select v-model="query.source" @change="resetPage">
          <option value="">все</option>
          <option v-for="src in options.sources" :key="src" :value="src">{{ src }}</option>
        </select>
      </label>
    </div>

    <div v-if="activeTags.length" class="active-tags">
      <button
        v-for="tag in activeTags"
        :key="tag.key"
        type="button"
        class="tag"
        :aria-label="`убрать фильтр ${tag.label}`"
        @click="removeTag(tag.key)"
      >
        {{ tag.label }} <span aria-hidden="true">×</span>
      </button>
      <button v-if="hasActiveFilters" type="button" class="ghost sm" @click="clearFilters">
        сбросить всё
      </button>
    </div>

    <div class="sort-row" role="group" aria-label="Сортировка">
      <span class="muted small">сортировка</span>
      <button
        v-for="opt in SORT_OPTS"
        :key="opt[0]"
        type="button"
        class="chip sm"
        :class="{ active: query.sort === opt[0] && !query.preset }"
        :aria-pressed="query.sort === opt[0] && !query.preset"
        @click="setSort(opt[0])"
      >
        {{ opt[1] }}
      </button>
    </div>
  </section>

  <div ref="resultsTop" class="result-line">
    <span>
      Найдено <b class="num">{{ formatInt(total) }}</b>
      <span v-if="query.preset" class="muted">
        · категория «{{ presetLabel }}»
      </span>
    </span>
    <span v-if="loading" class="loading" role="status">обновляю…</span>
  </div>

  <p v-if="error" class="alert alert-error" role="alert">{{ error }}</p>

  <div class="results" :class="{ stale: loading }" :aria-busy="loading">
    <div v-if="!items.length && !error && !loading" class="empty">
      <p>Ничего не нашлось.</p>
      <button v-if="hasActiveFilters" type="button" class="ghost" @click="clearFilters">
        сбросить фильтры
      </button>
    </div>

    <div class="cards-mobile">
      <router-link
        v-for="item in items"
        :key="'m-' + item.id"
        class="list-card"
        :to="detailRoute(item.id)"
      >
        <div class="list-card-top">
          <span :class="scoreClass(item.score)">{{ formatScore(item.score) }}</span>
          <span v-if="item.advice" :class="adviceClass(item.advice.action)">
            {{ adviceLabel(item.advice.action) }}
          </span>
          <strong class="list-card-price num">{{ formatEur(item.price_eur) }}</strong>
        </div>
        <strong class="list-card-title">{{ item.title }}</strong>
        <div class="muted small">
          {{ item.city || "город ?" }} · {{ item.socket || item.parts.chipset || "сокет ?" }}
        </div>
        <div class="muted small">
          {{ item.parts.cpu || "CPU ?" }} · {{ item.parts.gpu || "без GPU" }}
        </div>
        <div :class="profitTone(item.profit_eur)" class="small num">
          маржа {{ formatEur(item.profit_eur) }}
        </div>
      </router-link>
    </div>

    <div class="table-wrap desktop-only">
      <table v-if="items.length" class="table">
        <thead>
          <tr>
            <th scope="col">оценка</th>
            <th scope="col">модель</th>
            <th scope="col">объявление</th>
            <th scope="col" class="right">цена</th>
            <th scope="col">сокет</th>
            <th scope="col">комплектующие</th>
            <th scope="col" class="right">докинуть</th>
            <th scope="col" class="right">продажа</th>
            <th scope="col" class="right">маржа</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id" class="clickable" @click="openListing(item.id)">
            <td>
              <span :class="scoreClass(item.score)">{{ formatScore(item.score) }}</span>
              <div class="muted small">{{ item.verdict || "не разобрано" }}</div>
            </td>
            <td>
              <template v-if="item.advice">
                <span :class="adviceClass(item.advice.action)">{{ adviceLabel(item.advice.action) }}</span>
                <div class="muted small num">интерес {{ formatScore(item.advice.interest) }}</div>
              </template>
              <span v-else class="muted">—</span>
            </td>
            <td class="title-cell">
              <router-link :to="detailRoute(item.id)" class="row-link" @click.stop>
                {{ item.title }}
              </router-link>
              <div class="muted small">
                {{ item.city || "город ?" }}
                · {{ item.has_description ? "есть текст" : "только заголовок" }}
                <span v-if="item.source && item.source !== 'skelbiu'"> · {{ item.source }}</span>
              </div>
            </td>
            <td class="right num">
              {{ formatEur(item.price_eur) }}
              <div v-if="item.analysis?.price_note" class="warn small">текст ≠ карточка</div>
            </td>
            <td>
              {{ item.socket || item.parts.chipset || "—" }}
              <div class="muted small">{{ item.parts.motherboard || item.parts.chipset || "" }}</div>
            </td>
            <td>
              <div>{{ item.parts.cpu || "CPU ?" }}</div>
              <div class="muted small">
                {{ item.parts.gpu || "без GPU" }} · {{ item.parts.ram || "RAM ?" }}
              </div>
            </td>
            <td class="right num">{{ formatEur(item.upgrade_cost_eur) }}</td>
            <td class="right num">{{ formatEur(item.resale_eur) }}</td>
            <td class="right num" :class="profitTone(item.profit_eur)">
              {{ formatEur(item.profit_eur) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <nav v-if="total > PAGE_SIZE" class="pager" aria-label="Страницы">
    <button type="button" :disabled="query.page <= 1" @click="goToPage(query.page - 1)">← назад</button>
    <span class="muted num">стр. {{ query.page }} из {{ pageCount }}</span>
    <button type="button" :disabled="query.page >= pageCount" @click="goToPage(query.page + 1)">
      дальше →
    </button>
  </nav>
</template>
