function updateFundingFieldsStatus() {
  document.getElementById("add-funding-btn").disabled = false;
}

function setupFundingSelection() {
  document.addEventListener("typeahead:asyncreceive", function() {
    updateFundingFieldsStatus();
  });
}

function checkAccessMode(value) {
  if (value === "1") {
    document.getElementById("js-access-mode-message").classList.remove("d-none");
  } else {
    document.getElementById("js-access-mode-message").classList.add("d-none");
  }
}
document.addEventListener("DOMContentLoaded", function() {
  if (accessModeSelector) {
    checkAccessMode(accessModeSelector.value);
    accessModeSelector.addEventListener("change", function(event) {
      checkAccessMode(event.target.value);
    });
  }
});

window.addEventListener("DOMContentLoaded", function() {
  document.body.addEventListener("close-active-modal", function() {
    document.querySelector("#htmxModal").querySelector("[aria-label=Close]").click();
  });
  document.body.addEventListener("open-active-modal", function() {
    const htmxModal = new bootstrap.Modal(document.getElementById('htmxModal'))
    htmxModal.show()
  });
});

document.addEventListener("DOMContentLoaded", function() {
  const modal = document.getElementById("htmxModal");
  modal.addEventListener("hidden.bs.modal", function() {
    document.getElementById("htmxModalContent").innerHTML = "";
  });
});


document.addEventListener("DOMContentLoaded", function() {
  setupFundingSelection();
});
