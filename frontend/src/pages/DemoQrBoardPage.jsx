import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { DEMO_QR_BOOTHS, DEMO_QR_STUDENT_ID, buildDemoScanUrl } from "@/lib/demoQr";
import { deleteStamp, getSchools, getStamps } from "@/lib/api";

const LOGO_URL = "https://birdeo.com/wp-content/uploads/2024/11/LOGo-letudiant.jpg";

export default function DemoQrBoardPage() {
  const navigate = useNavigate();
  const [schools, setSchools] = useState([]);
  const [stamps, setStamps] = useState([]);
  const [busy, setBusy] = useState(false);
  const origin = typeof window !== "undefined" ? window.location.origin : "";

  const reload = async () => {
    const [schoolRows, stampRows] = await Promise.all([
      getSchools(),
      getStamps(DEMO_QR_STUDENT_ID).catch(() => []),
    ]);
    setSchools(schoolRows);
    setStamps(stampRows);
  };

  useEffect(() => {
    reload().catch(() => {});
    const timer = setInterval(() => reload().catch(() => {}), 5000);
    return () => clearInterval(timer);
  }, []);

  const schoolById = useMemo(() => {
    const map = {};
    schools.forEach((school) => {
      map[school.id] = school;
    });
    return map;
  }, [schools]);

  const stampsBySchool = useMemo(() => {
    const map = {};
    stamps.forEach((stamp) => {
      map[stamp.school_id] = stamp;
    });
    return map;
  }, [stamps]);

  const resetDemoVisits = async () => {
    setBusy(true);
    try {
      const targetIds = new Set(DEMO_QR_BOOTHS.map((booth) => booth.schoolId));
      const targets = stamps.filter((stamp) => targetIds.has(stamp.school_id));
      await Promise.all(targets.map((stamp) => deleteStamp(stamp.id)));
      await reload();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="demoqr-shell">
      <div className="demoqr-head">
        <img src={LOGO_URL} alt="l'Etudiant" className="demoqr-logo" />
        <div>
          <div className="demoqr-title">QR codes demo stands</div>
          <div className="demoqr-sub">
            Open Lucas, scan these booth QR codes, and the status below turns visited.
          </div>
        </div>
        <div className="demoqr-actions">
          <button className="sub-btn ghost" onClick={() => navigate("/analytics")}>
            Dashboard
          </button>
          <button className="sub-btn ghost" onClick={() => navigate("/")}>
            Retour
          </button>
        </div>
      </div>

      <div className="demoqr-grid">
        {DEMO_QR_BOOTHS.map((booth) => {
          const school = schoolById[booth.schoolId];
          const stamp = stampsBySchool[booth.schoolId];
          const scanUrl = buildDemoScanUrl(origin, booth.schoolId);
          return (
            <div className={`demoqr-card ${stamp ? "visited" : ""}`} key={booth.schoolId}>
              <div className="demoqr-card-top">
                <div>
                  <div className="demoqr-label">{booth.label}</div>
                  <div className="demoqr-name">{school?.name || booth.schoolId}</div>
                </div>
                <div className={`demoqr-status ${stamp ? "ok" : ""}`}>
                  {stamp ? "Visited" : "Not scanned"}
                </div>
              </div>
              <div className="demoqr-code">
                <QRCodeSVG
                  value={scanUrl}
                  size={280}
                  level="H"
                  fgColor="#000000"
                  bgColor="#ffffff"
                  marginSize={4}
                />
              </div>
              <div className="demoqr-url">{scanUrl}</div>
              {stamp ? <div className="demoqr-time">Last scan: {stamp.time_label}</div> : null}
            </div>
          );
        })}
      </div>

      <div className="demoqr-foot">
        <button className="sub-btn" onClick={resetDemoVisits} disabled={busy}>
          {busy ? "Reset en cours..." : "Reset Lucas demo visits"}
        </button>
      </div>
    </div>
  );
}
