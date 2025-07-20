function getForm() {
  return document.querySelector(".wjs-submission-form");
}

/**
 * Retrieves the text content of the nearest preceding H3 element relative to a given field within a form.
 *
 * @param {HTMLElement} field - The starting element to search upward from.
 * @return {string|undefined} The text content of the nearest H3 element if found, or undefined if no such element exists.
 */
function getSectionHeading(field) {
  const form = getForm();

  let el = field;
  while (el && el !== form) {
    let sibling = el.previousElementSibling;
    while (sibling) {
      if (sibling.tagName === "H3") {
        return sibling.textContent.trim();
      }
      sibling = sibling.previousElementSibling;
    }
    el = el.parentElement;
  }
}

/**
 * Checks if all the provided form fields are filled based on their types.
 * For radio inputs, it verifies if any option in the group is selected.
 * For checkboxes, it checks if the box is checked.
 * For select elements, it ensures a non-empty value is selected.
 * For other input types, it validates that the value is not empty or whitespace.
 *
 * @param form
 * @param {Array} fields - An array of form field elements to be checked.
 * @return {boolean} Returns true if all fields are considered filled, otherwise false.
 */
function isFilled(form, fields) {
  return fields.every(field => {
    if (field.type === "radio") {
      return !!form.querySelector(`input[type="radio"][name="${field.name}"]:checked`);
    }
    if (field.type === "checkbox") return field.checked;
    if (field.tagName === "SELECT") return field.value !== "";
    return field.value?.trim() !== "";
  });
}

/**
 * Updates the checklist items by validating if their associated fields are filled
 * and applies the corresponding CSS classes to the list items.
 * Additionally, determines if the submit button should be enabled or disabled
 * based on the completion status of all checklist items.
 *
 * @return {void} This function does not return a value.
 */
function updateRequiredChecklist() {
  let allSectionsFilled = true;
  const form = getForm();
  const submitBtn = document.getElementById("submit-btn");
  const fieldsStatusList = document.getElementById("wjs-submission-form__fields-list");

  fieldsStatusList.childNodes.forEach(fieldStatusItem => {
    const fields = JSON.parse(fieldStatusItem.dataset.fields).map(field => {
      return document.getElementById(field);
    });
    const filled = isFilled(form, fields);
    if (filled) {
      if (fieldStatusItem.dataset.section.toLowerCase().indexOf("arxiv") === -1) {
        fieldStatusItem.classList.add("wjs-submission-form__label--filled");
      }
    } else {
      fieldStatusItem.classList.remove("wjs-submission-form__label--filled");
      allSectionsFilled = false;
    }
  });

  submitBtn.disabled = !allSectionsFilled;
}


function getRequiredFields(form) {
  const radios = new Set();

  return Array.from(form.querySelectorAll("[required]")).map(field => {
    if (field.type === "radio") {
      if (radios.has(field.name)) return;
      radios.add(field.name);
    }
    return field;
  });
}

/**
 * Sets up a required checklist for a form based on required fields.
 * Identifies and groups required fields within form sections, dynamically
 * creates a list for tracking field completion status, and attaches necessary
 * event listeners for handling updates.
 *
 * @return {void} No return value, modifies the DOM by appending checklist elements and event listeners.
 */
function setupRequiredChecklist() {
  const form = getForm();
  const formFooter = document.getElementById("form-footer");
  const sectionMap = new Map();

  const fieldsStatusList = document.createElement("ul");
  fieldsStatusList.id = "wjs-submission-form__fields-list";
  fieldsStatusList.setAttribute("aria-live", "polite");
  form.insertBefore(fieldsStatusList, formFooter);

  getRequiredFields(form).forEach(field => {
    const section = getSectionHeading(field);
    if (!sectionMap.has(section)) {
      sectionMap.set(section, []);
    }
    sectionMap.get(section).push(field);
  });

  // For each section pick all required fields and listen for change event to trigger rerendering of
  // required fields list
  sectionMap.forEach((fields, section) => {
    const fieldsStatusListItem = document.createElement("li");
    fieldsStatusListItem.textContent = section;
    fieldsStatusListItem.dataset.section = section;
    fieldsStatusListItem.dataset.fields = JSON.stringify(fields.map(field => field.id));
    fieldsStatusList.appendChild(fieldsStatusListItem);
    attachEventListener(form, fields);
  });
  updateRequiredChecklist();
}


/**
 * Attaches event listeners to form fields to update required checklist on user interaction.
 *
 * @param {Array} item.fields - An array of field objects that represent the form fields.
 * @param {string} item.fields[].type - The type of the field, e.g., "radio".
 * @param {string} item.fields[].name - The name attribute of the field.
 * @return {void} This function does not return any value.
 * @param form
 * @param fields
 */
function attachEventListener(form, fields) {
  fields.forEach(field => {
    if (field.type === "radio") {
      form
        .querySelectorAll(`input[type="radio"][name="${field.name}"]`)
        .forEach(radio => radio.addEventListener("change", updateRequiredChecklist));
    } else {
      ["input", "change"].forEach(event => {
        field.addEventListener(event, updateRequiredChecklist);
      });
    }
  });
}
