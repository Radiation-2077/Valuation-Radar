import pluginVue from "eslint-plugin-vue";
import { defineConfigWithVueTs, vueTsConfigs } from "@vue/eslint-config-typescript";

export default defineConfigWithVueTs(
  {
    ignores: ["dist/**", "coverage/**"],
  },
  pluginVue.configs["flat/essential"],
  vueTsConfigs.recommended,
);
