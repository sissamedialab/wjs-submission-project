/**
 * Updates the visibility and required status of collaboration-related fields based on the provided value.
 * Toggles classes and triggers updates to a required fields checklist if necessary.
 *
 * @param {string} field - The identifier of the field being updated.
 * @param {string} value - The new value of the field, used to determine visibility and requirements.
 * @return {void} Does not return a value.
 */
function updateCollaborationFieldsStatus(field, value) {
  const orderField = document.getElementById("collaborations-order");
  const typeAheadField = document.getElementById("id_collaboration");
  const addCollaborationButton = document.getElementById("add-collab-btn");
  const isOrderFieldRequired = orderField.required;
  const istypeAheadFieldRequired = typeAheadField ? typeAheadField.required : false;
  let triggerPopulate = false;

  [
    document.getElementById("js-collaborations-search-wrapper"),
    document.getElementById("selected-collaborations-wrapper"),
  ].forEach(searchField => {
    if (searchField && value === "none") {
      searchField.classList.add("d-none");
      orderField.required = false;
      if (typeAheadField)
        typeAheadField.required = false;
      // as fields were previously required, we trigger a refresh of the required fields checklist to ensure
      // detect_required works
      triggerPopulate = isOrderFieldRequired || istypeAheadFieldRequired;
      addCollaborationButton.disabled = true;
    } else if (searchField) {
      searchField.classList.remove("d-none");
      orderField.required = true;
      triggerPopulate = (orderField.required !== isOrderFieldRequired);
      // Button is disabled by default ensuring the relation type is selected because it's required to submit
      // collaboration adding form
      addCollaborationButton.disabled = !value;
    }
  });
  if (triggerPopulate) {
    populateRequiredChecklist(document.querySelector("#wjs-submission-form__fields-list"));
  }
}


/**
 * Configures the selection functionality for collaboration options.
 * Sets up event listeners for collaboration-related input fields and updates the status of associated fields based on the selected option.
 *
 * @return {void} Does not return a value.
 */
function setupCollaborationsSelection() {
  updateCollaborationFieldsStatus("collaboration_relation", document.querySelector("input[name=collaboration_relation]:checked")?.value);
  document.querySelectorAll("input[name=collaboration_relation]").forEach((button) => {
    button.addEventListener("change", function(event) {
      updateCollaborationFieldsStatus("collaboration_relation", event.target.value);
    });
  });
}
