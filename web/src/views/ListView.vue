<script setup lang="ts">
import { onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useListings } from "../composables/useListings";
import { adviceClass, adviceLabel, formatEur, profitTone, scoreClass } from "../lib/format";

defineOptions({ name: "ListView" });

const props = defineProps<{ dataTick?: number }>();
const emit = defineEmits<{ changed: [] }>();
const router = useRouter();
const { query, items, total, options, error, resetPage, load } = useListings();

onMounted(() => emit("changed"));
watch(
  () => props.dataTick,
  (next, prev) => {
    if (prev != null && next !== prev) load();
  },
);
</script>

<template>
  <section class="filters">
    <input v-model.trim="query.q" placeholder="поиск по тексту, CPU, плате…" @input="resetPage" />
    <input v-model="query.min_price" type="number" placeholder="цена от" @input="resetPage" />
    <input v-model="query.max_price" type="number" placeholder="цена до" @input="resetPage" />
    <select v-model="query.city" @change="resetPage">
      <option value="">город</option>
      <option v-for="city in options.cities" :key="city" :value="city">{{ city }}</option>
    </select>
    <select v-model="query.socket" @change="resetPage">
      <option value="">сокет</option>
      <option v-for="socket in options.sockets" :key="socket" :value="socket">{{ socket }}</option>
    </select>
    <select v-if="options.sources.length > 1" v-model="query.source" @change="resetPage">
      <option value="">все источники</option>
      <option v-for="src in options.sources" :key="src" :value="src">{{ src }}</option>
    </select>
    <select v-model="query.potential" @change="resetPage">
      <option value="">любой запас</option>
      <option value="true">есть апгрейд</option>
      <option value="false">без запаса</option>
    </select>
    <select v-model="query.sort">
      <option value="score">по потенциалу</option>
      <option value="price_asc">дешевле</option>
      <option value="price_desc">дороже</option>
      <option value="profit">по марже</option>
      <option value="resale">по продаже</option>
      <option value="cost">по смете</option>
      <option value="ai">по модели</option>
      <option value="seen">свежие</option>
      <option value="title">название</option>
    </select>
  </section>

  <p v-if="error" class="err">{{ error }}</p>
  <p class="muted">Найдено {{ total }} в локальной базе</p>

  <table class="table">
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
        @click="router.push({ name: 'detail', params: { id: item.id } })"
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
