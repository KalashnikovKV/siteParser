<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useListings } from "../composables/useListings";
import { PRESET_LABELS } from "../composables/useListQuery";
import { adviceClass, adviceLabel, formatEur, profitTone, scoreClass } from "../lib/format";

defineOptions({ name: "ListView" });

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
  resetPage,
  load,
  loadPicks,
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

const filtersOpen = ref(false);

const hasActiveFilters = computed(() =>
  Boolean(
    query.q ||
      query.min_price ||
      query.max_price ||
      query.city ||
      query.socket ||
      query.source ||
      query.potential ||
      query.advice ||
      query.min_score ||
      query.min_profit ||
      query.has_description ||
      query.preset,
  ),
);

const advancedCount = computed(() =>
  [
    query.min_price,
    query.max_price,
    query.city,
    query.socket,
    query.source,
    query.potential,
    query.min_score,
    query.min_profit,
    query.has_description,
  ].filter(Boolean).length,
);

const adviceCounts = computed(() => options.value.advice_counts || {});

const activeTags = computed(() => {
  const tags: { key: string; label: string }[] = [];
  if (query.preset) {
    tags.push({
      key: "preset",
      label: PRESET_LABELS[query.preset] || query.preset,
    });
  }
  if (query.q) tags.push({ key: "q", label: `«${query.q}»` });
  if (query.advice && !query.preset) {
    const labels: Record<string, string> = {
      buy: "брать",
      inspect: "смотреть",
      skip: "пропуск",
      any: "уже смотрела",
    };
    tags.push({ key: "advice", label: labels[query.advice] || query.advice });
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
  return tags;
});

function openListing(id: string) {
  router.push({ name: "detail", params: { id } });
}

function setSort(sort: string) {
  query.sort = sort;
  query.page = 1;
  if (query.preset) query.preset = "";
}

function onManualFilter() {
  resetPage();
}

function removeTag(key: string) {
  if (key === "preset") {
    query.preset = "";
    query.page = 1;
    return;
  }
  if (key === "q") query.q = "";
  else if (key === "advice") query.advice = "";
  else if (key === "city") query.city = "";
  else if (key === "socket") query.socket = "";
  else if (key === "min_price") query.min_price = "";
  else if (key === "max_price") query.max_price = "";
  else if (key === "potential") query.potential = "";
  else if (key === "min_score") query.min_score = "";
  else if (key === "min_profit") query.min_profit = "";
  else if (key === "has_description") query.has_description = "";
  query.page = 1;
}

function toggleAdvice(action: string) {
  query.preset = "";
  query.advice = query.advice === action ? "" : action;
  query.sort = "ai";
  query.page = 1;
}

onMounted(() => emit("changed"));
watch(
  () => props.dataTick,
  (next, prev) => {
    if (prev != null && next !== prev) {
      load();
      loadPicks();
    }
  },
);
</script>

<template>
  <section v-if="picks?.items?.length" class="picks">
    <div class="picks-head">
      <div>
        <h2>{{ picks.title }}</h2>
        <p class="muted">
          {{
            picks.source === "advice"
              ? "Сразу лучшие по мнению модели: сначала «брать», потом «смотреть»"
              : "Модель ещё молчит — показываю топ по марже и запасу апгрейда"
          }}
        </p>
      </div>
      <button class="ghost" type="button" @click="applyPreset('picks')">весь топ модели</button>
    </div>
    <div class="picks-row">
      <button
        v-for="item in picks.items"
        :key="'pick-' + item.id"
        class="pick-card"
        type="button"
        @click="openListing(item.id)"
      >
        <div class="pick-top">
          <span v-if="item.advice" :class="adviceClass(item.advice.action)">
            {{ adviceLabel(item.advice.action) }}
          </span>
          <span :class="scoreClass(item.score)">
            {{ item.score == null ? "—" : item.score.toFixed(0) }}
          </span>
        </div>
        <strong class="pick-title">{{ item.title }}</strong>
        <div class="muted">
          {{ formatEur(item.price_eur) }}
          · {{ item.socket || item.parts.chipset || "сокет ?" }}
        </div>
        <div class="muted">
          {{ item.parts.cpu || "CPU ?" }}
          <span v-if="item.advice"> · интерес {{ item.advice.interest.toFixed(0) }}</span>
        </div>
        <p v-if="item.advice?.summary" class="pick-summary muted">{{ item.advice.summary }}</p>
        <div :class="profitTone(item.profit_eur)" class="pick-margin">
          маржа {{ formatEur(item.profit_eur) }}
        </div>
      </button>
    </div>
  </section>

  <section class="categories">
    <button
      type="button"
      class="chip"
      :class="{ active: !query.preset && !query.advice }"
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
      @click="applyPreset(name)"
    >
      {{ PRESET_LABELS[name] || name }}
    </button>
    <button
      type="button"
      class="chip"
      :class="{ active: query.advice === 'buy' && !query.preset }"
      @click="toggleAdvice('buy')"
    >
      брать
      <span v-if="adviceCounts.buy" class="chip-count">{{ adviceCounts.buy }}</span>
    </button>
    <button
      type="button"
      class="chip"
      :class="{ active: query.advice === 'inspect' && !query.preset }"
      @click="toggleAdvice('inspect')"
    >
      смотреть
      <span v-if="adviceCounts.inspect" class="chip-count">{{ adviceCounts.inspect }}</span>
    </button>
  </section>

  <section class="filters card-panel">
    <div class="filters-primary">
      <label class="field grow">
        <span>поиск</span>
        <input
          v-model.trim="query.q"
          placeholder="CPU, плата, RTX, город…"
          @input="onManualFilter"
        />
      </label>
      <label class="field narrow">
        <span>цена от</span>
        <input v-model="query.min_price" type="number" placeholder="€" @input="onManualFilter" />
      </label>
      <label class="field narrow">
        <span>цена до</span>
        <input v-model="query.max_price" type="number" placeholder="€" @input="onManualFilter" />
      </label>
      <div class="field narrow">
        <span>&nbsp;</span>
        <button type="button" class="ghost full" @click="filtersOpen = !filtersOpen">
          {{ filtersOpen ? "скрыть фильтры" : "ещё фильтры" }}
          <span v-if="advancedCount && !filtersOpen" class="chip-count">{{ advancedCount }}</span>
        </button>
      </div>
    </div>

    <div v-if="filtersOpen" class="filters-grid">
      <label class="field">
        <span>город</span>
        <select v-model="query.city" @change="onManualFilter">
          <option value="">все</option>
          <option v-for="city in options.cities" :key="city" :value="city">{{ city }}</option>
        </select>
      </label>
      <label class="field">
        <span>сокет</span>
        <select v-model="query.socket" @change="onManualFilter">
          <option value="">все</option>
          <option v-for="socket in options.sockets" :key="socket" :value="socket">{{ socket }}</option>
        </select>
      </label>
      <label class="field">
        <span>запас</span>
        <select v-model="query.potential" @change="onManualFilter">
          <option value="">любой</option>
          <option value="true">есть апгрейд</option>
          <option value="false">без запаса</option>
        </select>
      </label>
      <label class="field">
        <span>совет модели</span>
        <select v-model="query.advice" @change="onManualFilter">
          <option value="">все</option>
          <option value="buy">брать</option>
          <option value="inspect">смотреть</option>
          <option value="skip">пропуск</option>
          <option value="any">уже смотрела</option>
        </select>
      </label>
      <label class="field">
        <span>оценка от</span>
        <input v-model="query.min_score" type="number" placeholder="40" @input="onManualFilter" />
      </label>
      <label class="field">
        <span>маржа от</span>
        <input v-model="query.min_profit" type="number" placeholder="€" @input="onManualFilter" />
      </label>
      <label class="field">
        <span>описание</span>
        <select v-model="query.has_description" @change="onManualFilter">
          <option value="">любое</option>
          <option value="true">есть текст</option>
          <option value="false">только заголовок</option>
        </select>
      </label>
      <label v-if="options.sources.length > 1" class="field">
        <span>источник</span>
        <select v-model="query.source" @change="onManualFilter">
          <option value="">все</option>
          <option v-for="src in options.sources" :key="src" :value="src">{{ src }}</option>
        </select>
      </label>
    </div>

    <div v-if="activeTags.length" class="active-tags">
      <button
        v-for="tag in activeTags"
        :key="tag.key + tag.label"
        type="button"
        class="tag"
        @click="removeTag(tag.key)"
      >
        {{ tag.label }} ×
      </button>
      <button v-if="hasActiveFilters" type="button" class="ghost sm" @click="clearFilters">
        сбросить всё
      </button>
    </div>

    <div class="sort-row">
      <span class="muted">сортировка</span>
      <button
        v-for="opt in SORT_OPTS"
        :key="opt[0]"
        type="button"
        class="chip sm"
        :class="{ active: query.sort === opt[0] && !query.preset }"
        @click="setSort(opt[0])"
      >
        {{ opt[1] }}
      </button>
    </div>
  </section>

  <p v-if="error" class="err">{{ error }}</p>
  <p class="muted result-line">
    Найдено {{ total }}
    <span v-if="query.preset"> · категория «{{ PRESET_LABELS[query.preset] || query.preset }}»</span>
  </p>

  <p v-if="!items.length && !error" class="empty">
    Ничего не нашлось. Сбрось фильтры или выбери другую категорию.
  </p>

  <div class="cards-mobile">
    <button
      v-for="item in items"
      :key="'m-' + item.id"
      type="button"
      class="list-card"
      @click="openListing(item.id)"
    >
      <div class="list-card-top">
        <span :class="scoreClass(item.score)">
          {{ item.score == null ? "—" : item.score.toFixed(0) }}
        </span>
        <span v-if="item.advice" :class="adviceClass(item.advice.action)">
          {{ adviceLabel(item.advice.action) }}
        </span>
        <strong class="list-card-price">{{ formatEur(item.price_eur) }}</strong>
      </div>
      <strong class="list-card-title">{{ item.title }}</strong>
      <div class="muted">
        {{ item.city || "город ?" }} · {{ item.socket || item.parts.chipset || "сокет ?" }}
      </div>
      <div class="muted">
        {{ item.parts.cpu || "CPU ?" }} · {{ item.parts.gpu || "без GPU" }}
      </div>
      <div :class="profitTone(item.profit_eur)">маржа {{ formatEur(item.profit_eur) }}</div>
    </button>
  </div>

  <table class="table desktop-only">
    <thead>
      <tr>
        <th>оценка</th>
        <th>модель</th>
        <th>объявление</th>
        <th>цена</th>
        <th>сокет</th>
        <th>комплектующие</th>
        <th>докинуть</th>
        <th>продажа</th>
        <th>маржа</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="item in items"
        :key="item.id"
        class="clickable"
        @click="openListing(item.id)"
      >
        <td>
          <span :class="scoreClass(item.score)">
            {{ item.score == null ? "—" : item.score.toFixed(0) }}
          </span>
          <div class="muted">{{ item.verdict || "ещё не разобрано" }}</div>
        </td>
        <td>
          <span v-if="item.advice" :class="adviceClass(item.advice.action)">
            {{ adviceLabel(item.advice.action) }}
          </span>
          <span v-else class="muted">—</span>
          <div class="muted" v-if="item.advice">{{ item.advice.interest.toFixed(0) }}</div>
        </td>
        <td>
          <strong>{{ item.title }}</strong>
          <div class="muted">
            {{ item.city || "город ?" }}
            · {{ item.has_description ? "есть текст" : "только заголовок" }}
            <span v-if="item.source && item.source !== 'skelbiu'"> · {{ item.source }}</span>
          </div>
        </td>
        <td>
          {{ formatEur(item.price_eur) }}
          <div class="muted" v-if="item.analysis?.price_note">текст ≠ карточка</div>
        </td>
        <td>
          {{ item.socket || item.parts.chipset || "—" }}
          <div class="muted">{{ item.parts.motherboard || item.parts.chipset || "" }}</div>
        </td>
        <td>
          <div>{{ item.parts.cpu || "CPU ?" }}</div>
          <div class="muted">{{ item.parts.gpu || "без GPU" }} · {{ item.parts.ram || "RAM ?" }}</div>
        </td>
        <td>{{ formatEur(item.upgrade_cost_eur) }}</td>
        <td>{{ formatEur(item.resale_eur) }}</td>
        <td :class="profitTone(item.profit_eur)">{{ formatEur(item.profit_eur) }}</td>
      </tr>
    </tbody>
  </table>

  <div class="pager">
    <button :disabled="query.page <= 1" @click="query.page -= 1">назад</button>
    <span class="muted">стр. {{ query.page }}</span>
    <button :disabled="query.page * 30 >= total" @click="query.page += 1">дальше</button>
  </div>
</template>
