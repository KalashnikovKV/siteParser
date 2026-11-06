import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import ListView from "./views/ListView.vue";
import DetailView from "./views/DetailView.vue";
import "./styles.css";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "list", component: ListView },
    { path: "/listing/:id", name: "detail", component: DetailView, props: true },
    { path: "/:pathMatch(.*)*", redirect: { name: "list" } },
  ],
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition;
    // Фильтры и сортировка меняют только query — страница не должна прыгать наверх.
    if (to.path === from.path) return false;
    return { top: 0 };
  },
});

router.afterEach((to) => {
  document.title = to.name === "detail" ? "Объявление — Skelbiu PC" : "Skelbiu PC — локальная база";
});

createApp(App).use(router).mount("#app");
