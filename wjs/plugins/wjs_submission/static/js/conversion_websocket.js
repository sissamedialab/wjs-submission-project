/**
 * Maps result values to appropriate CSS class suffixes for styling.
 *
 * @param {string} result - The result value from the WebSocket message ("debug", "info", "warning", "error").
 * @return {string} The CSS class suffix to use for styling (e.g., "success", "info", "warning", "danger").
 */
function get_result_class(result) {
  const resultClassMap = {
    debug: "info",
    info: "info",
    warning: "warning",
    error: "danger",
    failed: "danger"
  };
  return resultClassMap[result] || "info";
}


/**
 * Displays the conversion log URL if available.
 *
 * @param {Object} data - The data object containing feedback information.
 * @return {void} This function does not return a value.
 */
function show_feedback_log(data) {
  const warningContainer = document.getElementById("js-conversion-message");
  const conversionStatusMessage = document.getElementById("conversion-message");
  const conversionLogContainer = document.getElementById("js-conversion-log");
  const conversionLogContainerUrl = document.getElementById("js-conversion-log-url");

  if (data.log_url && conversionLogContainer && conversionLogContainerUrl) {
    conversionLogContainerUrl.href = data.log_url;
    conversionLogContainer.classList.remove("d-none");
  }

  // Append warning or error messages while running
  if ((data.result === "warning" || data.result === "error") && data.status_log) {
    if (conversionStatusMessage && warningContainer) {
      if (conversionStatusMessage.innerHTML) {
        conversionStatusMessage.innerHTML += "<br>";
      }
      conversionStatusMessage.innerHTML += data.status_log;
      warningContainer.classList.remove("d-none");
    }
  }

}


/**
 * Displays feedback based on the provided data's status and result.
 * Updates the visual indicators such as message and status dot.
 *
 * When the status is "completed", the refresh button is clicked to refresh (via HTMX) the file listing to provide
 * proper rendering of the newly converted file with correct link, filename and status, which are not available to
 * the websocket payload.
 *
 * When the status is "running" and result is "warning" or "error", appends status_log messages to the conversion
 * message container.
 *
 * @param {Object} data - The data object containing feedback information.
 * @param {string} data.status - The current status, which can be "running", "completed", or "failed".
 * @param {string} data.result - The result level, which can be "debug", "info", "warning", or "error".
 * @param {string} [data.status_log] - Optional log message to display.
 * @param {WebSocket} chatSocket - The websocket
 * @return {void} This function does not return a value.
 */
function show_feedback(data, chatSocket) {
  if (!data.status) {
    return;
  }

  const conversionStatusContainer = document.getElementById("conversion-status");
  const refresh = document.querySelector(".js-refresh");

  console.log("show_feedback", data);

  switch (data.status) {
    case "completed":
    case "failed": {
      console.log(`Status: ${data.status}`);
      const resultClass = get_result_class(data.result);

      conversionStatusContainer.classList.remove("d-none");
      conversionStatusContainer.querySelector(".dot").className = `dot bg-${resultClass}`;
      conversionStatusContainer.querySelector(".content").className = `content text-${resultClass} text-capitalize`;
      conversionStatusContainer.querySelector(".content").textContent = data.status_log || "";

      // Refresh the file listing on completion
      if (data.status === "completed") {
        setTimeout(() => {
          refresh.click();
        }, 500);
      }

      // Disconnect the WS
      // Since message can arrive from two sources
      // (from Yakunin: the conversion process feedback messages; from WJS: when the logic completes handling of the converted files)
      // there is no guarantee that they reach us in the same order that they were generated;
      // it's possible that a "feedback" message reaches us after a "completed" messages,
      // so we disconnect after a "completed" message:
      chatSocket.close()
      break;
    }
    case "running": {
      console.log("Status: running");
      conversionStatusContainer.classList.remove("d-none");
      conversionStatusContainer.querySelector(".dot").className = "dot bg-running";
      conversionStatusContainer.querySelector(".content").className = "content text-running text-capitalize";
      conversionStatusContainer.querySelector(".content").textContent = "running";
      break;
    }
  }

  show_feedback_log(data);
  updateRequiredChecklist();
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
  if (!url){
    console.log("No url, quitting here!")
    return;
  }
  if (url==="None"){
    console.log("Url is 'None'??? Probable programming error. Quitting here!")
    return;
  }
  const chatSocket = new WebSocket(url);
  chatSocket.onopen = () => console.log("WS connected");

  chatSocket.onmessage = function(e) {
    console.log("WS event", e);
    try {
      const data = JSON.parse(e.data);
      console.log("WS message", data);
      show_feedback(data, chatSocket);
    } catch (_) {
      console.warn("Malformed WS message", e.data);
    }
  };

  chatSocket.onerror = function(e) {
    // FIXME: Report message to user
    console.error("WS error", e);
  };

  chatSocket.onclose = function(e) {
    console.warn("WS closed.", e);
  };
}
