document.addEventListener("DOMContentLoaded", function () {
  const toggleBtn = document.getElementById("toggleAllAccordions");
  let expanded = false;

  if (toggleBtn) {
    toggleBtn.addEventListener("click", function () {
      const buttons = document.querySelectorAll(
        '.accordion-button[type="button"][data-bs-toggle="collapse"]'
      );
      buttons.forEach(function (btn) {
        const target = document.querySelector(
          btn.getAttribute("data-bs-target")
        );
        if (!expanded) {
          btn.classList.remove("collapsed");
          btn.setAttribute("aria-expanded", "true");
          if (target && !target.classList.contains("show")) {
            target.classList.add("show");
          }
        } else {
          btn.classList.add("collapsed");
          btn.setAttribute("aria-expanded", "false");
          if (target && target.classList.contains("show")) {
            target.classList.remove("show");
          }
        }
      });
      expanded = !expanded;
      toggleBtn.textContent = expanded ? "Close All" : "Open  All";
    });
  }

  function updateKeywordSelectionState() {
    const keywordCheckboxes = document.querySelectorAll('input[type="checkbox"][name="keyword"]');
    const submitBtn = document.querySelector('button[type="submit"]');

    const checkedCount = Array.from(keywordCheckboxes).filter((cb) => cb.checked).length;
    const hiddenCbChecked = document.getElementById("js-keywords-hidden-required");

    if (checkedCount < 2 || checkedCount > 4) {
      if (submitBtn) submitBtn.disabled = true;
      if (hiddenCbChecked) {
        hiddenCbChecked.checked = false;
        hiddenCbChecked.dispatchEvent(new Event("change", { bubbles: true }));
      }
    } else {
      if (submitBtn) submitBtn.disabled = false;
      if (hiddenCbChecked) {
        hiddenCbChecked.checked = true;
        hiddenCbChecked.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
  }

  document.addEventListener("change", function (event) {
    if (event.target.matches('input[type="checkbox"][name="keyword"]')) {
      updateKeywordSelectionState();
    }
  });

  updateKeywordSelectionState();
});
