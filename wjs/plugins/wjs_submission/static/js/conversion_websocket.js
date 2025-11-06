/**
 * Displays feedback based on the provided data's status.
 * Updates the visual indicators such as message and status dot.
 *
 * @param {Object} data - The data object containing feedback information.
 * @param {string} data.status - The current status, which can be "success", "working", or "error".
 * @param {string} [data.status_log] - Optional log message associated with the "error" status.
 * @return {void} This function does not return a value.
 */
function show_feedback(data) {

  if (data.status) {
    const el = document.getElementById("conversion-status");
    const refresh = document.querySelector(".js-refresh");

    console.log("show_feedback", data);
    switch (data.status) {
      case "completed": {
        console.log("Status: completed");
        el.classList.remove("d-none");
        el.querySelector(".dot").className = "dot bg-success";
        el.querySelector(".content").className = "content text-success";
        el.querySelector(".content").textContent = "Success";
        setTimeout(() => {
          // refresh.click();
        }, 500);
        break;
      }
      case "running": {
        console.log("Status: running");
        el.classList.remove("d-none");
        el.querySelector(".dot").className = "dot bg-running";
        el.querySelector(".content").className = "content text-running";
        el.querySelector(".content").textContent = "Running";
        break;
      }
      case "error": {
        console.log("Status: error");
        el.classList.remove("d-none");
        el.querySelector(".dot").className = "dot bg-danger";
        el.querySelector(".content").className = "content text-danger";
        setTimeout(() => {
          refresh.click();
        }, 500);
        if (data.status_log) {
          const el = document.getElementById("conversion-message");
          const warningContainer = document.getElementById("js-conversion-message");
          if (el) el.textContent = data.status_log;
          if (el) el.textContent.length > 0 ? warningContainer.classList.remove("d-none") : warningContainer.classList.add("d-none");
        }
        break;
      }
    }
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
