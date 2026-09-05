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
  ],
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition ?? { top: 0 };
  },
});

createApp(App).use(router).mount("#app");
