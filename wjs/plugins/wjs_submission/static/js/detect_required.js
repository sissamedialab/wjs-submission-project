function getForm() {
  return document.querySelector(".wjs-submission-form");
}

/**
 * Retrieves the text content of the nearest preceding element with wjs-submission-form__form-label--required class relative to a given field within a form.
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
      if (sibling.classList.contains("wjs-submission-form__form-label--required")) {
        return sibling.textContent.trim();
      }
      sibling = sibling.previousElementSibling;
    }
    el = el.parentElement;
  }
}

/**
 * Remove all HTML tags from the provided string and return plain text.
 *
 * @param {string} html - The string containing HTML tags to be stripped.
 * @return {string} The plain text with all HTML tags removed.
 */
function stripHtmlTags(html) {
  // Create a temporary div element to parse HTML
  const tempDiv = document.createElement("div");
  tempDiv.innerHTML = html;

  // Get text content (automatically strips HTML tags)
  return tempDiv.textContent || tempDiv.innerText || "";
}


/**
 * Check if the given field contains non-empty textual content, either as HTML field or TinyMCE editor.
 *
 * @param {Object} field - The Element object to evaluate.
 * @return {boolean} Returns true if the field contains non-empty text content, otherwise false.
 */
function hasContent(field) {
  const editor = tinymce.get(field.id);
  const htmlContent = editor && editor.getContent() ? editor.getContent() : field.value;

  // Get content and strip HTML
  const textContent = stripHtmlTags(htmlContent);
  return textContent.trim().length > 0;
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
function allFilled(form, fields) {

  return fields.every(field => {
    if (field.type === "radio") {
      return !!form.querySelector(`input[type="radio"][name="${field.name}"]:checked`);
    }
    if (field.type === "checkbox") return field.checked;
    if (field.tagName === "SELECT") return field.value !== "";
    if (field.tagName === "TEXTAREA") {
      return hasContent(field);
    }
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
    const filled = allFilled(form, fields);
    if (filled) {
      fieldStatusItem.classList.add("wjs-submission-form__label--filled");
    } else {
      fieldStatusItem.classList.remove("wjs-submission-form__label--filled");
      allSectionsFilled = false;
    }
  });

  submitBtn.disabled = !allSectionsFilled;
}


/**
 * Retrieve the list of required fields from a given form element.
 * Filters out duplicate required radio groups to ensure only one entry for each group.
 *
 * @param {HTMLFormElement} form - The form element to inspect for required fields.
 * @return {Array<Element>} The array of required field elements, including unique entries for radio groups.
 */
function getRequiredFields(form) {
  const radios = new Set();

  return Array.from(form.querySelectorAll("[required]:not([required=\"false\"]),[js_required]")).map(field => {
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
  const formFooter = document.getElementById("form-footer");

  const fieldsStatusList = document.createElement("ul");
  fieldsStatusList.id = "wjs-submission-form__fields-list";
  fieldsStatusList.setAttribute("aria-live", "polite");
  formFooter.insertAdjacentElement("beforebegin", fieldsStatusList);
  populateRequiredChecklist(fieldsStatusList);
}

/**
 * Adds a TinyMCE change event listener to a specified field's editor.
 * The event listener triggers an update to the required checklist.
 *
 * @param {Object} field The field object containing the editor's id.
 * @return {void}
 */
function addTinyMceListener(field) {
  const editor = tinymce.get(field.id);
  if (editor) {
    editor.on("change", function() {
      updateRequiredChecklist();
    });
  }
}

/**
 * Populates the checklist of required fields for a given form and attaches event listeners to ensure
 * the checklist updates dynamically upon changes.
 *
 * @param {HTMLElement} fieldsStatusList - The DOM element representing the checklist container where required fields will be rendered.
 * @return {void} Does not return a value.
 */
function populateRequiredChecklist(fieldsStatusList) {
  const form = getForm();
  const sectionMap = new Map();

  getRequiredFields(form).forEach(field => {
    const section = getSectionHeading(field);
    if (!sectionMap.has(section)) {
      sectionMap.set(section, []);
    }
    sectionMap.get(section).push(field);
    addTinyMceListener(field);
  });

  while (fieldsStatusList.firstChild) {
    fieldsStatusList.removeChild(fieldsStatusList.firstChild);
  }

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
