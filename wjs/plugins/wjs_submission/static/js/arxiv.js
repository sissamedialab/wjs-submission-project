/**
 * Sets up the validation logic for the arXiv ID input field and related elements on the submission form.
 * Handles input validation, suggestion visibility, button enabling/disabling based on input validity,
 * and response processing from a back-end service related to arXiv ID validation.
 *
 * @return {void} This method doesn't return a value; it sets up event listeners and modifies the DOM as necessary.
 */
function setupArxivValidation() {
  console.log("setupArxivValidation");
  const fieldsStatusListItem = Array.from(document.querySelectorAll("li[data-section]")).find(li =>
    li.dataset.section.toLowerCase().includes("arxiv"),
  );
  const arxivInput = document.getElementById("arxiv-id-input");
  const resultDiv = document.getElementById("js-arxiv-validation-result");
  const suggestionDiv = document.getElementById("js-arxiv-validation-suggestion");
  const arxivValidationBtn = document.getElementById("js-arxiv-validation-btn");
  const loaderDiv = document.getElementById("js-arxiv-validation-loader");

  const arxivInputWrapper = arxivInput.closest(".wjs-submission-form__arxiv-validation-wrapper");
  const resultDivWrapper = resultDiv.closest(".wjs-submission-form__arxiv-validation-messages-wrapper");

  arxivInputWrapper.parentNode.insertBefore(suggestionDiv, resultDivWrapper);

  arxivInput.addEventListener("input", function() {
    const regex = /^\d{4}\.\d{5}$/;
    const isValid = regex.test(arxivInput.value);
    console.log(isValid);
    suggestionDiv.classList.toggle("d-none", arxivInput.value === "" || isValid);
    arxivValidationBtn.disabled = !isValid;
  });

  arxivInput.addEventListener("keydown", function(event) {
    if (event.key === "Enter" && !arxivValidationBtn.disabled) {
      event.preventDefault(); // Prevent form submission if inside a form
      arxivValidationBtn.click();
    }
  });

  arxivValidationBtn.addEventListener("click", function() {
    loaderDiv.classList.remove("d-none");
    resultDiv.classList.add("d-none");
  });

  document.addEventListener("htmx:afterRequest", function(event) {
    loaderDiv.classList.add("d-none");
    resultDiv.classList.remove("d-none");

    const responseData = JSON.parse(event.detail.xhr.response);
    const isSuccess = responseData.status === "success";

    if (fieldsStatusListItem) {
      fieldsStatusListItem.classList.toggle("wjs-submission-form__label--filled", isSuccess);
    }

    resultDiv.classList.toggle("wjs-submission-form__arxiv-validation-result--success", isSuccess);
    resultDiv.classList.toggle("wjs-submission-form__arxiv-validation-result--error", !isSuccess);

    const iconHtml = isSuccess
      ? "<i class=\"bi bi-check-circle-fill\"></i>"
      : "<i class=\"bi bi-exclamation-triangle-fill\"></i>";

    resultDiv.innerHTML = `${iconHtml} ${responseData.message}`;

    resultDiv.focus();

    // Funtion to update hidden input with arxiv validation processing request

    if (!event.detail.elt || event.detail.elt.id !== arxivValidationBtn.id) return;

    let responseText = event.detail.xhr.responseText;
    let res;
    try {
      res = JSON.parse(responseText);
    } catch (err) {
      console.error("Invalid JSON from arXiv microservice:", err, responseText);
      return;
    }

    if (res.status === "success") {
      const hidden = document.getElementById("arxiv-article-id-input");
      hidden.value = res.article_id;
    } else {
      console.log("Error fetching article: " + res.message);
    }
  });
}
