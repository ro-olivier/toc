import {app, constants, dom, i18n, state} from "./context.js";

app.translateStaticInterface = function translateStaticInterface() {
  document.title = i18n.t("app.title");

  document.querySelectorAll("[data-i18n]").forEach(element => {
    element.textContent = i18n.t(element.dataset.i18n);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach(element => {
    element.placeholder = i18n.t(element.dataset.i18nPlaceholder);
  });

  document.querySelectorAll("[data-i18n-dynamic]").forEach(element => {
    const parameters = element.dataset.i18nParameters ? JSON.parse(element.dataset.i18nParameters) : {};
    element.textContent = i18n.t(element.dataset.i18nDynamic, parameters);
  });

  document.querySelectorAll("[data-i18n-title]").forEach(element => {
    const translation = i18n.t(element.dataset.i18nTitle);
    element.title = translation;
    element.setAttribute("aria-label", translation);
  });
};

app.refreshLanguageInterface = function refreshLanguageInterface() {
  app.translateStaticInterface();

  Array.from(dom.languageSelect.options).forEach(option => {
    option.textContent = i18n.t(`language.${option.value}`);
  });

  if (state.ruleConfiguration) {
    const customValues = dom.customRulesFields.querySelector("[data-rule-name]") ? app.collectCustomRuleValues() : state.ruleConfiguration.presets[state.ruleConfiguration.default];
    const customOption = Array.from(dom.rulePresetSelect.options).find(option => option.value === "custom");

    if (customOption) customOption.textContent = i18n.t("rules.custom_option");

    app.renderCustomRuleControls(state.ruleConfiguration.schema, customValues);
    app.updateRulesetEditorVisibility();
  }

  app.renderOpenLobbies();
  app.refreshResumeGamePanel();

  if (state.displayedRuleset) app.renderRulesetDisplays(state.displayedRuleset);

  if (state.currentLobbyState && !dom.lobbyScreen.classList.contains("hidden")) {
    app.renderLobbyState(state.currentLobbyState);
  }

  state.backendMessageElements.forEach((message, element) => {
    element.textContent = app.getMessage(message);
  });

  app.renderActivityLog();
};

app.initializeLanguageInterface = function initializeLanguageInterface() {
    i18n.supportedLanguages.forEach(language => {
    const option = document.createElement("option");
    option.value = language;
    dom.languageSelect.appendChild(option);
  });

  dom.languageSelect.value = i18n.getLanguage();
  app.refreshLanguageInterface();

  dom.languageSelect.addEventListener("change", () => i18n.setLanguage(dom.languageSelect.value));
  window.addEventListener("toc-language-change", app.refreshLanguageInterface);
  window.addEventListener("toc-language-change", app.refreshLocalHandLabels);

};

app.setTranslatedText = function setTranslatedText(element, key, parameters = {}) {
  state.backendMessageElements.delete(element);
  element.dataset.i18nDynamic = key;
  element.dataset.i18nParameters = JSON.stringify(parameters);
  element.textContent = i18n.t(key, parameters);
};

app.setRawText = function setRawText(element, text) {
  state.backendMessageElements.delete(element);
  delete element.dataset.i18nDynamic;
  delete element.dataset.i18nParameters;
  element.textContent = text;
};

app.getMessage = function getMessage(message) {
  if (typeof message === "string") return message;

  if (!message?.messageKey) {
    console.warn("Received a player-facing message without messageKey:", message);
    return message?.fallback || "";
  }

  const parameters = {...(message.parameters || {})};
  if (parameters.color) parameters.color = app.formatColorName(parameters.color);

  const translatedMessage = i18n.t(message.messageKey, parameters);

  if (translatedMessage !== message.messageKey) return translatedMessage;

  console.warn(`Missing translation: ${message.messageKey}`);
  return message.fallback || message.messageKey;
};

app.getHttpErrorMessage = function getHttpErrorMessage(responseData) {
  const detail = responseData?.detail;

  if (detail && typeof detail === "object" && !Array.isArray(detail) && detail.messageKey) {
    return app.getMessage(detail);
  }

  if (typeof detail === "string") return detail;

  return i18n.t("errors.game_creation_failed");
};

app.setMessageText = function setMessageText(element, message) {
  if (typeof message === "string") {
    app.setRawText(element, message);
    return;
  }

  delete element.dataset.i18nDynamic;
  delete element.dataset.i18nParameters;
  state.backendMessageElements.set(element, message);
  element.textContent = app.getMessage(message);
};

app.renderActivityLog = function renderActivityLog() {
  dom.terminal.textContent = state.activityMessages.map(entry => {
    const prefix = entry.isError ? i18n.t("common.error_prefix") : "";
    return `${prefix}${app.getMessage(entry.message)}`;
  }).join("\n");

  dom.terminal.scrollTop = dom.terminal.scrollHeight;
};

app.log = function log(message, isError = false) {
  state.activityMessages.push({message, isError});
  app.renderActivityLog();
};

app.query = function query(message) {
  app.setMessageText(dom.turnInstruction, message);
  dom.turnInstruction.classList.remove("error-state");
  app.log(message);
};

app.error = function error(message) {
  app.setMessageText(dom.turnInstruction, message);
  dom.turnInstruction.classList.add("error-state");
  app.log(message, true);
};

app.formatPresetName = function formatPresetName(name) {
  const translationKey = `rules.presets.${name}`;
  const translatedName = i18n.t(translationKey);
  return translatedName === translationKey ? name.charAt(0).toUpperCase() + name.slice(1).replaceAll("_", " ") : translatedName;
};

app.formatColorName = function formatColorName(color) {
  const translationKey = `colors.${color}`;
  const translatedColor = i18n.t(translationKey);
  return translatedColor === translationKey ? color : translatedColor;
};

app.formatRuleChoice = function formatRuleChoice(ruleName, value) {
  const valueKey = Array.isArray(value) ? value.join("_") : String(value);
  const translationKey = `rules.choices.${ruleName}.${valueKey}`;
  const translatedValue = i18n.t(translationKey);
  return translatedValue === translationKey ? String(value).replaceAll("_", " ") : translatedValue;
};

app.createRuleTitle = function createRuleTitle(ruleName, controlId = null) {
  const labelText = i18n.t(`rules.labels.${ruleName}`);
  const description = i18n.t(`rules.descriptions.${ruleName}`);

  const title = document.createElement("div");
  title.className = "rule-title";

  const label = document.createElement(controlId ? "label" : "span");
  label.textContent = labelText;
  if (controlId) label.htmlFor = controlId;
  title.appendChild(label);

  if (description !== `rules.descriptions.${ruleName}`) {
    const helpWrapper = document.createElement("span");
    helpWrapper.className = "rule-help-wrapper";

    const help = document.createElement("button");
    help.type = "button";
    help.className = "rule-help-trigger";
    help.textContent = "?";
    help.setAttribute("aria-label", `${labelText}: ${description}`);

    const tooltip = document.createElement("span");
    tooltip.className = "rule-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.textContent = description;

    helpWrapper.append(help, tooltip);
    title.appendChild(helpWrapper);
  }

  return title;
};
