document.addEventListener("DOMContentLoaded", function () {
  const toggleBtn = document.getElementById("toggleAllAccordions");

  if (toggleBtn) {
    const accordionContainer = document.getElementById("groupAccordion");

    function getAccordionState() {
      if (!accordionContainer) return {buttons: [], allExpanded: false};
      const buttons = accordionContainer.querySelectorAll('.accordion-button[type="button"][data-bs-toggle="collapse"]');
      const allExpanded = buttons.length > 0 && Array.from(buttons).every(btn => btn.getAttribute('aria-expanded') === 'true');
      return {buttons, allExpanded};
    }

    function updateToggleAllButtonState() {
      const {allExpanded} = getAccordionState();
      toggleBtn.setAttribute('aria-expanded', allExpanded);
      toggleBtn.textContent = allExpanded ? "Close All" : "Open All";
    }

    toggleBtn.addEventListener("click", function () {
      const {buttons, allExpanded} = getAccordionState();
      buttons.forEach(function (btn) {
        const target = document.querySelector(btn.getAttribute("data-bs-target"));
        if (target) {
          const instance = bootstrap.Collapse.getOrCreateInstance(target);
          allExpanded ? instance.hide() : instance.show();
        }
      });
    });

    if (accordionContainer) {
      accordionContainer.addEventListener('shown.bs.collapse', updateToggleAllButtonState);
      accordionContainer.addEventListener('hidden.bs.collapse', updateToggleAllButtonState);
      updateToggleAllButtonState();
    }
  }

  function updateKeywordSelectionState() {
    const keywordCheckboxes = document.querySelectorAll('input[type="checkbox"][name="keywords"], input[type="checkbox"][name="keyword"]');
    const submitBtn = document.querySelector('button[type="submit"]');

    const checkedCount = Array.from(keywordCheckboxes).filter((cb) => cb.checked).length;
    const hiddenCbChecked = document.getElementById("js-keywords-hidden-required");

    const freeKeywordsSection = document.getElementById("js-free-keyword-section");
    if (freeKeywordsSection && HIDE_FREE_KEYWORDS) {
      if (checkedCount >= MIN_KEYWORDS_COUNT) {
        freeKeywordsSection.classList.remove('d-none');
      } else {
        freeKeywordsSection.classList.add('d-none');
      }
    }
    if (checkedCount < MIN_KEYWORDS_COUNT || checkedCount > MAX_KEYWORDS_COUNT) {
      if (submitBtn) submitBtn.disabled = true;
      if (hiddenCbChecked) {
        hiddenCbChecked.checked = false;
        hiddenCbChecked.dispatchEvent(new Event("change", {bubbles: true}));
      }
    } else {
      if (submitBtn) submitBtn.disabled = false;
      if (hiddenCbChecked) {
        hiddenCbChecked.checked = true;
        hiddenCbChecked.dispatchEvent(new Event("change", {bubbles: true}));
      }
    }
  }

  /**
   * When four keywords are checked, remaining unchecked boxes are disabled.
   */
  function disableCbMaxSelected() {
    const keywordCheckboxes = document.querySelectorAll('input[type="checkbox"][name="keywords"], input[type="checkbox"][name="keyword"]');
    const checkedCount = Array.from(keywordCheckboxes).filter(cb => cb.checked).length;
    const disable = checkedCount >= MAX_KEYWORDS_COUNT;

    keywordCheckboxes.forEach(cb => {
      if (!cb.checked) {
        cb.disabled = disable;
      } else {
        cb.disabled = false;
      }
    });
  }

  /**
   * Validates keyword weights: js-keywords-weight-hidden-required
   * is checked ONLY if all .wjs-submission-form__keyword-weight-item-weights groups
   * have one radio checked.
   */
  function updateKeywordWeightSelectionState() {
    const weightsContainers = document.querySelectorAll('.wjs-submission-form__keyword-weight-item-weights');
    let allHaveChecked = true;
    weightsContainers.forEach(container => {
      const checkedRadio = container.querySelector('input[type="radio"]:checked');
      if (!checkedRadio) {
        allHaveChecked = false;
      }
    });
    const containersCount = weightsContainers.length;

    const isValid = containersCount > 0 && allHaveChecked;

    const hiddenCbChecked = document.getElementById("js-keywords-weight-hidden-required");
    if (hiddenCbChecked) {
      hiddenCbChecked.checked = isValid;
      hiddenCbChecked.dispatchEvent(new Event("change", {bubbles: true}));
    }
  }

  function addKeywordWeightList() {
    let initialKeywordWeights = {};
    const jsonScript = document.getElementById("initial-keyword-weights");
    if (jsonScript) {
      try {
        initialKeywordWeights = JSON.parse(jsonScript.textContent);
      } catch (e) {
        console.warn("Failed to parse initial keyword weights", e);
      }
    }

    const keywordWeightListContainer = document.querySelector('.wjs-submission-form__keywords-weight-container');
    if (!keywordWeightListContainer) return;

    const weightInfo = document.querySelector('.wjs-submission-form__keywords-weight-info');

    const prevSelectedWeights = {};
    const prevWeightContainers = document.querySelectorAll('.wjs-submission-form__keyword-weight-item-weights');
    prevWeightContainers.forEach(container => {
      const checkedRadio = container.querySelector('input[type="radio"]:checked');
      if (checkedRadio) {
        prevSelectedWeights[checkedRadio.name] = checkedRadio.value;
      }
    });

    keywordWeightListContainer.innerHTML = "";

    const selectedCheckboxes = Array.from(
      document.querySelectorAll('input[type="checkbox"][name="keyword"]:checked')
    );

    if (selectedCheckboxes.length === 0) {
      if (weightInfo) weightInfo.classList.add('d-none');
      updateKeywordWeightSelectionState();
      return;
    }

    if (weightInfo) weightInfo.classList.remove('d-none');

    selectedCheckboxes.forEach(function (checkbox) {

      let labelText = checkbox.dataset.label || "";
      if (!labelText) {
        const label = document.querySelector(`label[for="${checkbox.id}"]`);
        labelText = label ? label.textContent.trim() : checkbox.value;
      }

      const keywordDiv = document.createElement('div');
      keywordDiv.className = 'wjs-submission-form__keyword-weight-item';

      const labelDiv = document.createElement('div');
      labelDiv.className = 'wjs-submission-form__keyword-weight-label';
      labelDiv.textContent = labelText;
      keywordDiv.appendChild(labelDiv);

      const keywordWeightsform = document.createElement('div');
      keywordWeightsform.className = 'wjs-submission-form__keyword-weight-item-weights';

      const keywordWeights = [25, 50, 75, 100];
      const radioName = `keyword_${checkbox.value}_weight`;

      keywordWeights.forEach(weight => {
        const radioId = `keyword-weight-${checkbox.value}-${weight}`;

        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.className = 'form-check-input wjs-submission-form__keyword-weight-input';
        radio.name = radioName;
        radio.id = radioId;
        radio.value = weight;

        if ((prevSelectedWeights[radioName] && prevSelectedWeights[radioName] == String(weight)) ||
          (initialKeywordWeights[checkbox.value] && String(initialKeywordWeights[checkbox.value]) === String(weight))) {
          radio.checked = true;
        }

        const radioLabel = document.createElement('label');
        radioLabel.className = 'form-check-label wjs-submission-form__keyword-weight-input-label';
        radioLabel.htmlFor = radioId;
        radioLabel.textContent = weight;

        const radioDiv = document.createElement('div');
        radioDiv.className = 'form-check';
        radioDiv.appendChild(radio);
        radioDiv.appendChild(radioLabel);

        keywordWeightsform.appendChild(radioDiv);
      });

      keywordDiv.appendChild(keywordWeightsform);
      keywordWeightListContainer.appendChild(keywordDiv);
    });

    updateKeywordWeightSelectionState();
  }

  /**
   * Collects the selected radio weight value and name for each
   * .wjs-submission-form__keyword-weight-item-weights group.
   * Returns an object of name and value for the checked radios.
   */
  function collectSelectedKeywordWeights() {
    const keywordsWeights = document.querySelectorAll('.wjs-submission-form__keyword-weight-item-weights');
    const results = {};

    keywordsWeights.forEach(container => {
      const checkedRadio = container.querySelector('input[type="radio"]:checked');
      if (checkedRadio) {
        results[checkedRadio.name] = checkedRadio.value;
      }
    });
    return results;
  }

  function openAccordionsWithCheckedKeywords() {
    const keywordCheckboxes = document.querySelectorAll('input[type="checkbox"][name="keyword"]:checked');

    keywordCheckboxes.forEach(checkbox => {
      const subgroupCollapse = checkbox.closest('.accordion-collapse');
      if (subgroupCollapse) {
        bootstrap.Collapse.getOrCreateInstance(subgroupCollapse, {toggle: false}).show();

        const subgroupButton = subgroupCollapse.previousElementSibling?.querySelector('.accordion-button');
        if (subgroupButton) {
          subgroupButton.classList.remove('collapsed');
          subgroupButton.setAttribute('aria-expanded', 'true');
        }

        const subgroupItem = subgroupCollapse.closest('.accordion-item');
        if (subgroupItem) {
          const parentCollapse = subgroupItem.closest('.accordion-collapse');
          if (parentCollapse) {
            bootstrap.Collapse.getOrCreateInstance(parentCollapse, {toggle: false}).show();
            const parentButton = parentCollapse.previousElementSibling?.querySelector('.accordion-button');
            if (parentButton) {
              parentButton.classList.remove('collapsed');
              parentButton.setAttribute('aria-expanded', 'true');
            }
          }
        }
      }
    });
  }

  document.addEventListener("change", function (event) {
    if (event.target.matches('input[type="checkbox"][name="keyword"]')) {
      updateKeywordSelectionState();
      disableCbMaxSelected();
      addKeywordWeightList();
    }
    if (event.target.matches('input[type="checkbox"][name="keywords"]')) {
      updateKeywordSelectionState();
      disableCbMaxSelected();
    }

    if (event.target.matches('.wjs-submission-form__keyword-weight-item input[type="radio"]') ||
      event.target.closest('.wjs-submission-form__keyword-weight-item')) {
      updateKeywordWeightSelectionState();
    }
  });

  updateKeywordSelectionState();
  disableCbMaxSelected();
  addKeywordWeightList();
  openAccordionsWithCheckedKeywords();
});
