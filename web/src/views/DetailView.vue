<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import PriceChart from "../components/PriceChart.vue";
import {
  adviceClass,
  adviceLabel,
  flagLabel,
  formatDateTime,
  formatEur,
  formatScore,
  isWarningFlag,
  profitTone,
  safeExternalUrl,
  scoreClass,
} from "../lib/format";
import { catalog } from "../repositories/catalog";
import type { ListingDetail } from "../types";

const props = defineProps<{ id: string; dataTick?: number }>();
const router = useRouter();
const item = ref<ListingDetail | null>(null);
const error = ref("");
const loading = ref(false);
const advising = ref(false);

const externalUrl = computed(() => safeExternalUrl(item.value?.url));
const sourceHost = computed(() => {
  const url = externalUrl.value;
  return url ? new URL(url).hostname.replace(/^www\./, "") : "";
});

const scoreParts = computed(() => {
  const a = item.value?.analysis;
  if (!a) return [];
  return [
    { label: "платформа", value: a.platform_score, max: 40 },
    { label: "запас апгрейда", value: a.headroom_score, max: 35 },
    { label: "слоты и БП", value: a.expandability_score, max: 15 },
    { label: "цена", value: a.value_score, max: 10 },
  ];
});

const parts = computed(() => {
  const p = item.value?.parts;
  if (!p) return [];
  return [
    { label: "процессор", value: p.cpu },
    { label: "материнская плата", value: p.motherboard || p.chipset },
    { label: "сокет", value: item.value?.socket || p.socket },
    { label: "видеокарта", value: p.gpu || "нет / не указана" },
    { label: "память", value: p.ram },
    { label: "накопитель", value: p.storage },
    { label: "блок питания", value: p.psu },
  ];
});

function toList() {
  if (window.history.state?.back != null) {
    router.back();
    return;
  }
  router.push({ name: "list" });
}

async function load() {
  error.value = "";
  loading.value = true;
  try {
    item.value = await catalog.listing(props.id);
    document.title = `${item.value.title || "Объявление"} — Skelbiu PC`;
  } catch (err) {
    item.value = null;
    error.value = err instanceof Error ? err.message : "Не найдено";
  } finally {
    loading.value = false;
  }
}

