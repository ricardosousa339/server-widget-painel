    const widgetsListEl = document.getElementById("widgetsList");
    const widgetsStatusEl = document.getElementById("widgetsStatus");
    const widgetsSummaryEl = document.getElementById("widgetsSummary");
    const footerMetaEl = document.getElementById("footerMeta");

    const customGifGalleryEl = document.getElementById("customGifGallery");
    const customGifSummaryEl = document.getElementById("customGifSummary");
    const customGifStatusEl = document.getElementById("customGifStatus");
    const customGifFileInputEl = document.getElementById("customGifFileInput");
    const uploadCustomGifBtnEl = document.getElementById("uploadCustomGifBtn");
    const reloadCustomGifBtnEl = document.getElementById("reloadCustomGifBtn");
    const enableCustomGifWidgetBtnEl = document.getElementById("enableCustomGifWidgetBtn");
    const clearCustomGifLibraryBtnEl = document.getElementById("clearCustomGifLibraryBtn");

    const doorbellGifPreviewEl = document.getElementById("doorbellGifPreview");
    const doorbellGifPreviewEmptyEl = document.getElementById("doorbellGifPreviewEmpty");
    const doorbellGifMetaEl = document.getElementById("doorbellGifMeta");
    const doorbellGifActionsEl = document.getElementById("doorbellGifActions");
    const doorbellGifStatusEl = document.getElementById("doorbellGifStatus");
    const doorbellGifFileInputEl = document.getElementById("doorbellGifFileInput");
    const uploadDoorbellGifBtnEl = document.getElementById("uploadDoorbellGifBtn");
    const removeDoorbellGifBtnEl = document.getElementById("removeDoorbellGifBtn");
    const reloadDoorbellGifBtnEl = document.getElementById("reloadDoorbellGifBtn");

    const verticalImageGalleryEl = document.getElementById("verticalImageGallery");
    const verticalImageSummaryEl = document.getElementById("verticalImageSummary");
    const verticalImageStatusEl = document.getElementById("verticalImageStatus");
    const verticalImageFileInputEl = document.getElementById("verticalImageFileInput");
    const verticalImageSpeedInputEl = document.getElementById("verticalImageSpeedInput");
    const verticalImageDirectionSelectEl = document.getElementById("verticalImageDirectionSelect");
    const uploadVerticalImageBtnEl = document.getElementById("uploadVerticalImageBtn");
    const clearVerticalImageLibraryBtnEl = document.getElementById("clearVerticalImageLibraryBtn");
    const reloadVerticalImageBtnEl = document.getElementById("reloadVerticalImageBtn");
    const saveVerticalImageSpeedBtnEl = document.getElementById("saveVerticalImageSpeedBtn");
    const enableVerticalImageWidgetBtnEl = document.getElementById("enableVerticalImageWidgetBtn");
    const toggleHelpBtnEl = document.getElementById("toggleHelpBtn");

    const displayModeSelectEl = document.getElementById("displayModeSelect");
    const hybridConfigFieldsEl = document.getElementById("hybridConfigFields");
    const hybridPeriodInputEl = document.getElementById("hybridPeriodInput");
    const hybridShowInputEl = document.getElementById("hybridShowInput");
    const modeSummaryEl = document.getElementById("modeSummary");

    const sidebarWidgetsCountEl = document.getElementById("sidebarWidgetsCount");
    const sidebarWidgetsModeEl = document.getElementById("sidebarWidgetsMode");
    const sidebarCustomCountEl = document.getElementById("sidebarCustomCount");
    const sidebarCustomSelectionEl = document.getElementById("sidebarCustomSelection");
    const sidebarDoorbellStateEl = document.getElementById("sidebarDoorbellState");
    const sidebarDoorbellAssetEl = document.getElementById("sidebarDoorbellAsset");
    const sidebarVerticalStateEl = document.getElementById("sidebarVerticalState");
    const sidebarVerticalSpeedEl = document.getElementById("sidebarVerticalSpeed");

    const categorySections = Array.from(document.querySelectorAll(".settings-category"));
    const sidebarNavLinks = Array.from(document.querySelectorAll(".sidebar-nav a[data-target]"));

    let latestWidgetsConfig = null;
    let latestGifState = null;
    let latestVerticalImageState = null;
    let activeCategoryId = null;

    const DISPLAY_MODES = new Set(["priority", "custom_only", "hybrid"]);
    const DEFAULT_HYBRID_PERIOD_SECONDS = 300;
    const DEFAULT_HYBRID_SHOW_SECONDS = 30;
    const HELP_VISIBLE_STORAGE_KEY = "widgets.config.help.visible";
    const statusClearTimers = new WeakMap();

    function setStatus(el, message, type) {
      const previousTimer = statusClearTimers.get(el);
      if (previousTimer) {
        window.clearTimeout(previousTimer);
        statusClearTimers.delete(el);
      }

      el.textContent = message;
      el.className = "status" + (type ? " " + type : "");

      if (type === "ok" && message) {
        const timer = window.setTimeout(() => {
          if (el.textContent === message) {
            el.textContent = "";
            el.className = "status";
          }
        }, 2400);
        statusClearTimers.set(el, timer);
      }
    }

    function applyHelpVisibility(showHelp) {
      document.body.classList.toggle("compact", !showHelp);
      toggleHelpBtnEl.textContent = showHelp ? "Ocultar ajuda" : "Mostrar ajuda";
      toggleHelpBtnEl.setAttribute("aria-pressed", showHelp ? "true" : "false");
    }

    function initializeHelpVisibility() {
      let showHelp = true;
      try {
        const storedValue = window.localStorage.getItem(HELP_VISIBLE_STORAGE_KEY);
        if (storedValue === "0") {
          showHelp = false;
        } else if (storedValue === "1") {
          showHelp = true;
        }
      } catch (_error) {
        showHelp = true;
      }
      applyHelpVisibility(showHelp);
    }

    function formatDateTime(ts) {
      if (!ts) return "-";
      const date = new Date(Number(ts) * 1000);
      if (Number.isNaN(date.getTime())) return "-";
      return date.toLocaleString();
    }

    function formatBytes(bytes) {
      const size = Number(bytes || 0);
      if (!Number.isFinite(size) || size <= 0) return "0 B";

      const units = ["B", "KB", "MB", "GB"];
      let index = 0;
      let value = size;
      while (value >= 1024 && index < units.length - 1) {
        value /= 1024;
        index += 1;
      }
      return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
    }

    function formatDuration(totalMs) {
      const ms = Number(totalMs || 0);
      if (!Number.isFinite(ms) || ms <= 0) return "0 ms";
      if (ms < 1000) return `${ms} ms`;
      return `${(ms / 1000).toFixed(2)} s`;
    }

    function sanitizeInt(value, fallback, minValue, maxValue) {
      const parsed = Number.parseInt(String(value), 10);
      if (!Number.isFinite(parsed)) {
        return fallback;
      }
      if (parsed < minValue) {
        return minValue;
      }
      if (parsed > maxValue) {
        return maxValue;
      }
      return parsed;
    }

    function normalizeDisplayMode(mode) {
      const normalized = String(mode || "").toLowerCase();
      if (!DISPLAY_MODES.has(normalized)) {
        return "priority";
      }
      return normalized;
    }

    function formatDisplayMode(mode) {
      if (mode === "custom_only") return "Sempre custom_gif";
      if (mode === "hybrid") return "Hibrido";
      return "Padrao (prioridade)";
    }

    function normalizeVerticalImageDirection(direction) {
      const normalized = String(direction || "up").toLowerCase();
      if (normalized === "down") {
        return "down";
      }
      return "up";
    }

    function formatVerticalImageDirection(direction) {
      return normalizeVerticalImageDirection(direction) === "down" ? "descendo" : "subindo";
    }

    function getAssetKey(asset) {
      return Number(asset?.revision || asset?.updated_at || asset?.uploaded_at || Date.now());
    }

    function getAssetName(asset) {
      return asset?.name || asset?.original_name || "-";
    }

    function clearElement(element) {
      while (element.firstChild) {
        element.removeChild(element.firstChild);
      }
    }

    function renderAssetPreview(imageEl, emptyEl, asset) {
      if (asset?.available && asset?.preview_url) {
        const cacheKey = getAssetKey(asset);
        const previewUrl = new URL(asset.preview_url, window.location.origin);
        previewUrl.searchParams.set("v", String(cacheKey));
        imageEl.src = previewUrl.toString();
        imageEl.hidden = false;
        emptyEl.hidden = true;
        return;
      }

      imageEl.hidden = true;
      imageEl.removeAttribute("src");
      emptyEl.hidden = false;
    }

    function formatAssetMeta(asset) {
      const parts = [
        `arquivo: ${getAssetName(asset)}`,
        `tipo: ${asset?.kind || "-"}`,
        `ativo: ${asset?.active ? "sim" : "nao"}`,
        `frames: ${Number(asset?.frame_count || 0)}`,
        `duracao: ${formatDuration(asset?.total_duration_ms)}`,
        `tamanho: ${formatBytes(asset?.size_bytes)}`,
        `enviado: ${formatDateTime(asset?.uploaded_at)}`,
      ];

      if (asset?.available === false) {
        parts.push("arquivo ausente");
      }

      return parts.join(" | ");
    }

    function formatCustomSummary(custom) {
      const assets = Array.isArray(custom?.assets) ? custom.assets : [];
      if (assets.length === 0) {
        return "Nenhum GIF custom cadastrado ainda.";
      }

      const selectedAsset = custom?.selected_asset;
      const selectedName = selectedAsset ? getAssetName(selectedAsset) : "nenhum";
      return [
        `arquivos: ${assets.length}`,
        `ativos: ${Number(custom?.active_count || 0)}`,
        `selecionado agora: ${selectedName}`,
        `ciclo: ${formatDuration(custom?.cycle_position_ms)} / ${formatDuration(custom?.cycle_total_ms)}`,
      ].join(" | ");
    }

    async function requestJson(url, options) {
      const res = await fetch(url, options);
      let detail = null;

      if (!res.ok) {
        detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || `Falha em ${url}`);
      }

      return await res.json();
    }

    async function patchGifAssetActive(assetId, active) {
      return await requestJson(`/widgets/custom-gif/${assetId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active }),
      });
    }

    async function deleteGifAsset(assetId) {
      return await requestJson(`/widgets/custom-gif/${assetId}`, {
        method: "DELETE",
      });
    }

    async function clearGifLibrary(kind) {
      return await requestJson(`/widgets/custom-gif?kind=${encodeURIComponent(kind)}`, {
        method: "DELETE",
      });
    }

    async function uploadGifAsset(kind, file, active) {
      const form = new FormData();
      form.append("file", file);
      form.append("kind", kind);
      form.append("active", active ? "true" : "false");

      return await requestJson("/widgets/custom-gif/upload", {
        method: "POST",
        body: form,
      });
    }

    async function uploadVerticalImageAsset(file, active) {
      const form = new FormData();
      form.append("file", file);
      form.append("active", active ? "true" : "false");

      return await requestJson("/widgets/vertical-image/upload", {
        method: "POST",
        body: form,
      });
    }

    async function patchVerticalImageAssetActive(assetId, active) {
      return await requestJson(`/widgets/vertical-image/${assetId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active }),
      });
    }

    async function deleteVerticalImageAsset(assetId) {
      return await requestJson(`/widgets/vertical-image/${assetId}`, {
        method: "DELETE",
      });
    }

    async function loadVerticalImageState(options = {}) {
      const silent = Boolean(options.silent);
      if (!silent) {
        setStatus(verticalImageStatusEl, "Carregando imagem vertical...", "");
      }

      const res = await fetch("/widgets/vertical-image");
      if (!res.ok) {
        throw new Error("Falha ao buscar /widgets/vertical-image");
      }

      const state = await res.json();
      renderVerticalImageState(state);

      if (!silent) {
        setStatus(verticalImageStatusEl, "Imagem vertical atualizada.", "ok");
      }

      return state;
    }

    function formatVerticalSummary(vertical) {
      const assets = Array.isArray(vertical?.assets) ? vertical.assets : [];
      if (assets.length === 0) {
        return "Nenhuma imagem vertical cadastrada ainda.";
      }

      const selectedAsset = vertical?.selected_asset;
      const selectedName = selectedAsset ? getAssetName(selectedAsset) : "nenhuma";
      const speed = Number(vertical?.scroll_speed_pps || 0);
      const direction = normalizeVerticalImageDirection(vertical?.scroll_direction || "up");
      return [
        `imagens: ${assets.length}`,
        `ativos: ${Number(vertical?.active_count || 0)}`,
        `em exibição: ${selectedName}`,
        `velocidade: ${speed > 0 ? speed : "-"} px/s`,
        `direção: ${formatVerticalImageDirection(direction)}`,
      ].join(" | ");
    }

    function formatVerticalAssetMeta(asset) {
      const width = Number(asset?.width || 0);
      const height = Number(asset?.height || 0);
      const dimensions = width > 0 && height > 0 ? `${width}x${height}` : "-";

      return [
        `arquivo: ${getAssetName(asset)}`,
        `ativo: ${asset?.active ? "sim" : "nao"}`,
        `dimensões: ${dimensions}`,
        `tamanho: ${formatBytes(asset?.size_bytes)}`,
        `enviado: ${formatDateTime(asset?.uploaded_at)}`,
      ].join(" | ");
    }

    function renderVerticalImageGallery(state) {
      latestVerticalImageState = state;

      const assets = Array.isArray(state?.assets) ? state.assets : [];
      const selectedAssetId = String(state?.selected_asset_id || "");

      verticalImageSummaryEl.textContent = formatVerticalSummary(state);
      clearElement(verticalImageGalleryEl);

      if (assets.length === 0) {
        const empty = document.createElement("div");
        empty.className = "gif-card-placeholder";
        empty.textContent = "Nenhuma imagem vertical cadastrada ainda.";
        verticalImageGalleryEl.appendChild(empty);
        return;
      }

      for (const asset of assets) {
        const card = document.createElement("article");
        card.className = "gif-card";
        if (asset.active) {
          card.classList.add("selected");
        }

        const header = document.createElement("div");
        header.className = "gif-card-header";

        const titleWrap = document.createElement("div");
        const title = document.createElement("h3");
        title.className = "gif-card-title";
        title.textContent = getAssetName(asset);
        titleWrap.appendChild(title);

        const badge = document.createElement("span");
        badge.className = "pill";
        badge.textContent = selectedAssetId === String(asset.id)
          ? (asset.active ? "ativo / atual" : "atual")
          : (asset.active ? "ativo" : "inativo");

        header.appendChild(titleWrap);
        header.appendChild(badge);

        const preview = document.createElement("img");
        preview.className = "gif-card-preview";
        preview.alt = `Preview de ${getAssetName(asset)}`;
        preview.hidden = true;

        const previewEmpty = document.createElement("div");
        previewEmpty.className = "gif-card-placeholder";
        previewEmpty.textContent = asset.available === false
          ? "Arquivo nao encontrado no disco."
          : "Preview indisponivel.";

        const previewWrap = document.createElement("div");
        previewWrap.appendChild(preview);
        previewWrap.appendChild(previewEmpty);

        renderAssetPreview(preview, previewEmpty, asset);

        const meta = document.createElement("div");
        meta.className = "gif-card-meta";
        meta.textContent = [
          formatVerticalAssetMeta(asset),
          `velocidade: ${Number(state?.scroll_speed_pps || 14)} px/s`,
          `direção: ${formatVerticalImageDirection(state?.scroll_direction || "up")}`,
        ].join(" | ");

        const actions = document.createElement("div");
        actions.className = "gif-card-actions";

        const activeLabel = document.createElement("label");
        const activeToggle = document.createElement("input");
        activeToggle.type = "checkbox";
        activeToggle.checked = Boolean(asset.active);
        activeToggle.addEventListener("change", async () => {
          const nextActive = activeToggle.checked;
          activeToggle.disabled = true;
          setStatus(
            verticalImageStatusEl,
            `${nextActive ? "Ativando" : "Desativando"} ${getAssetName(asset)}...`,
            ""
          );

          try {
            const updatedState = await patchVerticalImageAssetActive(asset.id, nextActive);
            renderVerticalImageState(updatedState);
            setStatus(
              verticalImageStatusEl,
              `${getAssetName(asset)} ${nextActive ? "ativada" : "desativada"}.`,
              "ok"
            );
          } catch (error) {
            activeToggle.checked = !nextActive;
            setStatus(
              verticalImageStatusEl,
              "Erro ao atualizar imagem vertical: " + error.message,
              "err"
            );
          } finally {
            activeToggle.disabled = false;
          }
        });
        activeLabel.appendChild(activeToggle);
        activeLabel.appendChild(document.createTextNode("Ativo"));

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "warn";
        deleteButton.textContent = "Remover";
        deleteButton.addEventListener("click", async () => {
          const confirmed = window.confirm(`Remover a imagem ${getAssetName(asset)}?`);
          if (!confirmed) {
            return;
          }

          deleteButton.disabled = true;
          setStatus(verticalImageStatusEl, `Removendo ${getAssetName(asset)}...`, "");

          try {
            const updatedState = await deleteVerticalImageAsset(asset.id);
            renderVerticalImageState(updatedState);
            setStatus(verticalImageStatusEl, `${getAssetName(asset)} removida.`, "ok");
          } catch (error) {
            setStatus(verticalImageStatusEl, "Erro ao remover imagem: " + error.message, "err");
          } finally {
            deleteButton.disabled = false;
          }
        });

        actions.appendChild(activeLabel);
        actions.appendChild(deleteButton);

        card.appendChild(header);
        card.appendChild(previewWrap);
        card.appendChild(meta);
        card.appendChild(actions);
        verticalImageGalleryEl.appendChild(card);
      }
    }

    function renderVerticalImageState(state) {
      latestVerticalImageState = state;

      const speed = Number(state?.scroll_speed_pps || 14);
      const direction = normalizeVerticalImageDirection(state?.scroll_direction || "up");
      verticalImageSpeedInputEl.value = String(speed);
      verticalImageDirectionSelectEl.value = direction;

      renderVerticalImageGallery(state);
      renderSidebarState();
    }

    function renderDoorbellGifState(state) {
      const doorbell = state?.doorbell || {};
      const asset = doorbell.asset || null;

      renderAssetPreview(doorbellGifPreviewEl, doorbellGifPreviewEmptyEl, asset);
      removeDoorbellGifBtnEl.disabled = !asset;

      doorbellGifMetaEl.textContent = asset
        ? formatAssetMeta(asset)
        : "Nenhum GIF da campainha configurado ainda.";

      clearElement(doorbellGifActionsEl);

      if (asset) {
        const label = document.createElement("label");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = Boolean(asset.active);

        checkbox.addEventListener("change", async () => {
          const nextActive = checkbox.checked;
          checkbox.disabled = true;
          setStatus(
            doorbellGifStatusEl,
            `${nextActive ? "Ativando" : "Desativando"} GIF da campainha...`,
            ""
          );

          try {
            const updatedState = await patchGifAssetActive(asset.id, nextActive);
            renderCustomGifState(updatedState);
            setStatus(
              doorbellGifStatusEl,
              `GIF da campainha ${nextActive ? "ativado" : "desativado"}.`,
              "ok"
            );
          } catch (error) {
            checkbox.checked = !nextActive;
            setStatus(
              doorbellGifStatusEl,
              "Erro ao atualizar GIF da campainha: " + error.message,
              "err"
            );
          } finally {
            checkbox.disabled = false;
          }
        });

        label.appendChild(checkbox);
        label.appendChild(document.createTextNode("Ativo"));
        doorbellGifActionsEl.appendChild(label);
      }
    }

    function renderCustomGifGallery(state) {
      latestGifState = state;

      const custom = state?.custom || {};
      const assets = Array.isArray(custom.assets) ? custom.assets : [];
      const selectedAssetId = String(custom.selected_asset_id || "");

      customGifSummaryEl.textContent = formatCustomSummary(custom);
      clearElement(customGifGalleryEl);

      if (assets.length === 0) {
        const empty = document.createElement("div");
        empty.className = "gif-card-placeholder";
        empty.textContent = "Nenhum GIF custom cadastrado ainda.";
        customGifGalleryEl.appendChild(empty);
        return;
      }

      for (const asset of assets) {
        const card = document.createElement("article");
        card.className = "gif-card";
        if (asset.active) {
          card.classList.add("selected");
        }

        const header = document.createElement("div");
        header.className = "gif-card-header";

        const titleWrap = document.createElement("div");
        const title = document.createElement("h3");
        title.className = "gif-card-title";
        title.textContent = getAssetName(asset);
        titleWrap.appendChild(title);

        const badge = document.createElement("span");
        badge.className = "pill";
        badge.textContent = selectedAssetId === String(asset.id)
          ? (asset.active ? "ativo / atual" : "atual")
          : (asset.active ? "ativo" : "inativo");

        header.appendChild(titleWrap);
        header.appendChild(badge);

        const preview = document.createElement("img");
        preview.className = "gif-card-preview";
        preview.alt = `Preview de ${getAssetName(asset)}`;
        preview.hidden = true;

        const previewEmpty = document.createElement("div");
        previewEmpty.className = "gif-card-placeholder";
        previewEmpty.textContent = asset.available === false
          ? "Arquivo nao encontrado no disco."
          : "Preview indisponivel.";

        const previewWrap = document.createElement("div");
        previewWrap.appendChild(preview);
        previewWrap.appendChild(previewEmpty);

        renderAssetPreview(preview, previewEmpty, asset);

        const meta = document.createElement("div");
        meta.className = "gif-card-meta";
        meta.textContent = formatAssetMeta(asset);

        const actions = document.createElement("div");
        actions.className = "gif-card-actions";

        const activeLabel = document.createElement("label");
        const activeToggle = document.createElement("input");
        activeToggle.type = "checkbox";
        activeToggle.checked = Boolean(asset.active);
        activeToggle.addEventListener("change", async () => {
          const nextActive = activeToggle.checked;
          activeToggle.disabled = true;
          setStatus(
            customGifStatusEl,
            `${nextActive ? "Ativando" : "Desativando"} ${getAssetName(asset)}...`,
            ""
          );

          try {
            const updatedState = await patchGifAssetActive(asset.id, nextActive);
            renderCustomGifState(updatedState);
            setStatus(
              customGifStatusEl,
              `${getAssetName(asset)} ${nextActive ? "ativado" : "desativado"}.`,
              "ok"
            );
          } catch (error) {
            activeToggle.checked = !nextActive;
            setStatus(
              customGifStatusEl,
              "Erro ao atualizar GIF: " + error.message,
              "err"
            );
          } finally {
            activeToggle.disabled = false;
          }
        });
        activeLabel.appendChild(activeToggle);
        activeLabel.appendChild(document.createTextNode("Ativo"));

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "warn";
        deleteButton.textContent = "Remover";
        deleteButton.addEventListener("click", async () => {
          const confirmed = window.confirm(`Remover o GIF ${getAssetName(asset)}?`);
          if (!confirmed) {
            return;
          }

          deleteButton.disabled = true;
          setStatus(customGifStatusEl, `Removendo ${getAssetName(asset)}...`, "");

          try {
            const updatedState = await deleteGifAsset(asset.id);
            renderCustomGifState(updatedState);
            setStatus(customGifStatusEl, `${getAssetName(asset)} removido.`, "ok");
          } catch (error) {
            setStatus(customGifStatusEl, "Erro ao remover GIF: " + error.message, "err");
          } finally {
            deleteButton.disabled = false;
          }
        });

        actions.appendChild(activeLabel);
        actions.appendChild(deleteButton);

        card.appendChild(header);
        card.appendChild(previewWrap);
        card.appendChild(meta);
        card.appendChild(actions);
        customGifGalleryEl.appendChild(card);
      }
    }

    function renderCustomGifState(state) {
      latestGifState = state;
      renderCustomGifGallery(state);
      renderDoorbellGifState(state);
      renderSidebarState();
    }

    async function loadCustomGifState(options = {}) {
      const silent = Boolean(options.silent);
      if (!silent) {
        setStatus(customGifStatusEl, "Carregando biblioteca custom...", "");
        setStatus(doorbellGifStatusEl, "Carregando GIF da campainha...", "");
      }

      const res = await fetch("/widgets/custom-gif");
      if (!res.ok) {
        throw new Error("Falha ao buscar /widgets/custom-gif");
      }

      const state = await res.json();
      renderCustomGifState(state);

      if (!silent) {
        setStatus(customGifStatusEl, "Biblioteca custom atualizada.", "ok");
        setStatus(doorbellGifStatusEl, "GIF da campainha atualizado.", "ok");
      }

      return state;
    }

    async function ensureWidgetEnabled(widgetName) {
      if (!setWidgetToggle(widgetName, true)) {
        await loadWidgetsConfig();
        setWidgetToggle(widgetName, true);
      }

      try {
        await saveWidgetsConfig(true);
      } catch (error) {
        setStatus(
          widgetsStatusEl,
          `Nao foi possivel ativar ${widgetName} automaticamente: ` + error.message,
          "warn"
        );
      }
    }

    async function ensureCustomGifWidgetEnabled() {
      await ensureWidgetEnabled("custom_gif");
    }

    async function ensureVerticalImageWidgetEnabled() {
      await ensureWidgetEnabled("vertical_image");
    }

    async function uploadCustomGif() {
      const files = Array.from(customGifFileInputEl.files || []);
      if (files.length === 0) {
        setStatus(customGifStatusEl, "Selecione um ou mais GIFs antes de enviar.", "warn");
        return;
      }

      uploadCustomGifBtnEl.disabled = true;
      setStatus(
        customGifStatusEl,
        files.length === 1 ? `Enviando ${getAssetName({ name: files[0].name })}...` : `Enviando ${files.length} GIFs...`,
        ""
      );

      try {
        for (const file of files) {
          await uploadGifAsset("custom", file, true);
        }

        customGifFileInputEl.value = "";
        await loadCustomGifState({ silent: true });
        await ensureCustomGifWidgetEnabled();
        setStatus(
          customGifStatusEl,
          files.length === 1
            ? `GIF ${files[0].name} enviado com sucesso.`
            : `${files.length} GIFs enviados com sucesso.`,
          "ok"
        );
      } catch (error) {
        try {
          await loadCustomGifState({ silent: true });
        } catch (_ignored) {
        }
        setStatus(customGifStatusEl, "Erro no upload: " + error.message, "err");
      } finally {
        uploadCustomGifBtnEl.disabled = false;
      }
    }

    async function clearCustomGifLibrary() {
      const confirmed = window.confirm("Apagar todos os GIFs custom da biblioteca?");
      if (!confirmed) {
        return;
      }

      clearCustomGifLibraryBtnEl.disabled = true;
      setStatus(customGifStatusEl, "Limpando biblioteca custom...", "");

      try {
        const state = await clearGifLibrary("custom");
        renderCustomGifState(state);
        setStatus(customGifStatusEl, "Biblioteca custom limpa.", "ok");
      } catch (error) {
        setStatus(customGifStatusEl, "Erro ao limpar biblioteca: " + error.message, "err");
      } finally {
        clearCustomGifLibraryBtnEl.disabled = false;
      }
    }

    async function activateCustomGifWidget() {
      await ensureCustomGifWidgetEnabled();
      setStatus(widgetsStatusEl, "custom_gif ativado na lista.", "ok");
    }

    async function uploadDoorbellGif() {
      const file = doorbellGifFileInputEl.files?.[0];
      if (!file) {
        setStatus(doorbellGifStatusEl, "Selecione um GIF antes de enviar.", "warn");
        return;
      }

      uploadDoorbellGifBtnEl.disabled = true;
      setStatus(doorbellGifStatusEl, `Enviando ${file.name}...`, "");

      try {
        await uploadGifAsset("doorbell", file, true);
        doorbellGifFileInputEl.value = "";
        await loadCustomGifState({ silent: true });
        await ensureCustomGifWidgetEnabled();
        setStatus(doorbellGifStatusEl, `GIF da campainha ${file.name} salvo com sucesso.`, "ok");
      } catch (error) {
        try {
          await loadCustomGifState({ silent: true });
        } catch (_ignored) {
        }
        setStatus(doorbellGifStatusEl, "Erro no upload: " + error.message, "err");
      } finally {
        uploadDoorbellGifBtnEl.disabled = false;
      }
    }

    async function removeDoorbellGif() {
      const confirmed = window.confirm("Remover o GIF da campainha?");
      if (!confirmed) {
        return;
      }

      removeDoorbellGifBtnEl.disabled = true;
      setStatus(doorbellGifStatusEl, "Removendo GIF da campainha...", "");

      try {
        const state = await clearGifLibrary("doorbell");
        renderCustomGifState(state);
        setStatus(doorbellGifStatusEl, "GIF da campainha removido.", "ok");
      } catch (error) {
        setStatus(doorbellGifStatusEl, "Erro ao remover GIF: " + error.message, "err");
      } finally {
        removeDoorbellGifBtnEl.disabled = false;
      }
    }

    async function uploadVerticalImage() {
      const files = Array.from(verticalImageFileInputEl.files || []);
      if (files.length === 0) {
        setStatus(verticalImageStatusEl, "Selecione uma ou mais imagens antes de enviar.", "warn");
        return;
      }

      uploadVerticalImageBtnEl.disabled = true;
      setStatus(
        verticalImageStatusEl,
        files.length === 1 ? `Enviando ${files[0].name}...` : `Enviando ${files.length} imagens...`,
        ""
      );

      try {
        for (const file of files) {
          await uploadVerticalImageAsset(file, true);
        }
        verticalImageFileInputEl.value = "";
        await loadVerticalImageState({ silent: true });
        await ensureVerticalImageWidgetEnabled();
        setStatus(
          verticalImageStatusEl,
          files.length === 1
            ? `Imagem ${files[0].name} salva com sucesso.`
            : `${files.length} imagens salvas com sucesso.`,
          "ok"
        );
      } catch (error) {
        try {
          await loadVerticalImageState({ silent: true });
        } catch (_ignored) {
        }
        setStatus(verticalImageStatusEl, "Erro no upload: " + error.message, "err");
      } finally {
        uploadVerticalImageBtnEl.disabled = false;
      }
    }

    async function clearVerticalImageLibrary() {
      const confirmed = window.confirm("Apagar toda a biblioteca de imagens verticais?");
      if (!confirmed) {
        return;
      }

      clearVerticalImageLibraryBtnEl.disabled = true;
      setStatus(verticalImageStatusEl, "Limpando biblioteca de imagens verticais...", "");

      try {
        const state = await requestJson("/widgets/vertical-image", {
          method: "DELETE",
        });
        renderVerticalImageState(state);
        setStatus(verticalImageStatusEl, "Biblioteca de imagens verticais limpa.", "ok");
      } catch (error) {
        setStatus(verticalImageStatusEl, "Erro ao limpar biblioteca: " + error.message, "err");
      } finally {
        clearVerticalImageLibraryBtnEl.disabled = false;
      }
    }

    async function saveVerticalImageSettings() {
      const speed = sanitizeInt(
        verticalImageSpeedInputEl.value,
        Number(latestVerticalImageState?.scroll_speed_pps || 14),
        1,
        120
      );
      const direction = normalizeVerticalImageDirection(verticalImageDirectionSelectEl.value);
      verticalImageSpeedInputEl.value = String(speed);
      verticalImageDirectionSelectEl.value = direction;

      saveVerticalImageSpeedBtnEl.disabled = true;
      setStatus(
        verticalImageStatusEl,
        `Salvando ajustes (${speed} px/s, ${formatVerticalImageDirection(direction)})...`,
        ""
      );

      try {
        const state = await requestJson("/widgets/vertical-image/config", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            scroll_speed_pps: speed,
            scroll_direction: direction,
          }),
        });
        renderVerticalImageState(state);
        setStatus(
          verticalImageStatusEl,
          `Imagem vertical atualizada (${speed} px/s, ${formatVerticalImageDirection(direction)}).`,
          "ok"
        );
      } catch (error) {
        setStatus(verticalImageStatusEl, "Erro ao salvar ajustes: " + error.message, "err");
      } finally {
        saveVerticalImageSpeedBtnEl.disabled = false;
      }
    }

    async function activateVerticalImageWidget() {
      await ensureVerticalImageWidgetEnabled();
      setStatus(widgetsStatusEl, "Imagem vertical ativada na lista.", "ok");
    }

    async function initPage() {
      await Promise.allSettled([
        loadWidgetsConfig(),
        loadCustomGifState(),
        loadVerticalImageState(),
      ]);
    }

    function syncDisplayModeUi(mode) {
      const normalizedMode = normalizeDisplayMode(mode);
      displayModeSelectEl.value = normalizedMode;
      hybridConfigFieldsEl.hidden = normalizedMode !== "hybrid";

      const periodSeconds = sanitizeInt(
        hybridPeriodInputEl.value,
        DEFAULT_HYBRID_PERIOD_SECONDS,
        10,
        86400
      );
      let showSeconds = sanitizeInt(
        hybridShowInputEl.value,
        DEFAULT_HYBRID_SHOW_SECONDS,
        1,
        3600
      );

      if (showSeconds >= periodSeconds) {
        showSeconds = Math.max(1, periodSeconds - 1);
      }

      hybridPeriodInputEl.value = String(periodSeconds);
      hybridShowInputEl.value = String(showSeconds);

      if (normalizedMode === "hybrid") {
        modeSummaryEl.textContent = `Modo atual: Hibrido | GIF ${showSeconds}s a cada ${periodSeconds}s`;
      } else {
        modeSummaryEl.textContent = `Modo atual: ${formatDisplayMode(normalizedMode)}`;
      }
    }

    function collectModeConfig() {
      const displayMode = normalizeDisplayMode(displayModeSelectEl.value);
      const hybridPeriodSeconds = sanitizeInt(
        hybridPeriodInputEl.value,
        DEFAULT_HYBRID_PERIOD_SECONDS,
        10,
        86400
      );
      let hybridShowSeconds = sanitizeInt(
        hybridShowInputEl.value,
        DEFAULT_HYBRID_SHOW_SECONDS,
        1,
        3600
      );

      if (hybridShowSeconds >= hybridPeriodSeconds) {
        hybridShowSeconds = Math.max(1, hybridPeriodSeconds - 1);
      }

      hybridPeriodInputEl.value = String(hybridPeriodSeconds);
      hybridShowInputEl.value = String(hybridShowSeconds);

      return {
        display_mode: displayMode,
        hybrid_period_seconds: hybridPeriodSeconds,
        default_gif_duration_seconds: hybridShowSeconds,
      };
    }

    function updateFooterMeta() {
      const updatedAt = latestWidgetsConfig?.updated_at;
      footerMetaEl.textContent = "Ultima atualizacao da configuracao: " + formatDateTime(updatedAt);
    }

    function getCategoryBody(section) {
      return section?.querySelector(".settings-category-body") || null;
    }

    function getCategoryHead(section) {
      return section?.querySelector(".settings-category-head") || null;
    }

    function setSidebarActiveCategory(categoryId) {
      activeCategoryId = categoryId || null;

      for (const link of sidebarNavLinks) {
        const targetId = link.dataset.target || "";
        link.classList.toggle("active", Boolean(categoryId) && targetId === categoryId);
      }

      for (const section of categorySections) {
        const head = getCategoryHead(section);
        if (head) {
          head.setAttribute("aria-expanded", section.classList.contains("is-open") ? "true" : "false");
        }
      }
    }

    function closeCategory(section) {
      if (!section) {
        return;
      }

      section.classList.remove("is-open");
      const body = getCategoryBody(section);
      if (body) {
        body.hidden = true;
      }
      if (activeCategoryId === section.id) {
        activeCategoryId = null;
      }
    }

    function openCategory(section, { scroll = false } = {}) {
      if (!section) {
        return false;
      }

      const body = getCategoryBody(section);
      if (body) {
        body.hidden = false;
      }
      section.classList.add("is-open");
      setSidebarActiveCategory(section.id);

      if (scroll) {
        section.scrollIntoView({ behavior: "smooth", block: "start" });
      }

      return true;
    }

    function toggleCategory(section, { scroll = false } = {}) {
      if (!section) {
        return false;
      }

      if (section.classList.contains("is-open")) {
        closeCategory(section);
        setSidebarActiveCategory(null);
        return false;
      }

      return openCategory(section, { scroll });
    }

    function openCategoryById(categoryId, { scroll = false } = {}) {
      const targetElement = document.getElementById(categoryId);
      const section = targetElement?.classList.contains("settings-category")
        ? targetElement
        : targetElement?.closest(".settings-category");

      if (!section) {
        return false;
      }

      const opened = openCategory(section, { scroll: false });
      if (!opened) {
        return false;
      }

      if (scroll) {
        const scrollTarget = targetElement && targetElement !== section ? targetElement : section;
        scrollTarget.scrollIntoView({ behavior: "smooth", block: "start" });
      }

      return true;
    }

    function initializeCategoryAccordion() {
      for (const section of categorySections) {
        const head = getCategoryHead(section);
        if (!head) {
          continue;
        }

        head.setAttribute("role", "button");
        head.setAttribute("tabindex", "0");
        head.setAttribute("aria-expanded", "true");

        head.addEventListener("click", () => {
          toggleCategory(section, { scroll: false });
        });

        head.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleCategory(section, { scroll: false });
          }
        });

        const body = getCategoryBody(section);
        if (body) {
          body.hidden = false;
        }

        section.classList.add("is-open");
      }

      for (const link of sidebarNavLinks) {
        link.addEventListener("click", (event) => {
          const targetId = link.dataset.target || "";
          const anchorId = (link.getAttribute("href") || "").replace(/^#/, "");
          if (!targetId) {
            return;
          }

          event.preventDefault();
          openCategoryById(targetId, { scroll: true });

          if (anchorId) {
            history.replaceState(null, "", `#${anchorId}`);
            const anchor = document.getElementById(anchorId);
            if (anchor && anchor !== document.getElementById(targetId)) {
              anchor.scrollIntoView({ behavior: "smooth", block: "start" });
            }
          }
        });
      }

      window.addEventListener("hashchange", () => {
        const targetId = window.location.hash.replace(/^#/, "");
        if (targetId) {
          openCategoryById(targetId, { scroll: true });
        }
      });

      if (window.location.hash) {
        const targetId = window.location.hash.replace(/^#/, "");
        if (!openCategoryById(targetId, { scroll: true })) {
          setSidebarActiveCategory(null);
        }
      } else if (categorySections.length > 0) {
        setSidebarActiveCategory(categorySections[0].id);
      }
    }

    function renderSidebarState() {
      const widgets = Array.isArray(latestWidgetsConfig?.widgets) ? latestWidgetsConfig.widgets : [];
      const enabledWidgets = widgets.filter((widget) => Boolean(widget.enabled));
      const configDisplayMode = normalizeDisplayMode(latestWidgetsConfig?.display_mode);

      sidebarWidgetsCountEl.textContent = widgets.length > 0 ? `${enabledWidgets.length}/${widgets.length}` : "-";
      sidebarWidgetsModeEl.textContent = latestWidgetsConfig
        ? `Modo: ${formatDisplayMode(configDisplayMode)}`
        : "Modo: -";

      const custom = latestGifState?.custom || {};
      const customAssets = Array.isArray(custom.assets) ? custom.assets : [];
      const customActiveCount = Number(
        custom.active_count || customAssets.filter((asset) => Boolean(asset?.active)).length
      );
      const selectedCustom = custom.selected_asset || null;

      sidebarCustomCountEl.textContent = customAssets.length > 0 ? `${customActiveCount}/${customAssets.length}` : "-";
      sidebarCustomSelectionEl.textContent = `Selecionado: ${selectedCustom ? getAssetName(selectedCustom) : "nenhum"}`;

      const doorbell = latestGifState?.doorbell || {};
      const doorbellAsset = doorbell.asset || null;

      sidebarDoorbellStateEl.textContent = doorbellAsset
        ? (doorbell.configured ? "Ativo" : "Inativo")
        : "Sem GIF";
      sidebarDoorbellAssetEl.textContent = `Asset: ${doorbellAsset ? getAssetName(doorbellAsset) : "nenhum"}`;

      const vertical = latestVerticalImageState || {};
      const verticalAssets = Array.isArray(vertical.assets) ? vertical.assets : [];
      const verticalActiveCount = Number(
        vertical.active_count || verticalAssets.filter((asset) => Boolean(asset?.active)).length
      );
      const selectedVertical = vertical.selected_asset || null;
      const verticalSpeed = Number(vertical.scroll_speed_pps || 0);
      const verticalDirection = normalizeVerticalImageDirection(vertical.scroll_direction || "up");

      sidebarVerticalStateEl.textContent = verticalAssets.length > 0
        ? `${verticalActiveCount}/${verticalAssets.length} ativos | atual: ${selectedVertical ? getAssetName(selectedVertical) : "nenhuma"}`
        : "Sem imagem";
      sidebarVerticalSpeedEl.textContent = Number.isFinite(verticalSpeed) && verticalSpeed > 0
        ? `Velocidade: ${verticalSpeed} px/s | ${formatVerticalImageDirection(verticalDirection)}`
        : `Velocidade: - | ${formatVerticalImageDirection(verticalDirection)}`;
    }

    function renderWidgets(config) {
      latestWidgetsConfig = config;
      widgetsListEl.innerHTML = "";

      const widgets = Array.isArray(config?.widgets) ? config.widgets : [];
      const enabledCount = widgets.filter((widget) => Boolean(widget.enabled)).length;

      for (const widget of widgets) {
        const card = document.createElement("article");
        card.className = "widget-item";

        const title = document.createElement("div");
        title.className = "widget-title";

        const label = document.createElement("label");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "widget-toggle";
        checkbox.value = widget.name;
        checkbox.checked = Boolean(widget.enabled);
        label.appendChild(checkbox);

        const text = document.createElement("span");
        text.textContent = widget.name;
        label.appendChild(text);

        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = widget.role;

        title.appendChild(label);
        title.appendChild(badge);

        const meta = document.createElement("div");
        meta.className = "meta";
        meta.textContent = "prioridade: " + widget.priority;

        card.appendChild(title);
        card.appendChild(meta);
        widgetsListEl.appendChild(card);
      }

      const configDisplayMode = normalizeDisplayMode(config?.display_mode);
      const configHybridPeriod = sanitizeInt(
        config?.hybrid_period_seconds,
        DEFAULT_HYBRID_PERIOD_SECONDS,
        10,
        86400
      );
      const configHybridShow = sanitizeInt(
        config?.default_gif_duration_seconds,
        DEFAULT_HYBRID_SHOW_SECONDS,
        1,
        3600
      );

      displayModeSelectEl.value = configDisplayMode;
      hybridPeriodInputEl.value = String(configHybridPeriod);
      hybridShowInputEl.value = String(configHybridShow);
      syncDisplayModeUi(configDisplayMode);

      widgetsSummaryEl.textContent = `Ativos: ${enabledCount} de ${widgets.length} | modo: ${formatDisplayMode(configDisplayMode)}`;
      renderSidebarState();
      updateFooterMeta();
    }

    function collectEnabledWidgets() {
      return Array.from(document.querySelectorAll(".widget-toggle"))
        .filter((el) => el.checked)
        .map((el) => el.value);
    }

    function setAllWidgets(enabled) {
      const toggles = document.querySelectorAll(".widget-toggle");
      for (const toggle of toggles) {
        toggle.checked = enabled;
      }
    }

    function setWidgetToggle(widgetName, enabled) {
      const toggle = document.querySelector(`.widget-toggle[value="${widgetName}"]`);
      if (!toggle) {
        return false;
      }
      toggle.checked = enabled;
      return true;
    }

    async function loadWidgetsConfig() {
      setStatus(widgetsStatusEl, "Carregando configuracao de widgets...", "");
      try {
        const res = await fetch("/widgets/config");
        if (!res.ok) {
          throw new Error("Falha ao buscar /widgets/config");
        }
        const config = await res.json();
        renderWidgets(config);
        setStatus(widgetsStatusEl, "Configuracao carregada.", "ok");
      } catch (error) {
        setStatus(widgetsStatusEl, "Erro ao carregar configuracao: " + error.message, "err");
      }
    }

    async function saveWidgetsConfig(silent) {
      const enabledWidgets = collectEnabledWidgets();
      const modeConfig = collectModeConfig();
      if (!silent) {
        setStatus(widgetsStatusEl, "Salvando configuracao...", "");
      }

      const res = await fetch("/widgets/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled_widgets: enabledWidgets,
          display_mode: modeConfig.display_mode,
          hybrid_period_seconds: modeConfig.hybrid_period_seconds,
          default_gif_duration_seconds: modeConfig.default_gif_duration_seconds,
        }),
      });

      if (!res.ok) {
        throw new Error("Falha ao salvar /widgets/config");
      }

      const config = await res.json();
      renderWidgets(config);
      if (!silent) {
        setStatus(widgetsStatusEl, "Configuracao salva com sucesso.", "ok");
      }
      return config;
    }

    document.getElementById("enableAllBtn").addEventListener("click", () => {
      setAllWidgets(true);
      setStatus(widgetsStatusEl, "Todos marcados. Clique em salvar para aplicar.", "warn");
    });

    document.getElementById("disableAllBtn").addEventListener("click", () => {
      setAllWidgets(false);
      setStatus(widgetsStatusEl, "Todos desmarcados. Clique em salvar para aplicar.", "warn");
    });

    document.getElementById("reloadWidgetsBtn").addEventListener("click", loadWidgetsConfig);
    document.getElementById("saveWidgetsBtn").addEventListener("click", async () => {
      try {
        await saveWidgetsConfig(false);
      } catch (error) {
        setStatus(widgetsStatusEl, "Erro ao salvar: " + error.message, "err");
      }
    });

    reloadCustomGifBtnEl.addEventListener("click", () => loadCustomGifState());
    uploadCustomGifBtnEl.addEventListener("click", uploadCustomGif);
    clearCustomGifLibraryBtnEl.addEventListener("click", clearCustomGifLibrary);
    enableCustomGifWidgetBtnEl.addEventListener("click", activateCustomGifWidget);

    reloadDoorbellGifBtnEl.addEventListener("click", () => loadCustomGifState());
    uploadDoorbellGifBtnEl.addEventListener("click", uploadDoorbellGif);
    removeDoorbellGifBtnEl.addEventListener("click", removeDoorbellGif);

    reloadVerticalImageBtnEl.addEventListener("click", () => loadVerticalImageState());
    uploadVerticalImageBtnEl.addEventListener("click", uploadVerticalImage);
    clearVerticalImageLibraryBtnEl.addEventListener("click", clearVerticalImageLibrary);
    saveVerticalImageSpeedBtnEl.addEventListener("click", saveVerticalImageSettings);
    enableVerticalImageWidgetBtnEl.addEventListener("click", activateVerticalImageWidget);

    toggleHelpBtnEl.addEventListener("click", () => {
      const showHelp = document.body.classList.contains("compact");
      applyHelpVisibility(showHelp);
      try {
        window.localStorage.setItem(HELP_VISIBLE_STORAGE_KEY, showHelp ? "1" : "0");
      } catch (_error) {
      }
    });

    displayModeSelectEl.addEventListener("change", () => {
      syncDisplayModeUi(displayModeSelectEl.value);
      setStatus(widgetsStatusEl, "Modo alterado. Clique em salvar para aplicar.", "warn");
    });

    hybridPeriodInputEl.addEventListener("change", () => {
      syncDisplayModeUi(displayModeSelectEl.value);
      setStatus(widgetsStatusEl, "Periodo hibrido alterado. Clique em salvar para aplicar.", "warn");
    });

    hybridShowInputEl.addEventListener("change", () => {
      syncDisplayModeUi(displayModeSelectEl.value);
      setStatus(widgetsStatusEl, "Tempo do GIF alterado. Clique em salvar para aplicar.", "warn");
    });

    initializeHelpVisibility();
    initializeCategoryAccordion();
    initPage();
