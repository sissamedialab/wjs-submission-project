/**
 * Set true to enable debugging messages.
 *
 * @type {boolean}
 */
const debug = false;

function getForm() {
  return document.querySelector(".wjs-submission-form");
}

/**
 * Retrieves the nearest preceding element with wjs-submission-form__form-label--required class relative to a given field within a form.
 *
 * @param {HTMLElement} field - The starting element to search upward from.
 * @return {HTMLElement} The element the nearest H3 element if found, or undefined if no such element exists.
 */
function getSectionHeading(field) {
  const form = getForm();

  let el = field;
  while (el && el !== form) {
    let sibling = el.previousElementSibling;
    while (sibling) {
      if (sibling.classList.contains("wjs-submission-form__form-label--required")) {
        return sibling;
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
 * Retrieves the alternate field specified by the "alternate_field" attribute of the given field.
 *
 * If the field declares an alternate field, that field can be checked instead.
 *
 * @param {HTMLFormElement} form The form containing the alternate field.
 * @param {HTMLElement} field The field element to check for an alternate field.
 * @return {HTMLElement | null} The alternate field element if it exists; otherwise, null.
 */
function getAlternateField(form, field) {
  const alternateFieldName = field.getAttribute("alternate_field");

  if (!alternateFieldName) {
    return null;
  }

  return form.querySelector(`[name="${alternateFieldName}"]`);
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
    // Skip fields that might not be rendered yet
    if (!field) return true;
    const alternateField = getAlternateField(form, field)
    return _verifyFieldValue(form, field) || (alternateField && _verifyFieldValue(form, alternateField));
  });
}

/**
 * Verify if field value is valid according to the field type or attributes.
 *
 * @param {HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement} field - The field element to validate.
 * @param {HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement} form - Form used to verify radio groups.
 * @return {boolean} True if the field has a valid or non-empty value, otherwise false.
 */
function _verifyFieldValue(form, field) {
  if (field.type === "radio") {
    return !!form.querySelector(`input[type="radio"][name="${field.name}"]:checked`);
  }
  if (field.dataset.type === "radio-select") {
    return !!form.querySelector(`input[type="radio"][name="${field.dataset.name}"]:checked`);
  }
  if (field.type === "checkbox") return field.checked;
  if (field.tagName === "SELECT") return field.value !== "";
  if (field.tagName === "TEXTAREA") {
    return hasContent(field);
  }
  return field.value?.trim() !== "";
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
  const submitBtn = document.getElementById("submit-btn");
  const fieldsStatusList = document.getElementById("wjs-submission-form__fields-list");
  const form = fieldsStatusList.closest("form");

  fieldsStatusList.childNodes.forEach(fieldStatusItem => {
    const fields = JSON.parse(fieldStatusItem.dataset.fields).map(field => {
      return document.getElementById(field);
    });
    const filled = allFilled(form, fields);
    if (debug)
      console.log("Filled", fieldStatusItem, fields, filled);
    if (filled) {
      fieldStatusItem.classList.add("wjs-submission-form__label--filled");
      if (!fieldStatusItem.querySelector(".visually-hidden")) {
        const srOnlyFilledElement = document.createElement("span");
        srOnlyFilledElement.classList.add("visually-hidden");
        srOnlyFilledElement.textContent = "Done";
        fieldStatusItem.appendChild(srOnlyFilledElement);
      }
    } else {
      fieldStatusItem.classList.remove("wjs-submission-form__label--filled");
      const srOnlyFilledElement = fieldStatusItem.querySelector(".visually-hidden");
      if (srOnlyFilledElement) {
        fieldStatusItem.removeChild(srOnlyFilledElement);
      }
      allSectionsFilled = false;
    }
  });

  submitBtn.disabled = !allSectionsFilled;
}


/**
 * Retrieve the list of required fields from a given form element.
 * Filters out duplicate required radio groups to ensure only one entry for each group.
 *
 * This is meant to be called multiple times as it must be called any time the required status of a field changes to
 * ensure the required checklist is updated correctly.
 *
 * @param {HTMLFormElement} form - The form element to inspect for required fields.
 * @return {Array<Element>} The array of required field elements, with radio groups represented by a single element.
 */
function getRequiredFields(form) {
  const radios = new Set();

  // Use .filter() to create an array of required fields. This avoids including
  // `undefined` elements, which was the issue with the previous .map() implementation.
  return Array.from(form.querySelectorAll("[required]:not([required=\"false\"]),[js_required]")).filter(field => {
    // For radio buttons, we only want to include one field from each named group.
    if (field.type === "radio") {
      if (radios.has(field.name)) {
        return false; // Exclude this field as its group is already included.
      }
      radios.add(field.name);
    }
    return true; // Include all other required fields.
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
  if (formFooter) {
    formFooter.insertAdjacentElement("beforebegin", fieldsStatusList);
    populateRequiredChecklist(fieldsStatusList);
  }
}

/**
 * Adds a TinyMCE change event listener to a specified field's editor.
 * The event listener triggers an update to the required checklist.
 *
 * @param {Object} field The field object containing the editor's id.
 * @return {void}
 */
function addTinyMceListener(field) {
  // Guard against undefined/null field object to prevent runtime errors.
  if (!field || !field.id) {
    return;
  }

  const editor = tinymce.get(field.id);

  if (editor) {
    editor.on("change", function() {
      if (typeof updateRequiredChecklist === "function") {
        updateRequiredChecklist();
      }
    });
    editor.on("keyup", function() {
      if (typeof updateRequiredChecklist === "function") {
        updateRequiredChecklist();
      }
    });
  }
}

/**
 * Populates the checklist of required fields for a given form and attaches event listeners to ensure
 * the checklist updates dynamically upon changes.
 *
 * This is meant to be called multiple times as it must be called any time the required status of a field changes to
 * ensure the required checklist is updated correctly.
 *
 * @param {HTMLElement} fieldsStatusList - The DOM element representing the checklist container where required fields will be rendered.
 * @return {void} Does not return a value.
 */
function populateRequiredChecklist(fieldsStatusList) {
  const form = fieldsStatusList.closest("form");
  const sectionMap = new Map();

  getRequiredFields(form).forEach(field => {
    const section = getSectionHeading(field);
    const sectionTitle = section.textContent.trim();
    // if the section is invisible, we skip it as the field is not visible and user can't interact with it
    // if it's required and hidden, it's either populated programmatically or it will get a default at render time
    if (!section.parentElement.checkVisibility()) {
      // Remove item from the footer list of fields. Used when the field is hidden by HTMX actions
      if (sectionMap.has(sectionTitle)) {
        sectionMap.delete(sectionTitle);
      }
      return;

    }
    if (!sectionMap.has(sectionTitle)) {
      sectionMap.set(sectionTitle, []);
    }
    sectionMap.get(sectionTitle).push(field);
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
    let mappedFields = [];
    fields.forEach((field) => {
      const alternateField = getAlternateField(form, field);
      if (alternateField) {
        mappedFields.push(alternateField);
      }
      mappedFields.push(field);
    })
    attachEventListener(form, mappedFields);
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
    } else if (["text", "textarea"].includes(field.type)) {
      // we can validate text fields on each keystroke
      field.addEventListener("input", updateRequiredChecklist);
    } else {
      field.addEventListener("change", updateRequiredChecklist);
    }
  });
}
