/**
 * Displays feedback based on the provided data's status.
 * Updates the visual indicators such as message and status dot.
 *
 * When the status is set to completed, the refresh button is clicked to refresh (via HTMX) the file listing to provide
 * proper rendering of the newly converted file with correct link, filename and status, which are not available to
 * the websocket payload.
 *
 * @param {Object} data - The data object containing feedback information.
 * @param {string} data.status - The current status, which can be "success", "working", or "error".
 * @param {string} [data.status_log] - Optional log message associated with the "error" status.
 * @return {void} This function does not return a value.
 */
function show_feedback(data) {

  if (data.status) {
    const conversionStatusContainer = document.getElementById("conversion-status");
    const refresh = document.querySelector(".js-refresh");

    console.log("show_feedback", data);
    switch (data.status) {
      case "completed": {
        console.log("Status: completed");
        conversionStatusContainer.classList.remove("d-none");
        conversionStatusContainer.querySelector(".dot").className = "dot bg-success";
        conversionStatusContainer.querySelector(".content").className = "content text-success";
        conversionStatusContainer.querySelector(".content").textContent = "Success";
        setTimeout(() => {
          refresh.click();
        }, 500);
        break;
      }
      case "running": {
        console.log("Status: running");
        conversionStatusContainer.classList.remove("d-none");
        conversionStatusContainer.querySelector(".dot").className = "dot bg-running";
        conversionStatusContainer.querySelector(".content").className = "content text-running";
        conversionStatusContainer.querySelector(".content").textContent = "Running";
        break;
      }
      case "error": {
        console.log("Status: error");
        conversionStatusContainer.classList.remove("d-none");
        conversionStatusContainer.querySelector(".dot").className = "dot bg-danger";
        conversionStatusContainer.querySelector(".content").className = "content text-danger";
        conversionStatusContainer.querySelector(".content").textContent = "Error";
        if (data.status_log) {
          const convertedFile = document.querySelector(".js-converted-file");
          convertedFile.value = null;
          const conversionStatusMessage = document.getElementById("conversion-message");
          const warningContainer = document.getElementById("js-conversion-message");
          const conversionLogContainer = document.getElementById("js-conversion-log");
          const conversionLogContainerUrl = document.getElementById("js-conversion-log-url");
          if (conversionStatusMessage) conversionStatusMessage.textContent = data.status_log;
          if (conversionStatusMessage) conversionStatusMessage.textContent.length > 0 ? warningContainer.classList.remove("d-none") : warningContainer.classList.add("d-none");
          if (conversionLogContainer && data.log_file) {
            conversionLogContainer.classList.remove("d-none");
            conversionLogContainerUrl.href = data.log_file;
          }
        }
        break;
      }
    }
    updateRequiredChecklist();
  }
}


/**
 * Establish a WebSocket connection to the specified URL, handling connection events,
 * data reception, errors, and reconnection attempts.
 *
 * @param {string} url - The WebSocket server URL to connect to.
 * @return {void} Does not return a value.
 */
function conversion_websocket_connect(url) {
  console.log(`Feedback URL: ${url}`);
  const chatSocket = new WebSocket(url);

  chatSocket.onopen = () => console.log("WS connected");

  chatSocket.onmessage = function(e) {
    console.log("WS data", e.data);
    try {
      const data = JSON.parse(e.data);
      console.log("WS message", data);
      show_feedback(data);
    } catch (_) {
      console.warn("Malformed WS message", e.data);
    }
  };

  chatSocket.onerror = function(e) {
    // FIXME: Report message to user
    console.error("WS error", e);
  };

  chatSocket.onclose = function(e) {
    console.warn("WS closed, attempting reconnect in 3s", e);
    setTimeout(() => {
      conversion_websocket_connect(url);
    }, 3000);
  };
}
