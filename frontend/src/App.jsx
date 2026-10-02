import { useEffect, useRef, useState } from "react";

const API = "http://localhost:8000/api";

export default function App() {
  const [projects, setProjects] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [projectTitle, setProjectTitle] = useState("");
  const [selected, setSelected] = useState(null);
  const [preview, setPreview] = useState("");
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [deleteCandidate, setDeleteCandidate] = useState(null);
  const [renameCandidate, setRenameCandidate] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [previewMode, setPreviewMode] = useState("desktop");
  const [expandedProjects, setExpandedProjects] = useState({});
  const [projectSearch, setProjectSearch] = useState("");
  const [projectPage, setProjectPage] = useState(1);
  const [previewNonce, setPreviewNonce] = useState(0);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [lastGenerationTimeMs, setLastGenerationTimeMs] = useState(null);
  const [systemInfo, setSystemInfo] = useState(null);
  const [previewFullscreen, setPreviewFullscreen] = useState(false);
  const previewFullscreenRef = useRef(null);

  const PROJECTS_PER_PAGE = 10;

  const isUpdateMode = Boolean(selected);

  const generationTimes = projects.flatMap((project) =>
    Array.isArray(project.versions)
      ? project.versions
          .map((version) => Number(version.generation_time_ms))
          .filter((value) => Number.isFinite(value) && value > 0)
      : []
  );

  const effectiveGenerationTimes =
    generationTimes.length > 0
      ? generationTimes
      : Number.isFinite(lastGenerationTimeMs) && lastGenerationTimeMs > 0
        ? [lastGenerationTimeMs]
        : [];

  const generationAverageMs = effectiveGenerationTimes.length
    ? effectiveGenerationTimes.reduce((sum, value) => sum + value, 0) /
      effectiveGenerationTimes.length
    : 30000;

  const generationAverageSeconds = Math.max(1, Math.round(generationAverageMs / 1000));

  const filteredProjects = projects.filter((project) => {
    const query = projectSearch.trim().toLowerCase();

    if (!query) return true;

    return (
      project.name?.toLowerCase().includes(query) ||
      project.type?.toLowerCase().includes(query)
    );
  });

  const totalProjectPages = Math.max(
    1,
    Math.ceil(
      filteredProjects.length / PROJECTS_PER_PAGE
    )
  );

  const visibleProjects = filteredProjects.slice(
    (projectPage - 1) * PROJECTS_PER_PAGE,
    projectPage * PROJECTS_PER_PAGE
  );

  async function loadProjects() {
    try {
      const res = await fetch(`${API}/projects`);

      if (!res.ok) {
        throw new Error("Impossible de charger les projets.");
      }

      const summary = await res.json();

      const detailedProjects = await Promise.all(
        summary.map(async (project) => {
          try {
            const projectRes = await fetch(
              `${API}/projects/${project.id}`
            );

            if (!projectRes.ok) {
              return project;
            }

            return await projectRes.json();
          } catch {
            return project;
          }
        })
      );

      setProjects(detailedProjects);

      setProjectPage((current) =>
        Math.min(
          current,
          Math.max(
            1,
            Math.ceil(
              detailedProjects.length / PROJECTS_PER_PAGE
            )
          )
        )
      );

      setExpandedProjects((previous) => {
        const next = { ...previous };

        detailedProjects.forEach((project) => {
          if (typeof next[project.id] !== "boolean") {
            next[project.id] = project.id === selected?.id;
          }
        });

        return next;
      });
    } catch {
      setProjects([]);
    }
  }

  async function openProject(project) {
    try {
      const res = await fetch(`${API}/projects/${project.id}`);

      if (!res.ok) {
        throw new Error("Impossible d'ouvrir le projet.");
      }

      const data = await res.json();

      setSelected(data);

      const current =
        data.versions?.find(
          (version) =>
            version.version === data.current_version
        ) || data.versions?.[data.versions.length - 1];

      setSelectedVersion(current?.version ?? null);
      setPreview(current?.html || "");
      setPreviewMode("desktop");
      setPreviewNonce((value) => value + 1);
      setPrompt("");
      setProjectTitle("");
      setMessage("");

      setExpandedProjects((previous) => ({
        ...previous,
        [data.id]: true,
      }));
    } catch {
      setMessage("Impossible d'ouvrir ce projet.");
    }
  }

  function openVersion(project, version) {
    setSelected(project);
    setSelectedVersion(version.version);
    setPreview(version.html || "");
    setPreviewMode("desktop");
    setPreviewNonce((value) => value + 1);
    setPrompt("");
    setProjectTitle("");
    setMessage("");

    setExpandedProjects((previous) => ({
      ...previous,
      [project.id]: true,
    }));
  }

  function toggleProject(projectId) {
    setExpandedProjects((previous) => ({
      ...previous,
      [projectId]: !previous[projectId],
    }));
  }

  function startNewProject() {
    setSelected(null);
    setSelectedVersion(null);
    setPreview("");
    setPrompt("");
    setProjectTitle("");
    setMessage("");
    setPreviewMode("desktop");
    setPreviewNonce((value) => value + 1);
  }

  function changePreviewMode(mode) {
    setPreviewMode(mode);
    setPreviewNonce((value) => value + 1);
  }

  async function enterPreviewFullscreen() {
    setPreviewFullscreen(true);
    setPreviewNonce((value) => value + 1);
    try {
      await new Promise((resolve) => window.setTimeout(resolve, 0));
      if (previewFullscreenRef.current?.requestFullscreen) {
        await previewFullscreenRef.current.requestFullscreen();
      }
    } catch {
      // Le mode intégré reste disponible si le navigateur refuse l'API fullscreen.
    }
  }

  async function exitPreviewFullscreen() {
    try {
      if (document.fullscreenElement && document.exitFullscreen) {
        await document.exitFullscreen();
      }
    } catch {
      // Rien à faire.
    }
    setPreviewFullscreen(false);
    setPreviewNonce((value) => value + 1);
  }

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    function handleFullscreenChange() {
      if (!document.fullscreenElement) {
        setPreviewFullscreen(false);
      }
    }

    document.addEventListener("fullscreenchange", handleFullscreenChange);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadSystemInfo() {
      try {
        const res = await fetch(`${API}/system`);

        if (!res.ok) {
          throw new Error("Impossible de charger les informations système.");
        }

        const data = await res.json();

        if (!cancelled) {
          setSystemInfo(data);
        }
      } catch {
        if (!cancelled) {
          setSystemInfo(null);
        }
      }
    }

    loadSystemInfo();

    const interval = window.setInterval(loadSystemInfo, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (!loading) {
      return undefined;
    }

    const startedAt = performance.now();
    const estimatedDuration = Math.max(5000, generationAverageMs);

    setGenerationProgress((current) =>
      Math.max(current, 8)
    );

    const timer = window.setInterval(() => {
      const elapsed = performance.now() - startedAt;
      const estimatedProgress =
        8 + (elapsed / estimatedDuration) * 82;

      setGenerationProgress((current) =>
        Math.min(93, Math.max(current, estimatedProgress))
      );
    }, 250);

    return () => window.clearInterval(timer);
  }, [loading, generationAverageMs]);


  async function generate() {
    if (!prompt.trim()) return;

    if (!selected && !projectTitle.trim()) {
      setMessage("Le titre du projet est obligatoire.");
      return;
    }

    setLoading(true);
    setGenerationProgress(8);
    setMessage("");

    try {
      const res = await fetch(`${API}/generation`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt,
          title: selected ? null : projectTitle.trim() || null,
          project_id: selected?.id || null,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setMessage(
          data.detail || "Une erreur est survenue."
        );
        return;
      }

      if (data.action === "DELETE") {
        setDeleteCandidate(
          data.project || selected
        );
        return;
      }

      if (!data.project || !data.version) {
        setMessage(
          "La réponse du backend est incomplète."
        );
        return;
      }

      setSelected(data.project);
      setSelectedVersion(data.version.version);
      setPreview(data.version.html || "");
      setPreviewMode("desktop");
      setPreviewNonce((value) => value + 1);
      setPrompt("");

      setExpandedProjects((previous) => ({
        ...previous,
        [data.project.id]: true,
      }));

      await loadProjects();

      const generationTimeMs = Number(
        data.version.generation_time_ms
      );

      if (
        Number.isFinite(generationTimeMs) &&
        generationTimeMs > 0
      ) {
        setLastGenerationTimeMs(generationTimeMs);
      }

      const generationTimeLabel = Number.isFinite(
        generationTimeMs
      )
        ? `${(generationTimeMs / 1000).toFixed(1)} s`
        : "temps indisponible";

      setMessage(
        `Version ${data.version.version} générée · ${generationTimeLabel}.`
      );
    } catch {
      setMessage(
        "Impossible de contacter le backend."
      );
    } finally {
      setGenerationProgress(100);
      setLoading(false);
    }
  }

  function downloadCurrentVersionZip() {
    if (!selected?.id || !selectedVersion) {
      return;
    }

    const url = `${API}/generation/projects/${selected.id}/versions/${selectedVersion}/download`;
    window.location.href = url;
  }

  function openRenameProject(project) {
    if (!project) return;

    setRenameCandidate(project);
    setRenameValue(project.name || "");
    setMessage("");
  }

  function closeRenameProject() {
    if (renaming) return;

    setRenameCandidate(null);
    setRenameValue("");
  }

  async function confirmRename() {
    if (!renameCandidate || renaming) return;

    const name = renameValue.trim();

    if (!name) {
      setMessage("Le nom du projet ne peut pas être vide.");
      return;
    }

    if (name === renameCandidate.name) {
      closeRenameProject();
      return;
    }

    setRenaming(true);

    try {
      const res = await fetch(
        `${API}/projects/${renameCandidate.id}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ name }),
        }
      );

      const data = await res.json();

      if (!res.ok) {
        throw new Error(
          data.detail || "Impossible de renommer le projet."
        );
      }

      if (data.project) {
        setSelected((current) =>
          current?.id === data.project.id
            ? { ...current, name: data.project.name }
            : current
        );
      }

      setRenameCandidate(null);
      setRenameValue("");
      setMessage("Projet renommé.");
      await loadProjects();
    } catch (error) {
      setMessage(
        error?.message || "Impossible de renommer le projet."
      );
    } finally {
      setRenaming(false);
    }
  }

  async function confirmDelete() {
    if (!deleteCandidate) return;

    try {
      await fetch(
        `${API}/projects/${deleteCandidate.id}`,
        {
          method: "DELETE",
        }
      );

      if (selected?.id === deleteCandidate.id) {
        setSelected(null);
        setSelectedVersion(null);
        setPreview("");
      }

      setDeleteCandidate(null);
      setPrompt("");
      setMessage("");

      await loadProjects();
    } catch {
      setMessage(
        "Impossible de supprimer le projet."
      );
      setDeleteCandidate(null);
    }
  }

  function getProjectVersions(project) {
    if (!Array.isArray(project.versions)) {
      return [];
    }

    return [...project.versions].sort(
      (a, b) => b.version - a.version
    );
  }

  return (
    <main className="app">
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="brand">
            <div className="brand-mark">D</div>

            <div>
              <div className="brand-name">
                Design AI
              </div>

              <div className="brand-subtitle">
                Personal Studio
              </div>
            </div>
          </div>

          <button
            className={`new-project ${
              !isUpdateMode ? "active" : ""
            }`}
            onClick={startNewProject}
          >
            <span>+</span>
            Générer un nouveau projet
          </button>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">
            <span>PROJETS</span>

            <span className="project-count">
              {projects.length}
            </span>
          </div>

          <div className="project-search">
            <span>⌕</span>
            <input
              type="search"
              value={projectSearch}
              onChange={(event) => {
                setProjectSearch(event.target.value);
                setProjectPage(1);
              }}
              placeholder="Rechercher un projet..."
              aria-label="Rechercher un projet"
            />
            {projectSearch && (
              <button
                type="button"
                onClick={() => {
                  setProjectSearch("");
                  setProjectPage(1);
                }}
                aria-label="Effacer la recherche"
              >
                ×
              </button>
            )}
          </div>

          <div className="project-list">
            {projects.length === 0 ? (
              <div className="sidebar-empty">
                Aucun projet pour le moment.
              </div>
            ) : (
              visibleProjects.map((project) => {
                const versions =
                  getProjectVersions(project);

                const isExpanded =
                  expandedProjects[project.id];

                const isSelected =
                  selected?.id === project.id;

                return (
                  <div
                    className={`project-tree ${
                      isSelected ? "active" : ""
                    }`}
                    key={project.id}
                  >
                    <div className="project-tree-header">
                      <button
                        className={`project-item ${
                          isSelected ? "active" : ""
                        }`}
                        onClick={() =>
                          openProject(project)
                        }
                      >
                        <div className="project-mini-preview">
                          <div className="mini-line large" />
                          <div className="mini-line medium" />
                          <div className="mini-line small" />
                        </div>

                        <div className="project-item-info">
                          <div className="project-item-name">
                            {project.name}
                          </div>

                          <div className="project-item-meta">
                            <span>
                              {project.type}
                            </span>

                            <span>
                              v{project.current_version}
                            </span>
                          </div>
                        </div>
                      </button>

                      {versions.length > 0 && (
                        <button
                          className={`project-expand ${
                            isExpanded
                              ? "expanded"
                              : ""
                          }`}
                          onClick={() =>
                            toggleProject(project.id)
                          }
                          aria-label={
                            isExpanded
                              ? "Masquer les versions"
                              : "Afficher les versions"
                          }
                        >
                          <span>⌄</span>
                        </button>
                      )}
                    </div>

                    {isExpanded &&
                      versions.length > 0 && (
                        <div className="version-tree">
                          {versions.map((version) => {
                            const isCurrent =
                              version.version ===
                              project.current_version;

                            const isActive =
                              isSelected &&
                              selectedVersion ===
                                version.version;

                            return (
                              <button
                                key={`${project.id}-v${version.version}`}
                                className={`version-item ${
                                  isActive
                                    ? "active"
                                    : ""
                                } ${
                                  isCurrent
                                    ? "current"
                                    : ""
                                }`}
                                onClick={() =>
                                  openVersion(
                                    project,
                                    version
                                  )
                                }
                              >
                                <span className="version-branch">
                                  └
                                </span>

                                <span className="version-number">
                                  v{version.version}
                                </span>

                                <span className="version-label">
                                  {isCurrent
                                    ? "actuelle"
                                    : version.prompt ||
                                      "Modification"}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                  </div>
                );
              })
            )}

            {projects.length > 0 &&
              filteredProjects.length === 0 && (
                <div className="sidebar-empty">
                  Aucun projet trouvé.
                </div>
              )}
          </div>

          {totalProjectPages > 1 && (
            <div className="project-pagination">
              <button
                type="button"
                onClick={() =>
                  setProjectPage((page) =>
                    Math.max(1, page - 1)
                  )
                }
                disabled={projectPage === 1}
                aria-label="Page précédente"
              >
                ‹
              </button>

              <span>
                {projectPage} / {totalProjectPages}
              </span>

              <button
                type="button"
                onClick={() =>
                  setProjectPage((page) =>
                    Math.min(totalProjectPages, page + 1)
                  )
                }
                disabled={
                  projectPage === totalProjectPages
                }
                aria-label="Page suivante"
              >
                ›
              </button>
            </div>
          )}
        </div>

        <div className="sidebar-bottom">
          <div className="local-status">
            <span className="status-dot" />

            <div>
              <strong>Local AI</strong>
              <small>Ollama connected</small>
            </div>
          </div>

          <div className="system-info">
            <div className="system-info-row">
              <span className="system-info-label">MODÈLE</span>
              <strong>{systemInfo?.model || "Ollama"}</strong>
            </div>

            <div className="system-info-row">
              <span className="system-info-label">RAM DISPONIBLE</span>
              <strong>
                {systemInfo
                  ? `${systemInfo.ram_available_gb} Go`
                  : "—"}
              </strong>
            </div>

            <div className="system-info-row generation-average-row">
              <span className="system-info-label">TEMPS MOYEN</span>
              <strong>
                {effectiveGenerationTimes.length > 0
                  ? `${generationAverageSeconds} s`
                  : "—"}
              </strong>
            </div>
          </div>

          <div className="sidebar-version">
            Personal Design AI · v0.1
          </div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Studio</span>

            <span className="breadcrumb-separator">
              /
            </span>

            <span className="breadcrumb-current">
              {selected
                ? selected.name
                : "Nouvelle création"}
            </span>
          </div>

          <div className="topbar-actions">
            {selected && (
              <div className="version-pill">
                <span>VERSION</span>
                v
                {selectedVersion ||
                  selected.current_version}
              </div>
            )}

            <div className="connection-pill">
              <span className="connection-dot" />
              Local
            </div>
          </div>
        </header>

        <div className="workspace-content">
          {!selected ? (
            <section className="home">
              <div className="creation-header">
                <div>
                  <div className="mode-badge create">
                    <span>✦</span>
                    CREATE
                  </div>

                  <h1>
                    Crée quelque chose
                    <br />
                    de <em>singulier.</em>
                  </h1>

                  <p>
                    Décris ton idée. Design AI transforme
                    ton intention en une véritable interface
                    web et construit ton projet avec toi.
                  </p>
                </div>
              </div>

              <Composer
                mode="create"
                prompt={prompt}
                setPrompt={setPrompt}
                projectTitle={projectTitle}
                setProjectTitle={setProjectTitle}
                generate={generate}
                loading={loading}
                message={message}
                selected={selected}
              />

              {projects.length > 0 && (
                <section className="recent-projects">
                  <div className="section-heading">
                    <div>
                      <span className="section-kicker">
                        WORKSPACE
                      </span>

                      <h2>Projets récents</h2>
                    </div>

                    <span className="section-count">
                      {projects.length} projet
                      {projects.length > 1
                        ? "s"
                        : ""}
                    </span>
                  </div>

                  <div className="project-grid">
                    {projects.map((project) => {
                      const versions = getProjectVersions(project);
                      const currentVersion =
                        versions.find(
                          (version) =>
                            version.version ===
                            project.current_version
                        ) || versions[0];

                      return (
                        <button
                          className="project-card"
                          key={project.id}
                          onClick={() =>
                            openProject(project)
                          }
                        >
                          <div className="project-card-preview">
                            {currentVersion?.html ? (
                              <iframe
                                title={`Aperçu de ${project.name}`}
                                srcDoc={currentVersion.html}
                                sandbox="allow-scripts"
                                tabIndex={-1}
                              />
                            ) : (
                              <div className="project-card-empty-preview">
                                <span>✦</span>
                                Aperçu indisponible
                              </div>
                            )}
                          </div>

                          <div className="project-card-footer">
                            <div>
                              <h3>{project.name}</h3>

                              <span>
                                {project.type} · v
                                {project.current_version}
                              </span>
                            </div>

                            <span className="arrow">
                              ↗
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </section>
              )}

              {projects.length === 0 && (
                <div className="empty-workspace">
                  <div className="empty-icon">
                    ✦
                  </div>

                  <h2>
                    Ton atelier est prêt.
                  </h2>

                  <p>
                    Commence par décrire l'interface que
                    tu veux créer.
                  </p>
                </div>
              )}
            </section>
          ) : (
            <section className="editor">
              <div className="editor-toolbar">
                <div>
                  <div className="mode-badge update">
                    <span>↗</span>
                    UPDATE
                  </div>

                  <div className="editor-title-row">
                    <h1>{selected.name}</h1>

                    <button
                      type="button"
                      className="editor-rename-button"
                      onClick={() => openRenameProject(selected)}
                      disabled={loading}
                      aria-label={`Modifier le nom du projet ${selected.name}`}
                      title="Modifier le nom du projet"
                    >
                      <span aria-hidden="true">✎</span>
                      Renommer
                    </button>
                  </div>

                  <p className="editor-description">
                    Modifie cette interface sans perdre
                    son identité existante.
                  </p>
                </div>

                <div className="editor-toolbar-actions">
                  <div className="editor-meta">
                    <span>
                      Version{" "}
                      {selectedVersion ||
                        selected.current_version}
                    </span>

                    <span className="meta-separator">
                      •
                    </span>

                    <span>Web</span>
                  </div>

                  <div className="editor-action-row">
                    <button
                      type="button"
                      className="editor-download-button"
                      onClick={downloadCurrentVersionZip}
                      disabled={loading || !selectedVersion}
                      aria-label={`Télécharger la version ${selectedVersion} de ${selected.name} en ZIP`}
                    >
                      <span aria-hidden="true">↓</span>
                      Télécharger le ZIP
                    </button>

                    <button
                      type="button"
                      className="editor-delete-button"
                      onClick={() => setDeleteCandidate(selected)}
                      disabled={loading}
                      aria-label={`Supprimer le projet ${selected.name}`}
                    >
                      <span aria-hidden="true">⌫</span>
                      Supprimer le projet
                    </button>
                  </div>
                </div>
              </div>

              <Composer
                mode="update"
                prompt={prompt}
                setPrompt={setPrompt}
                generate={generate}
                loading={loading}
                message={message}
                selected={selected}
              />

              <div className="canvas">
                <div className="canvas-top">
                  <span>DESIGN CANVAS</span>

                  <div className="canvas-controls">
                    <button
                      className={`canvas-control ${
                        previewMode === "desktop"
                          ? "active"
                          : ""
                      }`}
                      onClick={() => changePreviewMode("desktop")}
                    >
                      Desktop
                    </button>

                    <button
                      className={`canvas-control ${
                        previewMode === "mobile"
                          ? "active"
                          : ""
                      }`}
                      onClick={() => changePreviewMode("mobile")}
                    >
                      Mobile
                    </button>

                    <button
                      type="button"
                      className="canvas-control canvas-fullscreen-control"
                      onClick={enterPreviewFullscreen}
                      aria-label="Afficher l'interface en plein écran"
                      title="Visualiser en plein écran"
                    >
                      ⛶ <span>Visualiser</span>
                    </button>
                  </div>
                </div>

                <div
                  className={`preview-stage ${
                    previewMode === "mobile"
                      ? "mobile-mode"
                      : "desktop-mode"
                  }`}
                >
                  <div
                    className={`preview ${
                      previewMode === "mobile"
                        ? "preview-mobile"
                        : "preview-desktop"
                    }`}
                  >
                    <iframe
                      key={`${selected?.id || "new"}-${selectedVersion || "current"}-${previewMode}-${previewNonce}`}
                      title="Project preview"
                      srcDoc={preview}
                    />
                  </div>
                {previewFullscreen && (
                  <div
                    ref={previewFullscreenRef}
                    className="preview-fullscreen-overlay"
                    style={{
                      position: "fixed",
                      inset: 0,
                      zIndex: 9999,
                      background: "#ffffff",
                      display: "flex",
                      flexDirection: "column",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        height: 52,
                        minHeight: 52,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "0 18px",
                        borderBottom: "1px solid #e5e7eb",
                        background: "#ffffff",
                      }}
                    >
                      <strong style={{ fontSize: 13 }}>
                        Visualisation · {selected?.name}
                      </strong>
                      <button
                        type="button"
                        onClick={exitPreviewFullscreen}
                        style={{
                          border: "1px solid #d1d5db",
                          background: "#ffffff",
                          borderRadius: 8,
                          padding: "7px 11px",
                          cursor: "pointer",
                          fontSize: 13,
                        }}
                      >
                        ✕ Quitter
                      </button>
                    </div>

                    <div
                      style={{
                        flex: 1,
                        minHeight: 0,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        overflow: "auto",
                        background: "#f4f5f7",
                      }}
                    >
                      <div
                        style={{
                          width: previewMode === "mobile" ? 390 : "100%",
                          height: "100%",
                          maxWidth: previewMode === "mobile" ? 390 : "100%",
                          background: "#ffffff",
                          boxShadow:
                            previewMode === "mobile"
                              ? "0 12px 40px rgba(0,0,0,0.14)"
                              : "none",
                        }}
                      >
                        <iframe
                          key={`fullscreen-${selected?.id || "new"}-${selectedVersion || "current"}-${previewMode}-${previewNonce}`}
                          title="Project preview en plein écran"
                          srcDoc={preview}
                          style={{
                            width: "100%",
                            height: "100%",
                            border: 0,
                            display: "block",
                          }}
                        />
                      </div>
                    </div>
                  </div>
                )}

                </div>
              </div>

            </section>
          )}
        </div>
      </section>

      {loading && (
        <div
          className="generation-overlay"
          role="status"
          aria-live="polite"
          aria-label="Génération en cours"
        >
          <div className="generation-panel">
            <div className="generation-kicker">
              DESIGN AI
            </div>

            <h2>Génération en cours</h2>

            <p>
              Veuillez patienter pendant la préparation de votre interface.
            </p>

            <div className="generation-estimate">
              Estimation basée sur {effectiveGenerationTimes.length} génération{effectiveGenerationTimes.length > 1 ? "s" : ""}
              {effectiveGenerationTimes.length > 0
                ? ` · moyenne ${generationAverageSeconds}s`
                : " · première génération"}
            </div>

            <div className="generation-progress-row">
              <div className="generation-progress-track">
                <div
                  className="generation-progress-fill"
                  style={{ width: `${generationProgress}%` }}
                />
              </div>

              <strong>{Math.round(generationProgress)}%</strong>
            </div>

            <span className="generation-note">
              L’interface sera de nouveau accessible
              dès que la génération sera terminée.
            </span>
          </div>
        </div>
      )}

      {renameCandidate && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeRenameProject();
            }
          }}
        >
          <div className="modal rename-modal">
            <div className="modal-icon rename-icon">✎</div>

            <p className="section-kicker">
              PROJET
            </p>

            <h2>Renommer le projet</h2>

            <p>
              Choisis un nom clair pour retrouver facilement
              ce projet dans ton workspace.
            </p>

            <input
              className="rename-input"
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  confirmRename();
                }
                if (event.key === "Escape") {
                  closeRenameProject();
                }
              }}
              maxLength={100}
              autoFocus
              disabled={renaming}
              aria-label="Nouveau nom du projet"
            />

            <div className="modal-actions">
              <button
                className="ghost"
                onClick={closeRenameProject}
                disabled={renaming}
              >
                Annuler
              </button>

              <button
                className="primary-modal-action"
                onClick={confirmRename}
                disabled={renaming || !renameValue.trim()}
              >
                {renaming ? "Enregistrement..." : "Enregistrer"}
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteCandidate && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="modal-icon">!</div>

            <p className="section-kicker">
              CONFIRMATION
            </p>

            <h2>
              Supprimer le projet ?
            </h2>

            <p>
              Tu es sur le point de supprimer{" "}
              <strong>
                {deleteCandidate.name}
              </strong>
              . Cette action supprimera également
              ses versions.
            </p>

            <div className="modal-actions">
              <button
                className="ghost"
                onClick={() =>
                  setDeleteCandidate(null)
                }
              >
                Annuler
              </button>

              <button
                className="danger"
                onClick={confirmDelete}
              >
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function Composer({
  mode,
  prompt,
  setPrompt,
  projectTitle,
  setProjectTitle,
  generate,
  loading,
  message,
  selected,
}) {
  const isUpdate = mode === "update";

  return (
    <section
      className={`composer ${
        isUpdate
          ? "composer-update"
          : "composer-create"
      }`}
    >
      <div className="composer-top">
        <div className="composer-title">
          <span className="composer-spark">
            {isUpdate ? "↗" : "✦"}
          </span>

          <div>
            <strong>
              {isUpdate
                ? "Modifier le design"
                : "Commence par une idée"}
            </strong>

            <small>
              {isUpdate
                ? `Modification de ${selected.name}`
                : "Nouvelle création"}
            </small>
          </div>
        </div>

        <div
          className={`composer-mode ${
            isUpdate ? "update" : "create"
          }`}
        >
          {isUpdate ? "UPDATE" : "CREATE"}
        </div>
      </div>

      {!isUpdate && (
        <input
          className="composer-title-input"
          type="text"
          value={projectTitle}
          onChange={(e) => setProjectTitle(e.target.value)}
          placeholder="Titre du projet *"
          aria-label="Titre du projet obligatoire"
          aria-required="true"
          required
          maxLength={100}
        />
      )}

      <textarea
        value={prompt}
        onChange={(e) =>
          setPrompt(e.target.value)
        }
        onKeyDown={(e) => {
          if (
            (e.metaKey || e.ctrlKey) &&
            e.key === "Enter"
          ) {
            generate();
          }
        }}
        placeholder={
          isUpdate
            ? "Ex. Rends le hero plus minimaliste, augmente l'espace entre les éléments..."
            : "Ex. Crée une landing page pour un studio de design spécialisé dans l'IA..."
        }
      />

      <div className="composer-footer">
        <div className="composer-hint">
          {message ? (
            <span className="composer-message">
              {message}
            </span>
          ) : (
            <>
              <span>⌘</span>
              <span>Enter</span>
              <span className="hint-text">
                pour générer
              </span>
            </>
          )}
        </div>

        <button
          className="generate-button"
          onClick={generate}
          disabled={
            loading ||
            !prompt.trim() ||
            (!isUpdate && !projectTitle.trim())
          }
        >
          {loading ? (
            <>
              <span className="spinner" />
              Génération...
            </>
          ) : (
            <>
              {isUpdate
                ? "Appliquer"
                : "Créer le projet"}

              <span>↗</span>
            </>
          )}
        </button>
      </div>
    </section>
  );
}