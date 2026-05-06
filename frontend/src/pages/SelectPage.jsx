import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { usePassport } from "@/context/PassportContext";
import { TeacherIcon, ChartIcon, ScanIcon } from "@/components/icons";
import { getStudent, listStudents, deleteStudent, createGuestStudent } from "@/lib/api";

const LOGO_URL = "https://birdeo.com/wp-content/uploads/2024/11/LOGo-letudiant.jpg";

export default function SelectPage() {
  const navigate = useNavigate();
  const { selectStudent, clear } = usePassport();
  const [loading, setLoading] = useState("");
  const [created, setCreated] = useState([]);
  const [refreshing, setRefreshing] = useState(true);
  const [guestCreating, setGuestCreating] = useState(false);

  const refresh = async () => {
    setRefreshing(true);
    try {
      const list = await listStudents(false);
      setCreated(list);
    } catch {
      setCreated([]);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const loadProfile = async (id) => {
    setLoading(id);
    try {
      await getStudent(id);
      selectStudent(id);
      navigate("/passport/cover");
    } catch (e) {
      alert("Profil introuvable.");
    } finally {
      setLoading("");
    }
  };

  const removeProfile = async (e, id, name) => {
    e.stopPropagation();
    if (!window.confirm(`Supprimer le profil de ${name || "cet élève"} ?`)) return;
    try {
      await deleteStudent(id);
      setCreated((arr) => arr.filter((s) => s.id !== id));
    } catch {
      alert("Impossible de supprimer.");
    }
  };

  const reset = () => {
    clear();
    try {
      localStorage.clear();
    } catch {}
    refresh();
  };

  const startGuest = async () => {
    setGuestCreating(true);
    try {
      const guest = await createGuestStudent();
      selectStudent(guest.id);
      navigate("/passport/stamps");
    } catch {
      alert("Impossible de lancer le mode invité.");
    } finally {
      setGuestCreating(false);
    }
  };

  return (
    <div className="pe-shell">
      <div className="device">
        <div className="top-bar">
          <img src={LOGO_URL} alt="l'Étudiant" className="logo-img" />
          <div style={{ flex: 1 }} />
          <div className="tb-chip">PasseportEtudiant</div>
        </div>
        <div className="scroll-body">
          <motion.div
            className="sel-hero"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.2, 0.8, 0.2, 1] }}
          >
            <div className="sel-hero-text">
              <div className="sel-hero-eyebrow">Salon · Orientation</div>
              <div className="sel-hero-title">
                Salon de
                <br />
                l'Orientation 2026
              </div>
              <div className="sel-hero-sub">
                Choisis un profil démo ou active ton propre PasseportEtudiant.
              </div>
            </div>
            <motion.div
              className="sel-passport-mini"
              initial={{ rotate: -8, scale: 0.9, opacity: 0 }}
              animate={{ rotate: -2, scale: 1, opacity: 1 }}
              transition={{ delay: 0.15, type: "spring", stiffness: 140, damping: 14 }}
            >
              <svg width="30" height="22" viewBox="0 0 26 20" fill="none">
                <rect x="1" y="1" width="24" height="18" rx="2" stroke="rgba(255,255,255,.7)" strokeWidth="1.2" />
                <circle cx="8.5" cy="8" r="3.5" stroke="rgba(255,255,255,.55)" strokeWidth="1" />
                <line x1="14" y1="6" x2="22" y2="6" stroke="rgba(255,255,255,.5)" strokeWidth="1" />
                <line x1="14" y1="10" x2="20" y2="10" stroke="rgba(255,255,255,.35)" strokeWidth="1" />
                <line x1="3" y1="15.5" x2="23" y2="15.5" stroke="rgba(255,255,255,.3)" strokeWidth="1" />
                <line x1="3" y1="18" x2="18" y2="18" stroke="rgba(255,255,255,.2)" strokeWidth="1" />
              </svg>
              <div className="spm-label">Passeport</div>
            </motion.div>
          </motion.div>

          <motion.div
            className="create-card"
            onClick={() => navigate("/create")}
            initial={{ y: 14, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1, duration: 0.4 }}
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.98 }}
            data-testid="btn-activate-passport"
          >
            <div className="cc-icon">＋</div>
            <div>
              <div className="cc-name">Activer mon PasseportEtudiant</div>
              <div className="cc-desc">
                Crée ton profil en 60s avec le code professeur
              </div>
            </div>
          </motion.div>

          <motion.div
            className="create-card guest-card"
            onClick={startGuest}
            initial={{ y: 14, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.16, duration: 0.4 }}
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.98 }}
            data-testid="btn-start-guest"
          >
            <div className="cc-icon">◎</div>
            <div>
              <div className="cc-name">{guestCreating ? "Ouverture..." : "Essayer sans compte"}</div>
              <div className="cc-desc">
                Scanner les stands, voir son dashboard, laisser ses infos à la fin
              </div>
            </div>
          </motion.div>

          <div className="entry-grid">
            <button
              className="entry-btn"
              onClick={() => navigate("/teacher")}
              data-testid="entry-teacher"
            >
              <TeacherIcon />
              <div className="eb-title">Espace professeur</div>
              <div className="eb-sub">
                Créer un code classe, voir mes élèves
              </div>
            </button>
            <button
              className="entry-btn"
              onClick={() => navigate("/analytics")}
              data-testid="entry-analytics"
            >
              <ChartIcon />
              <div className="eb-title">Dashboard salon</div>
              <div className="eb-sub">
                Stats temps réel · l'Étudiant
              </div>
            </button>
            <button
              className="entry-btn"
              onClick={() => navigate("/demo-qr")}
              data-testid="entry-demo-qr"
            >
              <ScanIcon />
              <div className="eb-title">QR codes demo</div>
              <div className="eb-sub">Albert / EPITA / Mines</div>
            </button>
          </div>

          {created.length > 0 && (
            <>
              <div className="sel-label" style={{ display: "flex", alignItems: "center" }}>
                <span>Profils activés ({created.length})</span>
                <div style={{ flex: 1 }} />
                <button
                  onClick={refresh}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#aaa",
                    fontSize: 11,
                    fontWeight: 800,
                    letterSpacing: "0.1em",
                    cursor: "pointer",
                  }}
                  data-testid="btn-refresh-profiles"
                >
                  {refreshing ? "…" : "↻"}
                </button>
              </div>
              <AnimatePresence>
                {created.map((s) => (
                  <motion.div
                    key={s.id}
                    layout
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    transition={{ duration: 0.25 }}
                    className="sel-row"
                    onClick={() => loadProfile(s.id)}
                    data-testid={`profile-${s.id}`}
                  >
                    <div
                      className="sr-avatar"
                      style={{ background: "#fff0f0" }}
                    >
                      {s.emoji || "🧑"}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="sr-name">{s.name || "Élève"}</div>
                      <div className="sr-desc">
                        {s.classe}
                        {s.filieres?.length > 0 ? ` · ${s.filieres.join(", ")}` : ""}
                        {typeof s.stamp_count === "number"
                          ? ` · ${s.stamp_count} tampon${s.stamp_count > 1 ? "s" : ""}`
                          : ""}
                      </div>
                    </div>
                    <button
                      onClick={(e) => removeProfile(e, s.id, s.name)}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#ddd",
                        fontSize: 18,
                        cursor: "pointer",
                        padding: "4px 8px",
                      }}
                      title="Supprimer ce profil"
                      data-testid={`btn-delete-${s.id}`}
                    >
                      ×
                    </button>
                    <span style={{ color: "#ddd", fontSize: 20 }}>
                      {loading === s.id ? "…" : "›"}
                    </span>
                  </motion.div>
                ))}
              </AnimatePresence>
            </>
          )}

          <div className="sel-label">Profils de démonstration</div>

          <div
            className="sel-row"
            onClick={() => loadProfile("demo-lucas")}
            data-testid="demo-lucas"
          >
            <div className="sr-avatar" style={{ background: "#fff0f0" }}>
              🎓
            </div>
            <div style={{ flex: 1 }}>
              <div className="sr-name">Lucas, 17 ans</div>
              <div className="sr-desc">
                Lycéen intentionniste · Venu seul · Ingénierie
              </div>
            </div>
            <span style={{ color: "#ddd", fontSize: 20 }}>
              {loading === "demo-lucas" ? "…" : "›"}
            </span>
          </div>

          <div
            className="sel-row"
            onClick={() => loadProfile("demo-theo")}
            data-testid="demo-theo"
          >
            <div className="sr-avatar" style={{ background: "#f5f5f5" }}>
              👥
            </div>
            <div style={{ flex: 1 }}>
              <div className="sr-name">Théo, 16 ans</div>
              <div className="sr-desc">
                Groupe scolaire anonyme · sans profil individuel
              </div>
            </div>
            <span style={{ color: "#ddd", fontSize: 20 }}>
              {loading === "demo-theo" ? "…" : "›"}
            </span>
          </div>

          <div className="sel-footer">
            Prototype · Albert School × l'Étudiant · 2026
            <div>
              <button
                className="reset-btn"
                onClick={reset}
                data-testid="btn-reset-session"
              >
                Réinitialiser la session
              </button>
              <button
                className="reset-btn"
                onClick={() => navigate("/admin")}
                style={{ marginLeft: 6 }}
                data-testid="btn-admin"
              >
                🔐 Admin
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
