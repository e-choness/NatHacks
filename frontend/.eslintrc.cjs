module.exports = {
  root: true,
  extends: ["next/core-web-vitals", "plugin:react-hooks/recommended"],
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module"
  },
  rules: {
    "@next/next/no-img-element": "off",
    "react/react-in-jsx-scope": "off",
    "react-hooks/exhaustive-deps": "warn"
  }
};
