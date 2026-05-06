import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { usePassport } from "@/context/PassportContext";
import BottomNav from "@/components/BottomNav";
import Toast from "@/components/Toast";
import { BackIcon } from "@/components/icons";
import { getRecap, getLeaderboard, claimGuestStudent } from "@/lib/api";
import { downloadBadge, shareBadge } from "@/lib/badge";

export default function RecapPage() {
  const navigate = useNavigate();
  const { student, setStudent, loading } = usePassport();
  const [recap, setRecap] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [toast, setToast] = useState({ msg: "", type: "ok" });
  const [busy, setBusy] = useState(false);
  const [claimForm, setClaimForm] = useState({ first_name: "", last_name: "", email: "" });
  const [claiming, setClaiming] = useState(false);

  useEffect(() => {
    if (!student) return;
    getRecap(student.id).then(setRecap).catch(() => setRecap(null));
    getLeaderboard().then(setLeaderboard).catch(() => setLeaderboard([]));
  }, [student]);

  if (!student && !loading) {
    navigate("/", { replace: true });
    return null;
  }
  if (!student) return null;

  const isAnon = student.is_anonymous;
  const done = recap?.stamps?.length || 0;
  const score = recap?.score || 0;

  const badgeData = {
    name: student.name,
    serial: student.serial,
    score,
    stamps: done,
    filiere: (student.filieres && student.filieres[0]) || null,
    schools: (recap?.stamps || []).map((s) => s.school_name),
  };

  const onDownloadBadge = async () => {
    setBusy(true);
    try {
      await downloadBadge(badgeData);
      setToast({ msg: "✓ Badge téléchargé !", type: "ok" });
    } catch (e) {
      setToast({ msg: "Impossible de générer le badge", type: "err" });
    } finally {
      setBusy(false);
    }
  };

  const onShareBadge = async () => {
    setBusy(true);
    try {
      const shared = await shareBadge(badgeData);
      setToast({
        msg: shared ? "✓ Partagé !" : "✓ Badge téléchargé (partage indisponible)",
        type: "ok",
      });
    } catch (e) {
      setToast({ msg: "Impossible de partager", type: "err" });
    } finally {
      setBusy(false);
    }
  };

  const myClassCode = student.class_code;
  const myRank = myClassCode
    ? leaderboard.find((r) => r.code === myClassCode)?.rank
    : null;
  const shouldShowGuestClaim = student.is_guest && !student.guest_claimed;

  const onClaimGuest = async () => {
    setClaiming(true);
    try {
      const updated = await claimGuestStudent(student.id, claimForm);
      setStudent(updated);
      setToast({ msg: "✓ Dashboard enregistré et prêt à être envoyé", type: "ok" });
    } catch (e) {
      setToast({
        msg: e?.response?.data?.detail || "Impossible d'enregistrer tes coordonnées",
        type: "err",
      });
    } finally {
      setClaiming(false);
    }
  };

  return (
    <div className="pe-shell">
      <div className="device">
        <div className="top-bar">
          <button
            className="tb-back"
            onClick={() => navigate("/passport/stamps")}
            data-testid="btn-back"
          >
            <BackIcon />
          </button>
          <div className="tb-title">Récap post-salon</div>
          <div className="tb-chip">3 / 3</div>
        </div>
        <div className="rh">
          <div className="rht">
            <div>
              <div className="rhn">{student.name || "—"}</div>
              <div className="rhd">Paris · 15 avril 2026</div>
            </div>
          </div>
          <div className="rhs">
            <div className="rstat">
              <div className="rsn">{done}</div>
              <div className="rsl">Tampons</div>
            </div>
            <div className="rstat">
              <div className="rsn">
                {isAnon || done === 0 ? "—" : `${recap?.duration_min || 0}m`}
              </div>
              <div className="rsl">Durée</div>
            </div>
            <div className="rstat">
              <div className="rsn">
                {isAnon ? "—" : student.consents?.d ? "✓" : "✗"}
              </div>
              <div className="rsl">Diplomeo</div>
            </div>
          </div>
        </div>
        <div className="rscroll">
          {shouldShowGuestClaim ? (
            <div className="guest-claim-card" data-testid="guest-claim-card">
              <div className="guest-claim-kicker">Mode invité</div>
              <div className="guest-claim-title">Recevoir mon dashboard</div>
              <div className="guest-claim-text">
                Tu peux tester sans compte. Si ton récap t'intéresse, laisse tes coordonnées
                pour recevoir tes visites et recommandations.
              </div>
              <div className="guest-claim-grid">
                <input
                  className="fi"
                  value={claimForm.first_name}
                  onChange={(e) => setClaimForm({ ...claimForm, first_name: e.target.value })}
                  placeholder="Prénom"
                  data-testid="guest-firstname"
                />
                <input
                  className="fi"
                  value={claimForm.last_name}
                  onChange={(e) => setClaimForm({ ...claimForm, last_name: e.target.value })}
                  placeholder="Nom"
                  data-testid="guest-lastname"
                />
              </div>
              <input
                className="fi"
                value={claimForm.email}
                onChange={(e) => setClaimForm({ ...claimForm, email: e.target.value })}
                placeholder="Adresse mail"
                type="email"
                data-testid="guest-email"
              />
              <button
                className="sub-btn"
                onClick={onClaimGuest}
                disabled={claiming}
                data-testid="btn-claim-guest"
              >
                {claiming ? "Envoi..." : "M'envoyer mon dashboard"}
              </button>
            </div>
          ) : student.is_guest && student.guest_claimed ? (
            <div className="guest-claim-card done">
              <div className="guest-claim-kicker">Dashboard sauvegardé</div>
              <div className="guest-claim-text">
                Tes données de visite sont rattachées à {student.email}. L'équipe peut te
                renvoyer ton récap après la démo.
              </div>
            </div>
          ) : null}

          {isAnon ? (
            <>
              <div className="es">
                <div className="es-i">📭</div>
                <div className="es-t">Aucun récap disponible</div>
                <div className="es-s">
                  L'Étudiant ne sait pas que Théo était au salon. Pas de profil,
                  pas de tampon, pas de recommandation.
                </div>
              </div>
              <div className="sol-card">
                <div className="sol-title">✓ Ce que Théo aurait reçu</div>
                <div className="sol-text">
                  Un récap personnalisé avec les établissements visités, un
                  score d'exploration et les prochaines JPO.
                </div>
              </div>
              <button
                className="swb"
                onClick={() => navigate("/")}
                data-testid="btn-back-select"
              >
                ← Tester le profil de Lucas
              </button>
            </>
          ) : done < 3 ? (
            <>
              <div className="uh" data-testid="recap-unlock">
                <div style={{ fontSize: 30 }}>🗺️</div>
                <div className="uh-t">Explore encore le salon</div>
                <div className="uh-s">
                  Visite{" "}
                  <strong>
                    {3 - done} établissement{3 - done > 1 ? "s" : ""}
                  </strong>{" "}
                  supplémentaire{3 - done > 1 ? "s" : ""} pour débloquer tes
                  recommandations.
                </div>
              </div>
              <button
                className="swb"
                onClick={() => navigate("/passport/stamps")}
              >
                Aller tamponner →
              </button>
            </>
          ) : (
            <>
              <motion.div
                initial="hidden"
                animate="show"
                variants={{
                  hidden: {},
                  show: { transition: { staggerChildren: 0.07 } },
                }}
              >
                <div className="rsec">Établissements recommandés</div>
                {(recap?.recos || []).map((r, i) => (
                  <motion.div
                    key={i}
                    className="rc"
                    variants={{
                      hidden: { opacity: 0, y: 10 },
                      show: { opacity: 1, y: 0 },
                    }}
                    data-testid={`reco-${i}`}
                  >
                    <div className="rct">
                      <div>
                        <div className="rcn">{r.name}</div>
                        <div className="rcy">{r.type}</div>
                      </div>
                      <div className={`rcb ${r.t ? "t" : ""}`}>{r.m}%</div>
                    </div>
                    <div className="rctr">
                      <motion.div
                        className={`rcf ${r.t ? "t" : ""}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${r.m}%` }}
                        transition={{ delay: 0.2 + i * 0.08, duration: 0.7 }}
                      />
                    </div>
                    {r.why && r.why.length > 0 && (
                      <div
                        style={{
                          marginTop: 8,
                          fontSize: 10.5,
                          color: "#999",
                          display: "flex",
                          flexWrap: "wrap",
                          gap: 4,
                        }}
                      >
                        {r.why.map((w, j) => (
                          <span
                            key={j}
                            style={{
                              background: "#f5f4ef",
                              padding: "2px 8px",
                              borderRadius: 99,
                              fontWeight: 600,
                            }}
                          >
                            {w}
                          </span>
                        ))}
                      </div>
                    )}
                  </motion.div>
                ))}
              </motion.div>

              <div>
                <div className="rsec">Prochaines étapes</div>
                {(recap?.next || []).map((n, i) => (
                  <motion.div
                    key={i}
                    className="nc"
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 + i * 0.05 }}
                  >
                    <div className="nd" style={{ background: n.c }} />
                    <div>
                      <div className="nt">{n.t}</div>
                      <div className="nd2">{n.d}</div>
                    </div>
                  </motion.div>
                ))}
              </div>

              <div>
                <div className="rsec">Données capturées</div>
                <div className="db">
                  {done} établissement{done > 1 ? "s" : ""} visité
                  {done > 1 ? "s" : ""}
                  <br />
                  Filière : {student.filieres?.[0] || "non renseignée"}
                  <br />
                  Diplomeo : {student.consents?.d ? "Actif" : "Inactif"}
                </div>
              </div>

              {recap?.badges && (
                <div>
                  <div className="rsec">
                    Badges débloqués · {recap.badges.length}/{recap.all_badges.length}
                  </div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(3, 1fr)",
                      gap: 8,
                    }}
                  >
                    {recap.all_badges.map((b) => {
                      const got = recap.badges.some((ub) => ub.id === b.id);
                      return (
                        <motion.div
                          key={b.id}
                          initial={{ scale: got ? 0.6 : 1, opacity: 0 }}
                          animate={{ scale: 1, opacity: 1 }}
                          transition={{ type: "spring", stiffness: 200, damping: 14 }}
                          style={{
                            background: got ? "white" : "#f5f4ef",
                            border: got ? "1.5px solid var(--red)" : "1.5px solid #eee",
                            borderRadius: 12,
                            padding: "10px 6px",
                            textAlign: "center",
                            opacity: got ? 1 : 0.45,
                            position: "relative",
                          }}
                          data-testid={`badge-${b.id}`}
                        >
                          <div style={{ fontSize: 26, marginBottom: 4 }}>{b.icon}</div>
                          <div style={{ fontSize: 11, fontWeight: 800, color: "var(--ink)" }}>
                            {b.label}
                          </div>
                          <div style={{ fontSize: 9.5, color: "#999", marginTop: 2, lineHeight: 1.3 }}>
                            {b.desc}
                          </div>
                          {got && (
                            <div
                              style={{
                                position: "absolute",
                                top: 4,
                                right: 4,
                                background: "var(--red)",
                                color: "white",
                                fontSize: 9,
                                fontWeight: 800,
                                padding: "1px 6px",
                                borderRadius: 99,
                              }}
                            >
                              ✓
                            </div>
                          )}
                        </motion.div>
                      );
                    })}
                  </div>
                  {recap.badges.length === recap.all_badges.length ? (
                    <div
                      style={{
                        background: "linear-gradient(90deg, #fbbf24, #f59e0b)",
                        color: "white",
                        padding: "10px 14px",
                        borderRadius: 12,
                        marginTop: 8,
                        fontSize: 12,
                        fontWeight: 800,
                        textAlign: "center",
                      }}
                    >
                      🏆 Tu as tout débloqué — tu rentres au tirage Salon Étudiant Major
                    </div>
                  ) : null}
                </div>
              )}

              {leaderboard.length > 0 && (
                <div>
                  <div className="rsec">
                    Classement des classes
                    {myRank ? (
                      <span
                        style={{
                          marginLeft: 8,
                          background: "var(--red)",
                          color: "white",
                          padding: "2px 9px",
                          borderRadius: 99,
                          fontSize: 10,
                          letterSpacing: "0.08em",
                        }}
                      >
                        TA CLASSE : #{myRank}
                      </span>
                    ) : null}
                  </div>
                  {leaderboard.slice(0, 5).map((row) => {
                    const mine = row.code === myClassCode;
                    return (
                      <div
                        key={row.code}
                        className="rc"
                        style={{
                          borderColor: mine ? "var(--red)" : "#eee",
                          background: mine ? "#fff8f8" : "#fff",
                        }}
                        data-testid={`leaderboard-row-${row.code}`}
                      >
                        <div className="rct" style={{ marginBottom: 4 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                            <div
                              style={{
                                fontWeight: 900,
                                color: row.rank === 1 ? "#d97706" : row.rank === 2 ? "#6b7280" : row.rank === 3 ? "#b45309" : "#aaa",
                                fontSize: 18,
                                width: 28,
                              }}
                            >
                              #{row.rank}
                            </div>
                            <div style={{ minWidth: 0 }}>
                              <div className="rcn" style={{ fontSize: 13 }}>
                                {row.school_name}
                                {mine ? " — toi" : ""}
                              </div>
                              <div className="rcy">
                                {row.students} élève{row.students > 1 ? "s" : ""} · {row.stamps} tampons
                              </div>
                            </div>
                          </div>
                          <div className={`rcb ${mine ? "t" : ""}`}>{row.avg}/élève</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              <div>
                <div className="rsec">Ton badge à partager</div>
                <div
                  style={{
                    background: "linear-gradient(135deg, #1A237E 0%, #2a35a0 100%)",
                    borderRadius: 16,
                    padding: 20,
                    color: "white",
                    position: "relative",
                    overflow: "hidden",
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", opacity: 0.5, marginBottom: 6 }}>
                    J'ÉTAIS AU SALON ORIENTATION 2026
                  </div>
                  <div style={{ fontSize: 22, fontWeight: 900, letterSpacing: "-0.01em", marginBottom: 12 }}>
                    {student.name}
                  </div>
                  <div style={{ display: "flex", gap: 18, alignItems: "center" }}>
                    <div
                      style={{
                        width: 70,
                        height: 70,
                        borderRadius: "50%",
                        border: "3px solid var(--red)",
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "var(--red)",
                        fontWeight: 900,
                        fontSize: 22,
                        background: "rgba(255,255,255,0.06)",
                      }}
                    >
                      {done}
                      <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.04em", opacity: 0.7 }}>stands</span>
                    </div>
                    <div style={{ flex: 1, lineHeight: 1.5, fontSize: 13, opacity: 0.85 }}>
                      {done} établissement{done > 1 ? "s" : ""} visité{done > 1 ? "s" : ""}
                      <br />
                      Filière : {student.filieres?.[0] || "—"}
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                  <button
                    className="swb"
                    onClick={onShareBadge}
                    disabled={busy}
                    style={{ background: "var(--red)", flex: 1 }}
                    data-testid="btn-share-badge"
                  >
                    {busy ? "…" : "Partager"}
                  </button>
                  <button
                    className="swb"
                    onClick={onDownloadBadge}
                    disabled={busy}
                    style={{ flex: 1 }}
                    data-testid="btn-download-badge"
                  >
                    {busy ? "…" : "Télécharger"}
                  </button>
                </div>
              </div>

              <button
                className="swb"
                onClick={() => navigate("/")}
                data-testid="btn-back-select"
                style={{ background: "#f5f5f5", color: "var(--ink)" }}
              >
                ← Tester un autre profil
              </button>
            </>
          )}
        </div>
        <BottomNav />
        <Toast
          message={toast.msg}
          type={toast.type}
          onClose={() => setToast({ msg: "", type: "ok" })}
        />
      </div>
    </div>
  );
}

