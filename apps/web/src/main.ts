import { VueQueryPlugin } from "@tanstack/vue-query";
import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import "./styles/index.css";

createApp(App).use(router).use(VueQueryPlugin).mount("#app");