async function askModel() {
  advising.value = true;
  error.value = "";
  try {
    item.value = await catalog.adviseListing(props.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Модель не ответила";
  } finally {
    advising.value = false;
  }
}

onMounted(load);
watch(() => props.id, load);
watch(
  () => props.dataTick,
  (next, prev) => {
    if (prev != null && next !== prev) load();
  },
);
</script>

<template>
  <div class="detail">
    <a href="/" class="back-link" @click.prevent="toList">← к списку</a>
    <p v-if="error" class="alert alert-error" role="alert">{{ error }}</p>
    <p v-else-if="loading && !item" class="muted" role="status">загружаю…</p>

    <article v-if="item" class="detail-grid">
      <section class="panel hero">
        <div class="hero-info">
          <div class="hero-badges">
            <span :class="scoreClass(item.score)" title="оценка правил">
              {{ item.score == null ? "нет оценки" : item.score.toFixed(1) }}
            </span>
            <span v-if="item.advice" :class="adviceClass(item.advice.action)">
              модель: {{ adviceLabel(item.advice.action) }}
            </span>
            <span class="muted small">{{ item.verdict || "ещё не разобрано" }}</span>
          </div>
          <h1 class="hero-title">{{ item.title }}</h1>
          <div class="hero-meta">
            <span class="hero-price num">
              {{ item.price_eur == null ? "цена ?" : formatEur(item.price_eur) }}
            </span>
            <span class="muted">{{ item.city || "город не указан" }}</span>
            <span v-if="item.condition" class="muted">{{ item.condition }}</span>
          </div>
          <p v-if="item.analysis?.price_note" class="warn small">{{ item.analysis.price_note }}</p>
          <div class="hero-actions">
            <a
              v-if="externalUrl"
              class="button primary"
              :href="externalUrl"
              target="_blank"
              rel="noopener noreferrer"
            >
              открыть на {{ sourceHost }} ↗
            </a>
            <button type="button" :disabled="advising" :aria-busy="advising" @click="askModel">
              {{ advising ? "модель думает…" : item.advice ? "переспросить модель" : "спросить модель" }}
            </button>
          </div>
          <dl class="hero-dates small">
            <div>
              <dt>впервые</dt>
              <dd>{{ formatDateTime(item.first_seen_at) }}</dd>
            </div>
            <div>
              <dt>последний раз</dt>
              <dd>{{ formatDateTime(item.last_seen_at) }}</dd>
            </div>
            <div>
              <dt>описание</dt>
              <dd>{{ item.last_detail_at ? formatDateTime(item.last_detail_at) : "не скачано" }}</dd>
            </div>
          </dl>
        </div>
        <div class="hero-chart">
          <h2 class="small muted">История цены</h2>
          <PriceChart :points="item.price_points" />
        </div>
      </section>

      <section v-if="item.advice" class="panel advice" aria-labelledby="advice-title">
        <div class="section-head">
          <h2 id="advice-title">Совет модели</h2>
          <span class="muted small num">
            интерес {{ formatScore(item.advice.interest) }}
            <template v-if="item.advice.model"> · {{ item.advice.model }}</template>
          </span>
        </div>
        <div v-if="item.advice.flags?.length" class="flags">
          <span
            v-for="flag in item.advice.flags"
            :key="flag"
            class="badge"
            :class="isWarningFlag(flag) ? 'bad' : ''"
          >
            {{ flagLabel(flag) }}
          </span>
        </div>
        <p class="advice-summary">{{ item.advice.summary || "Модель не оставила пояснения." }}</p>
        <div class="advice-lists">
          <div v-if="item.advice.keep?.length">
            <h3>что уже хорошо</h3>
            <ul>
              <li v-for="row in item.advice.keep" :key="'k' + row">{{ row }}</li>
            </ul>
          </div>
          <div v-if="item.advice.risks?.length">
            <h3>риски</h3>
            <ul>
              <li v-for="row in item.advice.risks" :key="'r' + row">{{ row }}</li>
            </ul>
          </div>
        </div>
      </section>

      <section class="panel" aria-labelledby="parts-title">
        <h2 id="parts-title">Комплектующие</h2>
        <dl class="parts">
          <div v-for="row in parts" :key="row.label">
            <dt>{{ row.label }}</dt>
            <dd>{{ row.value || "—" }}</dd>
          </div>
        </dl>
      </section>

      <section class="panel" aria-labelledby="potential-title">
        <h2 id="potential-title">Потенциал от платы</h2>
        <div v-if="scoreParts.length" class="meters">
          <label v-for="row in scoreParts" :key="row.label" class="meter-row">
            <span>{{ row.label }}</span>
            <meter
              min="0"
              :max="row.max"
              :low="row.max * 0.35"
              :high="row.max * 0.6"
              :optimum="row.max"
              :value="row.value"
            ></meter>
            <span class="num">{{ formatScore(row.value) }}<span class="muted"> / {{ row.max }}</span></span>
          </label>
        </div>
        <ul v-if="item.analysis?.reasons?.length" class="reasons">
          <li v-for="reason in item.analysis.reasons" :key="reason">{{ reason }}</li>
        </ul>
        <template v-if="item.analysis?.upgrades?.length">
          <h3>что можно сменить</h3>
          <ul>
            <li v-for="up in item.analysis.upgrades" :key="up">{{ up }}</li>
          </ul>
        </template>
        <p v-if="!item.analysis" class="muted">Ещё не разобрано — нажми «Пересчитать».</p>
      </section>

      <section v-if="item.analysis?.plan" class="panel wide" aria-labelledby="plan-title">
        <h2 id="plan-title">Смета, чтобы раскрыть потенциал</h2>
        <dl class="money">
          <div>
            <dt>купить</dt>
            <dd class="num">{{ formatEur(item.price_eur) }}</dd>
          </div>
          <div>
            <dt>докупить</dt>
            <dd class="num">{{ formatEur(item.analysis.plan.upgrade_cost_eur) }}</dd>
          </div>
          <div>
            <dt>вложить всего</dt>
            <dd class="num">{{ formatEur(item.analysis.plan.total_in_eur) }}</dd>
          </div>
          <div>
            <dt>продать готовую</dt>
            <dd class="num">{{ formatEur(item.analysis.plan.resale_eur) }}</dd>
          </div>
          <div>
            <dt>маржа</dt>
            <dd class="num" :class="profitTone(item.analysis.plan.profit_eur)">
              {{ formatEur(item.analysis.plan.profit_eur) }}
            </dd>
          </div>
        </dl>
        <div class="table-wrap">
          <table class="table plan-table">
            <thead>
              <tr>
                <th scope="col">действие</th>
                <th scope="col">позиция</th>
                <th scope="col" class="right">цена</th>
                <th scope="col">зачем</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in item.analysis.plan.items" :key="row.role + row.name">
                <td>
                  <span class="badge" :class="row.action === 'buy' ? 'mid' : 'good'">
                    {{ row.action === "buy" ? "купить" : "оставить" }}
                  </span>
                </td>
                <td>{{ row.name }}</td>
                <td class="right num">{{ row.action === "buy" ? formatEur(row.price_eur) : "—" }}</td>
                <td class="muted">{{ row.reason }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-for="note in item.analysis.plan.notes" :key="note" class="muted small">{{ note }}</p>
      </section>

      <section v-if="item.description" class="panel wide" aria-labelledby="text-title">
        <h2 id="text-title">Текст объявления</h2>
        <pre class="description">{{ item.description }}</pre>
      </section>
    </article>
  </div>
</template>
