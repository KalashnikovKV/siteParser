import { onMounted, ref } from "vue";
import { catalog } from "../repositories/catalog";
import type { AdvisorStatus, JobStatus, Stats } from "../types";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useBackgroundJob() {
  const stats = ref<Stats | null>(null);
  const advisor = ref<AdvisorStatus | null>(null);
  const analyzeJob = ref<JobStatus | null>(null);
  const detailsJob = ref<JobStatus | null>(null);
  const adviseJob = ref<JobStatus | null>(null);
  const analyzeBusy = ref(false);
  const detailsBusy = ref(false);
  const adviseBusy = ref(false);
  const error = ref("");
  const dataTick = ref(0);

  async function refreshStats() {
    try {
      stats.value = await catalog.stats();
      advisor.value = await catalog.advisorStatus();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Нет связи с API";
    }
  }

  function watchStream(
    kind: string,
    current: { value: JobStatus | null },
  ): Promise<JobStatus> {
    return new Promise((resolve, reject) => {
      const source = new EventSource(`/api/jobs/${kind}/stream`);
      source.onmessage = (event) => {
        const status = JSON.parse(event.data) as JobStatus;
        current.value = status;
        if (status.stats) stats.value = status.stats;
        if (!status.running) {
          source.close();
          if (status.error) reject(new Error(status.error));
          else resolve(status);
        }
      };
      source.onerror = () => {
        source.close();
        const last = current.value;
        if (last && !last.running) {
          if (last.error) reject(new Error(last.error));
          else resolve(last);
          return;
        }
        reject(new Error("stream"));
      };
    });
  }

  async function waitUntilIdle(
    kind: string,
    poll: () => Promise<JobStatus>,
    current: { value: JobStatus | null },
    busy: { value: boolean },
  ) {
    busy.value = true;
    error.value = "";
    try {
      try {
        await watchStream(kind, current);
      } catch {
        while (true) {
          const status = await poll();
          current.value = status;
          if (status.stats) stats.value = status.stats;
          if (!status.running) {
            if (status.error) throw new Error(status.error);
            return status;
          }
          await sleep(2000);
        }
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Задача не удалась";
      await refreshStats();
    } finally {
      busy.value = false;
      dataTick.value += 1;
    }
  }

  async function run(
    kind: string,
    start: () => Promise<JobStatus>,
    poll: () => Promise<JobStatus>,
    current: { value: JobStatus | null },
    busy: { value: boolean },
  ) {
    if (busy.value) return;
    busy.value = true;
    error.value = "";
    try {
      current.value = await start();
      if (!current.value.running && (current.value.total ?? 0) === 0) {
        if (kind === "details") {
          error.value = "Нечего докачивать: нет пустых или устаревших описаний";
        }
        busy.value = false;
        await refreshStats();
        dataTick.value += 1;
        return;
      }
      await waitUntilIdle(kind, poll, current, busy);
      if (!current.value?.stats) await refreshStats();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Задача не удалась";
      await refreshStats();
      busy.value = false;
    }
  }

  onMounted(async () => {
    await refreshStats();
    const [analyze, details, advise] = await Promise.all([
      catalog.analyzeStatus(),
      catalog.detailsStatus(),
      catalog.advisorStatus(),
    ]);
    analyzeJob.value = analyze;
    detailsJob.value = details;
    adviseJob.value = advise.job ?? null;
    if (analyze.running) waitUntilIdle("analyze", catalog.analyzeStatus, analyzeJob, analyzeBusy);
    if (details.running) waitUntilIdle("details", catalog.detailsStatus, detailsJob, detailsBusy);
    if (advise.job?.running) {
      waitUntilIdle("advise", catalog.adviseJob, adviseJob, adviseBusy);
      return;
    }
    // Сами предлагаем лучшие варианты: если модель жива и мало советов — догоняем.
    if (advise.available && (stats.value?.advised ?? 0) < 20 && !adviseBusy.value) {
      run("advise", () => catalog.advise(), catalog.adviseJob, adviseJob, adviseBusy);
    }
  });

  return {
    stats,
    advisor,
    analyzeJob,
    detailsJob,
    adviseJob,
    analyzeBusy,
    detailsBusy,
    adviseBusy,
    error,
    dataTick,
    refreshStats,
    analyze: () =>
      run("analyze", () => catalog.analyze(), catalog.analyzeStatus, analyzeJob, analyzeBusy),
    fetchDetails: () =>
      run("details", () => catalog.details(), catalog.detailsStatus, detailsJob, detailsBusy),
    advise: () => run("advise", () => catalog.advise(), catalog.adviseJob, adviseJob, adviseBusy),
  };
}
