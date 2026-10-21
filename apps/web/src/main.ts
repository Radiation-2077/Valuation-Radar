import { VueQueryPlugin } from "@tanstack/vue-query";
import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import "katex/dist/katex.min.css";
import "./styles/index.css";

createApp(App).use(router).use(VueQueryPlugin).mount("#app");
