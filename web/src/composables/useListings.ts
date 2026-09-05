import { onMounted, ref } from "vue";
import { catalog } from "../repositories/catalog";
import type { Filters, ListingCard } from "../types";
import { useDebouncedWatch } from "./useDebouncedWatch";
import { useListQuery } from "./useListQuery";

export function useListings() {
  const query = useListQuery();
  const items = ref<ListingCard[]>([]);
  const total = ref(0);
  const options = ref<Filters>({ cities: [], sockets: [], sources: [] });
  const error = ref("");

  function resetPage() {
    query.page = 1;
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
    await load();
  });

  useDebouncedWatch(() => ({ ...query }), load, 250);

  return { query, items, total, options, error, resetPage, load };
}
