/**
 * Updates the status of funding-related fields by enabling the "add-funding-btn".
 * @return {void} Does not return any value.
 */
function updateFundingFieldsStatus() {
  document.getElementById("add-funding-btn").disabled = false;
}

/**
 * Check the access mode based on the provided value and update the visibility of the message element.
 *
 * @param {string} value - The access mode value to check. If "1", the message element is shown; otherwise, it is hidden.
 * @return {void}
 */
function checkAccessMode(value) {
  if (accessModesWithDisclaimer.includes(value)) {
    document.getElementById("js-access-mode-message").classList.remove("d-none");
  } else {
    document.getElementById("js-access-mode-message").classList.add("d-none");
  }
}

/**
 * Set up event listeners for handling funding workflow.
 *
 * - when a typeahead input is triggered, the add funding button is enabled
 * - bind custom events triggered by HX-trigger HTMX header to open / close the modal according to the funders
 *    selection workflow
 * - clear the modal when closed content to prevent flickering when the modal is reopened with new content
 *
 * @return {void} Does not return a value.
 */
function setupFundingEvents() {
  document.addEventListener("typeahead:asyncreceive", function() {
    updateFundingFieldsStatus();
  });
  document.body.addEventListener("close-active-modal", function() {
    console.log("cl;ose 2")
    document.querySelector("#htmxModal").querySelector("[aria-label=Close]").click();
  });
  document.body.addEventListener("open-active-modal", function() {
    console.log("open")
    const htmxModal = new bootstrap.Modal(document.getElementById("htmxModal"));
    htmxModal.show();
  });
  const modal = document.getElementById("htmxModal");
  modal.addEventListener("hidden.bs.modal", function() {
    // this cleanup modal disposal issues
    document.getElementById("htmxModalContent").innerHTML = "";
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');
    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
  });
}

window.addEventListener("DOMContentLoaded", function() {
  setupFundingEvents();
  if (accessModeSelector) {
    checkAccessMode(accessModeSelector.value);
    accessModeSelector.addEventListener("change", function(event) {
      checkAccessMode(event.target.value);
    });
  }
});
