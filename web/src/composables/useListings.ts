import { onMounted, ref } from "vue";
import { catalog } from "../repositories/catalog";
import type { Filters, ListingCard, PicksPage } from "../types";
import { useDebouncedWatch } from "./useDebouncedWatch";
import { useListQuery } from "./useListQuery";

export function useListings() {
  const { query, clearFilters, applyPreset, showAll } = useListQuery();
  const items = ref<ListingCard[]>([]);
  const picks = ref<PicksPage | null>(null);
  const total = ref(0);
  const options = ref<Filters>({ cities: [], sockets: [], sources: [] });
  const error = ref("");

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

  async function load() {
    error.value = "";
    try {
      const page = await catalog.listings({
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
        limit: 30,
      });
      items.value = page.items;
      total.value = page.total;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Ошибка поиска";
    }
  }

  onMounted(async () => {
    options.value = await catalog.filters();
    await Promise.all([load(), loadPicks()]);
  });

  useDebouncedWatch(() => ({ ...query }), load, 250);

  return {
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
  };
}
