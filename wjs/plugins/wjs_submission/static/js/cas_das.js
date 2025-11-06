/**
 * Toggle the visibility of a URL input field based on the specified value.
 *
 * @param {string} field - The identifier of the field to toggle.
 * @param {string} value - The value to check against; controls visibility of the URL input field.
 * @return {void}
 */
function urlSelectedCheck(field, value) {
  const fieldUrl = document.getElementById(`id_${field}_url`).closest(".wjs-submission-form__form-label-wrapper");

  if (fieldUrl && value === "url") {
    fieldUrl.classList.remove("d-none");
  } else if (fieldUrl) {
    fieldUrl.classList.add("d-none");
  }
}
