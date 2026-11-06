import { onMounted, ref } from "vue";
import { catalog } from "../repositories/catalog";
import type { Filters, ListingCard, PicksPage } from "../types";
import { useDebouncedWatch } from "./useDebouncedWatch";
import { useListQuery } from "./useListQuery";

export const PAGE_SIZE = 30;

export function useListings() {
  const { query, clearFilters, applyPreset, showAll } = useListQuery();
  const items = ref<ListingCard[]>([]);
  const picks = ref<PicksPage | null>(null);
  const total = ref(0);
  const options = ref<Filters>({ cities: [], sockets: [], sources: [] });
  const error = ref("");
  const loading = ref(false);
  let inflight: AbortController | null = null;

  function resetPage() {
    query.page = 1;
    if (query.preset) query.preset = "";
  }

  async function loadPicks() {
    try {
      picks.value = await catalog.picks(8);
    } catch {
      picks.value = null;
    }
  }

  async function loadOptions() {
    try {
      options.value = await catalog.filters();
    } catch {
      /* фильтры без списков городов и сокетов — не повод ломать выдачу */
    }
  }

  async function load() {
    inflight?.abort();
    const controller = new AbortController();
    inflight = controller;
    loading.value = true;
    try {
      const page = await catalog.listings(
        {
          q: query.q,
          min_price: query.min_price,
          max_price: query.max_price,
          city: query.city,
          socket: query.socket,
          source: query.source,
          potential: query.potential,
          advice: query.advice,
          min_score: query.min_score,
          min_profit: query.min_profit,
          has_description: query.has_description,
          preset: query.preset,
          kind: query.kind,
          sort: query.sort,
          page: query.page,
          limit: PAGE_SIZE,
        },
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      items.value = page.items;
      total.value = page.total;
      error.value = "";
    } catch (err) {
      if (controller.signal.aborted) return;
      error.value = err instanceof Error ? err.message : "Ошибка поиска";
    } finally {
      if (inflight === controller) {
        inflight = null;
        loading.value = false;
      }
    }
  }

  onMounted(async () => {
    await Promise.all([loadOptions(), load(), loadPicks()]);
  });

  useDebouncedWatch(() => ({ ...query }), load, 250);

  return {
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
  };
}
