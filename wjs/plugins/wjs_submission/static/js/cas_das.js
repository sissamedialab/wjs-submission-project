/**
 * Toggle the visibility of a field based on whether the selected value is one of the trigger values.
 *
 * @param {string} field - The identifier of the field group (e.g. "cas", "das").
 * @param {string} suffix - The field's id suffix (e.g. "text").
 * @param {string[]} triggerValues - The radio values that should reveal this field.
 * @param {string} value - The currently selected radio value.
 * @return {void}
 */
function fieldSelectedCheck(field, suffix, triggerValues, value) {
  const fieldEl = document.getElementById(`id_${field}_${suffix}`);
  if(!fieldEl) return
  const fieldWrapper = fieldEl.closest(".wjs-submission-form__form-label-wrapper");
  const fieldsStatusList = document.getElementById("wjs-submission-form__fields-list");

  if (fieldWrapper && triggerValues.includes(value)) {
    fieldWrapper.classList.remove("d-none");
    fieldEl.setAttribute("required", "true");
  } else if (fieldWrapper) {
    fieldWrapper.classList.add("d-none");
    fieldEl.removeAttribute("required");
  }
  populateRequiredChecklist(fieldsStatusList);
}

/**
 * Set the label and help text of the shared cas/das text box according to the selected declaration.
 *
 * The same box is used for the "url" and "other" declarations: it asks for a URL in the first
 * case and for a free-text statement in the second. The box's label is visually hidden
 * (label_class="d-none") and it has no placeholder (per the project's convention of not using
 * placeholders as instructions), so the visible help text below the box is what is actually shown.
 * The group's own "Required" marker already covers required-ness, so this text carries only the
 * url-vs-statement instruction, not another "Required" prefix.
 *
 * @param {string} field - The identifier of the field group (e.g. "cas", "das").
 * @param {string} value - The currently selected radio value.
 * @return {void}
 */
function textLabelCheck(field, value) {
  const labelEl = document.querySelector(`label[for="id_${field}_text"]`);
  const helpTextEl = document.getElementById(`id_${field}_text_helptext`);
  let text;
  if (value === "url") {
    text = "Please insert complete URL";
  } else if (value === "other") {
    text = "Please provide a statement or a URL";
  } else {
    return;
  }
  if (labelEl) labelEl.textContent = text;
  if (helpTextEl) helpTextEl.textContent = text;
}

/**
 * Toggle the visibility of the shared url/free-text input field based on the specified value.
 *
 * @param {string} field - The identifier of the field to toggle.
 * @param {string} value - The value to check against; controls visibility of the text input field.
 * @return {void}
 */
function textSelectedCheck(field, value) {
  fieldSelectedCheck(field, "text", ["url", "other"], value);
  textLabelCheck(field, value);
}
