
function updateFundingFieldsStatus() {
  document.getElementById("add-funding-btn").disabled = false;
}

function setupFundingSelection() {
  document.addEventListener("typeahead:asyncreceive", function() {
    updateFundingFieldsStatus();
  });
}
