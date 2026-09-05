import { watch, type WatchSource } from "vue";

export function useDebouncedWatch<T>(
  source: WatchSource<T>,
  callback: () => void,
  delayMs = 250,
) {
  let timer = 0;
  watch(
    source,
    () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(callback, delayMs);
    },
    { deep: true },
  );
}
