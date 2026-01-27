/**
 * Toggle the visibility of a URL input field based on the specified value.
 *
 * @param {string} field - The identifier of the field to toggle.
 * @param {string} value - The value to check against; controls visibility of the URL input field.
 * @return {void}
 */
function urlSelectedCheck(field, value) {
  const fieldUrl = document.getElementById(`id_${field}_url`);
  const fieldUrlWrapper = fieldUrl.closest(".wjs-submission-form__form-label-wrapper");
  const fieldsStatusList = document.getElementById("wjs-submission-form__fields-list");
  console.log(fieldsStatusList);

  if (fieldUrlWrapper && value === "url") {
    fieldUrlWrapper.classList.remove("d-none");
    fieldUrl.setAttribute("required", "true");
  } else if (fieldUrlWrapper) {
    fieldUrlWrapper.classList.add("d-none");
    fieldUrl.removeAttribute("required");
  }
  populateRequiredChecklist(fieldsStatusList);
}
