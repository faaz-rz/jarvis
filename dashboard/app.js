(() => {
  "use strict";

  const elements = {
    modelPill: document.getElementById("model-pill"),
    toolPill: document.getElementById("tool-pill"),
    clock: document.getElementById("clock"),
    stateLabel: document.getElementById("state-label"),
    coreState: document.getElementById("core-state"),
    core: document.getElementById("jarvis-core"),
    canvas: document.getElementById("brain-canvas"),
    connections: document.getElementById("connections"),
    taskHeading: document.getElementById("task-heading"),
    taskCopy: document.getElementById("task-copy"),
    taskSteps: document.getElementById("task-steps"),
    steps: Array.from(document.querySelectorAll("#task-steps li")),
    missionPanel: document.getElementById("mission-panel"),
    missionTitle: document.getElementById("mission-title"),
    missionStatus: document.getElementById("mission-status"),
    missionSummary: document.getElementById("mission-summary"),
    missionSteps: document.getElementById("mission-steps"),
    missionButton: document.getElementById("mission-button"),
    missionPause: document.getElementById("mission-pause"),
    missionResume: document.getElementById("mission-resume"),
    missionCancel: document.getElementById("mission-cancel"),
    missionDialog: document.getElementById("mission-dialog"),
    missionForm: document.getElementById("mission-form"),
    missionGoal: document.getElementById("mission-goal"),
    missionClose: document.getElementById("mission-close"),
    activityList: document.getElementById("activity-list"),
    conversationList: document.getElementById("conversation-list"),
    inspector: document.getElementById("capability-inspector"),
    form: document.getElementById("message-form"),
    input: document.getElementById("message-input"),
    stopButton: document.getElementById("stop-button"),
    voiceButton: document.getElementById("voice-button"),
    shutdownButton: document.getElementById("shutdown-button"),
    clearActivity: document.getElementById("clear-activity"),
    permissionDialog: document.getElementById("permission-dialog"),
    permissionCopy: document.getElementById("permission-copy"),
    allowButton: document.getElementById("allow-button"),
    denyButton: document.getElementById("deny-button"),
    toast: document.getElementById("toast"),
  };

  const capabilityDetails = {
    voice: ["Voice", "Local listening, wake-word input, and speech output."],
    vision: ["Vision", "Qwen screen understanding with OCR fallback."],
    research: ["Research", "Web search, browsing, and sourced synthesis."],
    desktop: ["Applications", "Launch approved desktop applications and websites."],
    system: ["System", "Battery, volume, screenshots, and protected power controls."],
    files: ["Files", "Create files and folders inside the permitted workspace."],
    memory: ["Memory", "Recall conversations, preferences, and learned facts."],
    code: ["Code", "Generate, save, test, and debug Python code."],
  };

  const eventTypes = [
    "connected",
    "system_configured",
    "system_online",
    "system_shutdown",
    "message",
    "stream_start",
    "stream_chunk",
    "stream_end",
    "brain_state",
    "request_received",
    "learned_command_resolved",
    "memory_search_started",
    "memory_recalled",
    "model_queued",
    "model_started",
    "model_finished",
    "tool_started",
    "tool_finished",
    "permission_required",
    "permission_resolved",
    "skill_used",
    "task_completed",
    "task_cancelled",
    "generation_cancel_requested",
    "mission_planning",
    "mission_created",
    "mission_updated",
    "mission_step_started",
    "mission_step_completed",
    "mission_paused",
    "mission_resumed",
    "mission_cancelled",
    "mission_completed",
    "mission_failed",
    "speech_started",
    "speech_finished",
    "voice_state",
  ];

  let sessionToken = "";
  let eventSource = null;
  let streamMessage = null;
  let voiceEnabled = false;
  let stateVersion = 0;
  let toastTimer = null;
  let activeCapability = null;
  let activeMission = null;

  function formatTime(timestamp = Date.now() / 1000) {
    return new Intl.DateTimeFormat([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(timestamp * 1000));
  }

  function humanize(value) {
    return String(value || "")
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function showToast(message) {
    elements.toast.textContent = message;
    elements.toast.classList.add("visible");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      elements.toast.classList.remove("visible");
    }, 2800);
  }

  function emptyPlaceholder(container, copy) {
    container.replaceChildren();
    const paragraph = document.createElement("p");
    paragraph.className = "empty-state";
    paragraph.textContent = copy;
    container.append(paragraph);
  }

  function appendMessage(message) {
    const existingEmpty = elements.conversationList.querySelector(".empty-state");
    if (existingEmpty) {
      existingEmpty.remove();
    }
    const article = document.createElement("article");
    const sender = String(message.sender || "JARVIS");
    article.className = `message ${sender.toLowerCase() === "you" ? "user" : sender.toLowerCase() === "system" ? "system" : "assistant"}`;

    const header = document.createElement("header");
    const name = document.createElement("strong");
    name.textContent = sender === "You" ? "You" : sender;
    const time = document.createElement("time");
    time.textContent = formatTime(message.timestamp);
    header.append(name, time);

    const text = document.createElement("p");
    text.textContent = message.text || "";
    article.append(header, text);
    elements.conversationList.append(article);
    elements.conversationList.scrollTop = elements.conversationList.scrollHeight;

    while (elements.conversationList.children.length > 80) {
      elements.conversationList.firstElementChild.remove();
    }
    return { article, text };
  }

  function addActivity(title, detail = "", tone = "", timestamp) {
    const existingEmpty = elements.activityList.querySelector(".empty-state");
    if (existingEmpty) {
      existingEmpty.remove();
    }
    const item = document.createElement("article");
    item.className = `activity-item ${tone}`.trim();
    const dot = document.createElement("i");
    dot.setAttribute("aria-hidden", "true");
    const content = document.createElement("div");
    const heading = document.createElement("strong");
    heading.textContent = title;
    content.append(heading);
    if (detail) {
      const copy = document.createElement("span");
      copy.textContent = detail;
      content.append(copy);
    }
    const time = document.createElement("time");
    time.textContent = formatTime(timestamp);
    item.append(dot, content, time);
    elements.activityList.prepend(item);

    while (elements.activityList.children.length > 60) {
      elements.activityList.lastElementChild.remove();
    }
  }

  function setBrainState(state, label, capability = null) {
    stateVersion += 1;
    const currentVersion = stateVersion;
    const normalized = state || "idle";
    const displayLabel = label || humanize(normalized);
    elements.core.dataset.state = normalized;
    elements.stateLabel.textContent = displayLabel;
    elements.coreState.textContent = displayLabel.toUpperCase();
    activateCapability(capability);

    if (normalized === "complete") {
      window.setTimeout(() => {
        if (stateVersion === currentVersion) {
          setBrainState("idle", "Ready");
          resetSteps();
        }
      }, 2200);
    }
  }

  function resetSteps() {
    elements.steps.forEach((step) => {
      step.classList.remove("active", "complete");
    });
  }

  function updateSteps(activeName, completedNames = []) {
    elements.steps.forEach((step) => {
      const name = step.dataset.step;
      step.classList.toggle("active", name === activeName);
      step.classList.toggle("complete", completedNames.includes(name));
    });
  }

  function clearMissionView() {
    activeMission = null;
    elements.missionPanel.hidden = true;
    elements.taskSteps.hidden = false;
  }

  function renderMission(mission) {
    const activeStatuses = new Set([
      "planning",
      "running",
      "waiting_permission",
      "paused",
    ]);
    if (!mission || !activeStatuses.has(mission.status)) {
      clearMissionView();
      return;
    }

    activeMission = mission;
    elements.missionPanel.hidden = false;
    elements.taskSteps.hidden = true;
    elements.taskHeading.textContent = mission.title || "Super Mission";
    elements.taskCopy.textContent = mission.goal || "Executing a persistent goal.";
    elements.missionTitle.textContent = mission.title || "Super Mission";
    elements.missionStatus.textContent = humanize(mission.status);
    elements.missionSummary.textContent = mission.summary || mission.goal || "";
    elements.missionSteps.replaceChildren();

    (mission.steps || []).forEach((step, index) => {
      const item = document.createElement("li");
      const allowedStatuses = new Set([
        "pending",
        "running",
        "waiting_permission",
        "completed",
        "cancelled",
      ]);
      item.className = allowedStatuses.has(step.status) ? step.status : "pending";

      const marker = document.createElement("span");
      marker.className = "mission-step-index";
      marker.textContent = String(index + 1);

      const copy = document.createElement("div");
      copy.className = "mission-step-copy";
      const title = document.createElement("strong");
      title.textContent = step.title || `Step ${index + 1}`;
      const detail = document.createElement("span");
      detail.textContent = step.result || step.success_criteria || step.instruction || "";
      copy.append(title, detail);
      item.append(marker, copy);
      elements.missionSteps.append(item);
    });

    elements.missionPause.disabled = !["running", "waiting_permission"].includes(mission.status);
    elements.missionResume.disabled = mission.status !== "paused";
    elements.missionCancel.disabled = false;
  }

  function activateCapability(capability) {
    activeCapability = capability;
    document.querySelectorAll(".capability-node").forEach((node) => {
      node.classList.toggle("active", node.dataset.capability === capability);
    });
    drawConnections();
  }

  function capabilityForTool(tool) {
    const mapping = {
      analyze_screen: "vision",
      clear_long_term_memory: "memory",
      remember_fact: "memory",
      search_memory: "memory",
      create_file: "files",
      create_folder: "files",
      open_application: "desktop",
      open_website: "research",
      web_search: "research",
      research_web: "research",
      get_battery_status: "system",
      set_volume: "system",
      take_screenshot: "system",
      control_computer_power: "system",
    };
    return mapping[tool] || null;
  }

  function capabilityForSkill(skill) {
    const mapping = {
      Vision: "vision",
      Research: "research",
      Search: "research",
      AppControl: "desktop",
      SystemControl: "system",
      Automation: "files",
      SelfLearning: "memory",
      DevMode: "code",
      SmallTalk: null,
    };
    return mapping[skill] ?? null;
  }

  function drawConnections() {
    const context = elements.connections.getContext("2d");
    const canvasRect = elements.canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    elements.connections.width = Math.max(1, Math.round(canvasRect.width * ratio));
    elements.connections.height = Math.max(1, Math.round(canvasRect.height * ratio));
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, canvasRect.width, canvasRect.height);
    const coreRect = elements.core.getBoundingClientRect();
    const startX = coreRect.left + coreRect.width / 2 - canvasRect.left;
    const startY = coreRect.top + coreRect.height / 2 - canvasRect.top;

    document.querySelectorAll(".capability-node").forEach((node) => {
      const nodeRect = node.getBoundingClientRect();
      const endX = nodeRect.left + nodeRect.width / 2 - canvasRect.left;
      const endY = nodeRect.top + nodeRect.height / 2 - canvasRect.top;
      const active = node.dataset.capability === activeCapability;
      context.save();
      context.beginPath();
      context.moveTo(startX, startY);
      context.lineTo(endX, endY);
      context.lineWidth = active ? 2 : 1;
      context.strokeStyle = active
        ? "rgba(109, 231, 239, 0.9)"
        : "rgba(143, 124, 255, 0.18)";
      if (active) {
        context.shadowColor = "rgba(109, 231, 239, 0.75)";
        context.shadowBlur = 11;
      }
      context.stroke();
      context.beginPath();
      context.arc(endX, endY, active ? 3.5 : 2, 0, Math.PI * 2);
      context.fillStyle = active
        ? "rgba(109, 231, 239, 1)"
        : "rgba(143, 124, 255, 0.45)";
      context.fill();
      context.restore();
    });
  }

  function showPermission(confirmations) {
    elements.permissionCopy.replaceChildren();
    (confirmations.length ? confirmations : ["Review the requested action."]).forEach((confirmation) => {
      const paragraph = document.createElement("p");
      paragraph.textContent = confirmation;
      elements.permissionCopy.append(paragraph);
    });
    if (!elements.permissionDialog.open) {
      elements.permissionDialog.showModal();
    }
  }

  function closePermission() {
    if (elements.permissionDialog.open) {
      elements.permissionDialog.close();
    }
  }

  function activityForEvent(event) {
    const data = event.data || {};
    const definitions = {
      system_online: ["Dashboard connected", "Local control channel is ready.", "success"],
      request_received: ["Request received", data.text || "", "active"],
      learned_command_resolved: ["Learned command resolved", data.action || "", "active"],
      memory_search_started: ["Searching memory", "Looking for useful prior context.", "active"],
      memory_recalled: ["Memory search complete", `${data.count || 0} relevant items recalled.`, data.count ? "success" : ""],
      model_queued: ["Qwen engaged", "The central brain is preparing a response.", "active"],
      model_started: ["Planning next step", `Model turn ${data.step || 1}.`, "active"],
      tool_started: [`Using ${humanize(data.tool)}`, "A controlled capability is active.", "active"],
      tool_finished: [
        `${humanize(data.tool)} ${data.success ? "completed" : "failed"}`,
        data.result || "",
        data.success ? "success" : "error",
      ],
      permission_required: ["Permission required", "No protected action has run yet.", "warning"],
      permission_resolved: [
        data.allowed ? "Permission granted" : "Permission denied",
        (data.tools || []).map(humanize).join(", "),
        data.allowed ? "success" : "warning",
      ],
      skill_used: [`Used ${humanize(data.skill)}`, "Handled by a deterministic capability.", "active"],
      task_completed: ["Task complete", "JARVIS finished the current request.", "success"],
      task_cancelled: ["Task cancelled", "The current request stopped safely.", "warning"],
      generation_cancel_requested: ["Stopping response", "Cancellation was requested.", "warning"],
      mission_planning: ["Planning Super Mission", data.goal || "", "active"],
      mission_created: ["Super Mission created", data.mission?.title || "", "success"],
      mission_step_started: [
        "Mission step started",
        data.mission?.steps?.[data.position]?.title || "",
        "active",
      ],
      mission_step_completed: [
        "Mission step verified",
        data.mission?.steps?.[data.position]?.title || "",
        "success",
      ],
      mission_paused: ["Super Mission paused", data.reason || "", "warning"],
      mission_resumed: ["Super Mission resumed", data.mission?.title || "", "active"],
      mission_cancelled: ["Super Mission cancelled", data.mission?.title || "", "warning"],
      mission_completed: ["Super Mission complete", data.mission?.title || "", "success"],
      mission_failed: ["Super Mission failed", data.reason || "", "error"],
      speech_started: ["Speaking", "Voice output is active.", "active"],
      voice_state: [
        data.listening ? "Voice listening active" : "Voice listening paused",
        data.enabled ? "Local microphone state changed." : "Voice input is unavailable.",
        data.listening ? "success" : "",
      ],
      system_shutdown: ["Shutting down", "The local JARVIS session is ending.", "warning"],
    };
    return definitions[event.type] || null;
  }

  function handleEvent(event, initial = false) {
    const data = event.data || {};
    const activity = activityForEvent(event);
    if (activity) {
      addActivity(activity[0], activity[1], activity[2], event.timestamp);
    }

    switch (event.type) {
      case "message":
        appendMessage(data);
        break;
      case "stream_start":
        streamMessage = appendMessage({
          sender: data.sender || "JARVIS",
          text: "",
          timestamp: event.timestamp,
        });
        setBrainState("responding", "Responding");
        updateSteps("verify", ["understand", "recall", "select", "act"]);
        break;
      case "stream_chunk":
        if (streamMessage) {
          streamMessage.text.textContent += data.text || "";
          elements.conversationList.scrollTop = elements.conversationList.scrollHeight;
        }
        break;
      case "stream_end":
        streamMessage = null;
        break;
      case "brain_state":
        setBrainState(data.state, data.label);
        break;
      case "request_received":
        elements.taskHeading.textContent = "Understanding request";
        elements.taskCopy.textContent = data.text || "Processing your instruction.";
        setBrainState("understanding", "Understanding");
        updateSteps("understand");
        break;
      case "memory_search_started":
        setBrainState("recalling", "Recalling", "memory");
        updateSteps("recall", ["understand"]);
        break;
      case "memory_recalled":
        updateSteps("select", ["understand", "recall"]);
        break;
      case "model_queued":
      case "model_started":
        setBrainState("planning", "Planning");
        updateSteps("select", ["understand", "recall"]);
        break;
      case "tool_started": {
        const capability = capabilityForTool(data.tool);
        setBrainState("acting", `Using ${humanize(data.tool)}`, capability);
        updateSteps("act", ["understand", "recall", "select"]);
        break;
      }
      case "tool_finished":
        setBrainState("verifying", "Verifying", capabilityForTool(data.tool));
        updateSteps("verify", ["understand", "recall", "select", "act"]);
        break;
      case "skill_used": {
        const capability = capabilityForSkill(data.skill);
        setBrainState("acting", `Using ${humanize(data.skill)}`, capability);
        updateSteps("verify", ["understand", "select", "act"]);
        break;
      }
      case "permission_required":
        setBrainState("approval", "Waiting for approval", capabilityForTool((data.tools || [])[0]));
        updateSteps("act", ["understand", "recall", "select"]);
        showPermission(data.confirmations || []);
        break;
      case "permission_resolved":
        closePermission();
        setBrainState(data.allowed ? "acting" : "cancelling", data.allowed ? "Approved" : "Denied");
        break;
      case "generation_cancel_requested":
        setBrainState("cancelling", "Cancelling");
        break;
      case "mission_planning":
        renderMission({
          title: "Planning mission",
          goal: data.goal || "",
          summary: "Qwen is creating a grounded, verifiable plan.",
          status: "planning",
          steps: [],
        });
        setBrainState("planning", "Mission planning");
        break;
      case "mission_created":
      case "mission_updated":
      case "mission_step_started":
      case "mission_step_completed":
      case "mission_paused":
      case "mission_resumed":
        renderMission(data.mission);
        if (data.mission?.status === "paused") {
          setBrainState("approval", "Mission paused");
        } else if (data.mission?.status === "waiting_permission") {
          setBrainState("approval", "Waiting for approval");
        } else if (data.mission?.status === "running") {
          setBrainState("planning", "Mission running");
        }
        break;
      case "mission_completed":
        clearMissionView();
        elements.taskHeading.textContent = "Super Mission complete";
        elements.taskCopy.textContent = data.mission?.title || "Every mission step was verified.";
        setBrainState("complete", "Mission complete");
        break;
      case "mission_cancelled":
        clearMissionView();
        elements.taskHeading.textContent = "Super Mission cancelled";
        elements.taskCopy.textContent = data.mission?.title || "The mission stopped safely.";
        setBrainState("cancelling", "Mission cancelled");
        break;
      case "mission_failed":
        clearMissionView();
        elements.taskHeading.textContent = "Mission planning failed";
        elements.taskCopy.textContent = data.reason || "Qwen could not create a reliable plan.";
        setBrainState("error", "Mission failed");
        break;
      case "task_completed":
        elements.taskHeading.textContent = "Objective complete";
        setBrainState("complete", "Complete");
        updateSteps(null, ["understand", "recall", "select", "act", "verify"]);
        break;
      case "task_cancelled":
        elements.taskHeading.textContent = "Objective cancelled";
        setBrainState("cancelling", "Cancelled");
        break;
      case "system_shutdown":
        setBrainState("cancelling", "Offline");
        break;
      case "voice_state":
        voiceEnabled = Boolean(data.enabled);
        elements.voiceButton.disabled = !voiceEnabled;
        elements.voiceButton.setAttribute("aria-pressed", String(Boolean(data.listening)));
        break;
      default:
        break;
    }

    if (!initial && event.type === "connected") {
      addActivity("Live connection restored", "Receiving JARVIS events.", "success", event.timestamp);
    }
  }

  async function post(path, payload) {
    const response = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Jarvis-Token": sessionToken,
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(`JARVIS rejected the request (${response.status}).`);
    }
    return response.json();
  }

  async function sendMessage(text) {
    try {
      await post("/api/message", { text });
    } catch (error) {
      showToast(error.message || "Could not reach JARVIS.");
    }
  }

  async function sendAction(action) {
    try {
      await post("/api/action", { action });
    } catch (error) {
      showToast(error.message || "Could not perform that action.");
    }
  }

  async function sendMission(goal) {
    try {
      await post("/api/mission", { goal });
    } catch (error) {
      showToast(error.message || "Could not start the Super Mission.");
    }
  }

  function connectEvents() {
    eventSource = new EventSource("/api/events");
    eventTypes.forEach((type) => {
      eventSource.addEventListener(type, (message) => {
        try {
          handleEvent(JSON.parse(message.data));
        } catch (error) {
          console.error("Invalid JARVIS event", error);
        }
      });
    });
    eventSource.onerror = () => {
      setBrainState("cancelling", "Reconnecting");
    };
  }

  async function initialize() {
    try {
      const response = await fetch("/api/state", { cache: "no-store" });
      if (!response.ok) {
        throw new Error("Dashboard state is unavailable.");
      }
      const state = await response.json();
      sessionToken = state.session_token || "";
      voiceEnabled = Boolean(state.voice_enabled);
      elements.voiceButton.disabled = !voiceEnabled;
      elements.voiceButton.setAttribute(
        "aria-label",
        voiceEnabled
          ? "Toggle local voice listening"
          : "Voice is disabled for this session",
      );
      elements.modelPill.textContent = state.model || "Local model";
      elements.toolPill.textContent = `${(state.tools || []).length} tools`;
      setBrainState(state.brain_state || "idle", state.status || "Ready");

      emptyPlaceholder(elements.activityList, "Activity will appear as JARVIS works.");
      emptyPlaceholder(elements.conversationList, "Your conversation will appear here.");
      (state.messages || []).forEach(appendMessage);
      (state.events || []).forEach((event) => {
        if (event.type !== "message" && !event.type.startsWith("stream_")) {
          handleEvent(event, true);
        }
      });
      renderMission(state.mission);
      connectEvents();
    } catch (error) {
      setBrainState("error", "Disconnected");
      showToast(error.message || "Could not initialize the dashboard.");
    }
  }

  elements.form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = elements.input.value.trim();
    if (!text) {
      return;
    }
    elements.input.value = "";
    elements.input.style.height = "";
    sendMessage(text);
  });

  elements.input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.form.requestSubmit();
    }
  });

  elements.input.addEventListener("input", () => {
    elements.input.style.height = "auto";
    elements.input.style.height = `${Math.min(elements.input.scrollHeight, 130)}px`;
  });

  elements.stopButton.addEventListener("click", () => sendAction("cancel"));
  elements.allowButton.addEventListener("click", () => sendAction("allow"));
  elements.denyButton.addEventListener("click", () => sendAction("deny"));
  elements.permissionDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    sendAction("deny");
  });

  elements.missionButton.addEventListener("click", () => {
    if (activeMission) {
      showToast("Resume or cancel the active Super Mission first.");
      return;
    }
    elements.missionGoal.value = "";
    elements.missionDialog.showModal();
    elements.missionGoal.focus();
  });

  elements.missionForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const goal = elements.missionGoal.value.trim();
    if (!goal) {
      elements.missionGoal.focus();
      return;
    }
    elements.missionDialog.close();
    sendMission(goal);
  });

  elements.missionClose.addEventListener("click", () => {
    elements.missionDialog.close();
  });
  elements.missionPause.addEventListener("click", () => sendAction("mission_pause"));
  elements.missionResume.addEventListener("click", () => sendAction("mission_resume"));
  elements.missionCancel.addEventListener("click", () => {
    if (window.confirm("Cancel this Super Mission and its remaining steps?")) {
      sendAction("mission_cancel");
    }
  });

  elements.voiceButton.addEventListener("click", () => {
    if (!voiceEnabled) {
      showToast("Voice input is disabled for this session.");
      return;
    }
    const active = elements.voiceButton.getAttribute("aria-pressed") === "true";
    elements.voiceButton.setAttribute("aria-pressed", String(!active));
    sendAction(active ? "voice_off" : "voice_on");
  });

  elements.shutdownButton.addEventListener("click", () => {
    if (window.confirm("Shut down this local JARVIS session?")) {
      sendAction("shutdown");
    }
  });

  elements.clearActivity.addEventListener("click", () => {
    emptyPlaceholder(elements.activityList, "Activity cleared. New events will appear here.");
  });

  document.querySelectorAll(".capability-node").forEach((node) => {
    node.addEventListener("click", () => {
      const [title, copy] = capabilityDetails[node.dataset.capability];
      elements.inspector.replaceChildren();
      const heading = document.createElement("strong");
      heading.textContent = title;
      const detail = document.createElement("span");
      detail.textContent = copy;
      elements.inspector.append(heading, detail);
    });
  });

  const resizeObserver = new ResizeObserver(drawConnections);
  resizeObserver.observe(elements.canvas);
  window.addEventListener("resize", drawConnections);
  window.setTimeout(drawConnections, 0);

  window.setInterval(() => {
    elements.clock.textContent = new Intl.DateTimeFormat([], {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date());
  }, 1000);
  elements.clock.textContent = new Intl.DateTimeFormat([], {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());

  initialize();
})();
