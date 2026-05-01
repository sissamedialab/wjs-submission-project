/**
 * Toggles the visibility of the "authors contributions" section based on the provided triggers.
 *
 * If HTMX view provides "update-fragment:1" trigger in HX-Trigger header and authors-contributions-wrapper element
 * is available, display it via css, mark the textarea as required with custom attribute on the field and refresh the
 * list of required fields.
 *
 * @param {string} triggers - A comma-separated string of triggers. Each trigger can include visibility information
 *                            for the "authors contributions" section, in the format "update-fragment:1" to show or
 *                            "update-fragment:0" to hide it.
 * @return {void} No return value.
 */
function toggleAuthorsContributionsVisibility(triggers) {
  triggers.split(",").forEach(trigger => {
    if (trigger.startsWith("update-fragment:")) {
      const show = trigger.split(":")[1] === "1";
      const el = document.querySelector("#authors-contributions-wrapper");
      if (el) {
        if (show) {
          el.style.display = "";
          document.querySelector("#id_authors_contributions").setAttribute("js_required", "true");
        } else {
          el.style.display = "none";
          document.querySelector("#id_authors_contributions").removeAttribute("js_required");
        }
      }
      populateRequiredChecklist(document.querySelector("#wjs-submission-form__fields-list"));
    }
  });
}

/**
 * Sets up the author selection process by adding an event listener
 * to monitor the "typeahead:asyncreceive" event and trigger the
 * necessary updates to author fields.
 *
 * @return {void} No return value.
 */
function setupAuthorSelection() {
  document.addEventListener("typeahead:asyncreceive", function() {
    updateAuthorFieldsStatus();
  });
}

/**
 * Enable the "add-author-btn" button when a search is initiated.
 *
 * @return {void} Does not return a value.
 */
function updateAuthorFieldsStatus() {
  document.getElementById("add-author-btn").disabled = false;
}

document.body.addEventListener("htmx:afterRequest", e => {
  const triggers = e.detail?.xhr?.getResponseHeader("HX-Trigger");
  if (!triggers) return;
  toggleAuthorsContributionsVisibility(triggers);
});
