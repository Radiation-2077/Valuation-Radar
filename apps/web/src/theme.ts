import type { GlobalThemeOverrides } from "naive-ui";

export const darkThemeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#57d6b1",
    primaryColorHover: "#72e4c3",
    primaryColorPressed: "#42bd9b",
    primaryColorSuppl: "#57d6b1",
    infoColor: "#80c7ff",
    warningColor: "#e8b86d",
    errorColor: "#ee8c78",
    successColor: "#57d6b1",
    bodyColor: "#07131f",
    cardColor: "#0d2030",
    modalColor: "#0a1a27",
    popoverColor: "#0d2030",
    textColorBase: "#dce7ef",
    textColor1: "#dce7ef",
    textColor2: "#a9bac6",
    textColor3: "#8296a5",
    borderColor: "rgba(158, 190, 210, 0.18)",
    dividerColor: "rgba(158, 190, 210, 0.14)",
    borderRadius: "12px",
  },
  Card: {
    borderRadius: "18px",
  },
  Button: {
    borderRadiusMedium: "10px",
    borderRadiusSmall: "8px",
    borderRadiusTiny: "6px",
  },
  Input: {
    borderRadius: "10px",
  },
  Select: {
    peers: {
      InternalSelection: {
        borderRadius: "10px",
      },
    },
  },
  Drawer: {
    color: "#081622",
  },
  DataTable: {
    thColor: "transparent",
    tdColor: "transparent",
    tdColorHover: "rgba(87, 214, 177, 0.04)",
    borderColor: "rgba(158, 190, 210, 0.12)",
  },
};

export const lightThemeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#0e9f7d",
    primaryColorHover: "#17b892",
    primaryColorPressed: "#0a8367",
    primaryColorSuppl: "#0e9f7d",
    infoColor: "#3478c8",
    warningColor: "#b77a1f",
    errorColor: "#c45645",
    successColor: "#0e9f7d",
    bodyColor: "#eef4f7",
    cardColor: "#ffffff",
    modalColor: "#ffffff",
    popoverColor: "#ffffff",
    textColorBase: "#172833",
    textColor1: "#172833",
    textColor2: "#405865",
    textColor3: "#728692",
    borderColor: "rgba(38, 73, 91, 0.16)",
    dividerColor: "rgba(38, 73, 91, 0.12)",
    borderRadius: "12px",
  },
  Card: {
    borderRadius: "18px",
  },
  Button: {
    borderRadiusMedium: "10px",
    borderRadiusSmall: "8px",
    borderRadiusTiny: "6px",
  },
  Input: {
    borderRadius: "10px",
  },
  Select: {
    peers: {
      InternalSelection: {
        borderRadius: "10px",
      },
    },
  },
  Drawer: {
    color: "#f8fbfc",
  },
  DataTable: {
    thColor: "transparent",
    tdColor: "transparent",
    tdColorHover: "rgba(14, 159, 125, 0.06)",
    borderColor: "rgba(38, 73, 91, 0.12)",
  },
};
