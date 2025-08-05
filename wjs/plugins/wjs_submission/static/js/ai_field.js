/**
 * Handles the toggle functionality for the "Use of AI" input field by replacing it with a custom Bootstrap switch.
 * The method hides the original input and label, creates a styled toggle switch, and synchronizes its state with the hidden input.
 *
 * @return {void} This method does not return a value.
 */
function handleUseAiToggle() {
  // Find the input field by name
  const aiInput = document.querySelector("input[name=\"Use of AI\"]");
  const aiLabel = document.querySelector(`label[for="${aiInput.id}"]`);

  aiInput.setAttribute("aria-hidden", "true");
  aiInput.classList.add("d-none");
  aiLabel.setAttribute("aria-hidden", "true");
  aiLabel.classList.add("d-none");

  // Create the Bootstrap switch
  const switchAI = document.createElement("div");
  switchAI.className = "form-check form-switch mb-2";

  const switchAIInput = document.createElement("input");
  switchAIInput.className = "form-check-input";
  switchAIInput.type = "checkbox";
  switchAIInput.id = "ai-switch-checkbox";
  switchAIInput.setAttribute("role", "switch");

  const switchLabel = document.createElement("label");
  switchLabel.className = "form-check-label";
  switchLabel.setAttribute("for", switchAIInput.id);
  switchLabel.textContent = "Use of AI";

  switchAI.appendChild(switchAIInput);
  switchAI.appendChild(switchLabel);

  // Insert the switch before the label
  aiLabel.parentNode.insertBefore(switchAI, aiLabel);

  // Toggle input visibility when switch is toggled
  switchAIInput.addEventListener("change", function() {
    aiInput.checked = this.checked;
    if (this.checked) {
      aiInput.classList.remove("d-none");
    } else {
      aiInput.classList.add("d-none");
    }
  });

  if (aiInput.value) {
    switchAIInput.checked = true;
    aiInput.classList.remove("d-none");
  } else {
    switchAIInput.checked = false;
    aiInput.classList.add("d-none");
  }
}
