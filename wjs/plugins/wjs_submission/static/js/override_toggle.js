// Dynamically enable/disable the license and copyright fields based on the
// corresponding override checkbox.  When the checkbox is unchecked, the field
// is disabled (read-only); when checked, it becomes editable.
document.addEventListener("DOMContentLoaded", function () {
  const licenseCheckbox = document.getElementById("id_license_override");
  const licenseField = document.getElementById("id_article_license");
  const rightsCheckbox = document.getElementById("id_rights_override");
  const rightsField = document.getElementById("id_article_rights");

  if (licenseCheckbox && licenseField) {
    function updateLicense() {
      licenseField.disabled = !licenseCheckbox.checked;
    }
    licenseCheckbox.addEventListener("change", updateLicense);
    updateLicense();
  }

  if (rightsCheckbox && rightsField) {
    function updateRights() {
      rightsField.disabled = !rightsCheckbox.checked;
    }
    rightsCheckbox.addEventListener("change", updateRights);
    updateRights();
  }
});
