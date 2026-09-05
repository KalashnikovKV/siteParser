<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { adviceClass, adviceLabel, formatEur, scoreClass } from "../lib/format";
import { catalog } from "../repositories/catalog";
import PriceChart from "../components/PriceChart.vue";
import type { ListingDetail } from "../types";

const { id } = defineProps<{ id: string }>();
const router = useRouter();
const item = ref<ListingDetail | null>(null);
const error = ref("");
const advising = ref(false);

function toList() {
  if (window.history.state?.back != null) {
    router.back();
    return;
  }
  router.push({ name: "list" });
}

async function load() {
  error.value = "";
  try {
    item.value = await catalog.listing(id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Не найдено";
  }
}

async function askModel() {
  advising.value = true;
  error.value = "";
  try {
    item.value = await catalog.adviseListing(id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Модель не ответила";
  } finally {
    advising.value = false;
  }
}

onMounted(load);
watch(() => id, load);
</script>

<template>
  <p><a href="/" @click.prevent="toList">← к списку</a></p>
  <p v-if="error" class="err">{{ error }}</p>
  <article v-if="item">
    <div class="card">
      <h2 style="margin-top: 0">{{ item.title }}</h2>
      <p>
        <span :class="scoreClass(item.score)">
          {{ item.score == null ? "нет оценки" : item.score.toFixed(1) }}
        </span>
        {{ item.verdict || "ещё не разобрано" }}
        · {{ item.price_eur == null ? "цена ?" : formatEur(item.price_eur) }}
        · {{ item.city }}
      </p>
      <p v-if="item.analysis?.price_note" class="muted">{{ item.analysis.price_note }}</p>
      <p>
        <a :href="item.url" target="_blank" rel="noreferrer">открыть на skelbiu.lt</a>
        ·
        <button :disabled="advising" @click="askModel">
          {{ advising ? "модель думает…" : item.advice ? "переспросить модель" : "спросить модель" }}
        </button>
      </p>
    </div>

    <div class="card" v-if="item.advice">
      <h3>Совет модели</h3>
      <p>
        <span :class="adviceClass(item.advice.action)">{{ adviceLabel(item.advice.action) }}</span>
        · интерес {{ item.advice.interest.toFixed(0) }}
        <span class="muted" v-if="item.advice.model"> · {{ item.advice.model }}</span>
      </p>
      <p>{{ item.advice.summary }}</p>
      <p v-if="item.advice.keep?.length"><b>что уже хорошо</b></p>
      <ul>
        <li v-for="row in item.advice.keep || []" :key="'k' + row">{{ row }}</li>
      </ul>
      <p v-if="item.advice.risks?.length"><b>риски</b></p>
      <ul>
        <li v-for="row in item.advice.risks || []" :key="'r' + row">{{ row }}</li>
      </ul>
      <p v-if="item.advice.flags?.length" class="muted">
        {{ item.advice.flags.join(" · ") }}
      </p>
    </div>

    <div class="grid2">
      <div class="card">
        <h3>Комплектующие</h3>
        <dl class="parts">
          <dt>процессор</dt>
          <dd>{{ item.parts.cpu || "—" }}</dd>
          <dt>материнская плата</dt>
          <dd>{{ item.parts.motherboard || item.parts.chipset || "—" }}</dd>
          <dt>сокет</dt>
          <dd>{{ item.socket || item.parts.socket || "—" }}</dd>
          <dt>видеокарта</dt>
          <dd>{{ item.parts.gpu || "нет / не указана" }}</dd>
          <dt>память</dt>
          <dd>{{ item.parts.ram || "—" }}</dd>
          <dt>накопитель</dt>
          <dd>{{ item.parts.storage || "—" }}</dd>
          <dt>БП</dt>
          <dd>{{ item.parts.psu || "—" }}</dd>
        </dl>
      </div>
      <div class="card">
        <h3>Потенциал от платы</h3>
        <p v-if="item.analysis">
          платформа {{ item.analysis.platform_score }} ·
          запас {{ item.analysis.headroom_score }} ·
          слоты/БП {{ item.analysis.expandability_score }} ·
          цена {{ item.analysis.value_score }}
        </p>
        <ul>
          <li v-for="reason in item.analysis?.reasons || []" :key="reason">{{ reason }}</li>
        </ul>
        <p v-if="item.analysis?.upgrades?.length"><b>что можно сменить</b></p>
        <ul>
          <li v-for="up in item.analysis?.upgrades || []" :key="up">{{ up }}</li>
        </ul>
      </div>
    </div>

    <div class="card" v-if="item.analysis?.plan">
      <h3>Смета, чтобы раскрыть потенциал</h3>
      <p>
        купить объявление
        <b>{{ item.price_eur == null ? "?" : `${item.price_eur.toFixed(0)} €` }}</b>
        · докупить
        <b>{{ item.analysis.plan.upgrade_cost_eur }} €</b>
        · вложить всего
        <b>{{ item.analysis.plan.total_in_eur ?? "—" }} €</b>
        · продать готовую
        <b>{{ item.analysis.plan.resale_eur ?? "—" }} €</b>
        · маржа
        <b :class="item.analysis.plan.profit_eur != null && item.analysis.plan.profit_eur < 0 ? 'bad' : 'good'">
          {{ item.analysis.plan.profit_eur ?? "—" }} €
        </b>
      </p>
      <table class="table plan-table">
        <thead>
          <tr>
            <th>действие</th>
            <th>позиция</th>
            <th>цена</th>
            <th>зачем</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in item.analysis.plan.items" :key="row.role + row.name">
            <td>{{ row.action === "buy" ? "купить" : "оставить" }}</td>
            <td>{{ row.name }}</td>
            <td>{{ row.action === "buy" ? `${row.price_eur} €` : "—" }}</td>
            <td class="muted">{{ row.reason }}</td>
          </tr>
        </tbody>
      </table>
      <p class="muted" v-for="note in item.analysis.plan.notes" :key="note">{{ note }}</p>
    </div>

    <div class="card">
      <h3>Цена</h3>
      <PriceChart :points="item.price_points" />
    </div>

    <div class="card" v-if="item.description">
      <h3>Текст объявления</h3>
      <pre style="white-space: pre-wrap; font: inherit">{{ item.description }}</pre>
    </div>
  </article>
</template>
