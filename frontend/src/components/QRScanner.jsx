import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Html5Qrcode } from "html5-qrcode";
import { getSchools } from "@/lib/api";
import { DEMO_QR_BOOTHS } from "@/lib/demoQr";

/**
 * QR scanner overlay. onResult(text) is called when a QR is decoded.
 * The camera path favors the rear camera and includes an image fallback for demos.
 */
export default function QRScanner({ open, onClose, onResult }) {
  const scannerRef = useRef(null);
  const onResultRef = useRef(onResult);
  const fileInputRef = useRef(null);
  const [error, setError] = useState("");
  const [schools, setSchools] = useState([]);

  useEffect(() => {
    onResultRef.current = onResult;
  }, [onResult]);

  useEffect(() => {
    if (!open) return;
    setError("");
    getSchools()
      .then(setSchools)
      .catch(() => setSchools([]));
  }, [open]);

  useEffect(() => {
    if (!open) return;

    let scanner;
    let stopped = false;
    const qrboxSize = Math.min(
      340,
      Math.max(260, Math.floor((window.innerWidth || 360) * 0.78))
    );
    const config = {
      fps: 15,
      qrbox: { width: qrboxSize, height: qrboxSize },
      disableFlip: false,
      experimentalFeatures: { useBarCodeDetectorIfSupported: true },
    };

    const handleSuccess = (decodedText) => {
      if (stopped) return;
      stopped = true;
      onResultRef.current?.(decodedText);
    };

    const tryStart = async (cameraConfig) => {
      await scanner.start(cameraConfig, config, handleSuccess, () => {});
    };

    const start = async () => {
      try {
        scanner = new Html5Qrcode("qr-reader", false);
        scannerRef.current = scanner;

        try {
          await tryStart({ facingMode: { exact: "environment" } });
          return;
        } catch {}

        try {
          await tryStart({ facingMode: "environment" });
          return;
        } catch {}

        const devices = await Html5Qrcode.getCameras().catch(() => []);
        const backCamera =
          devices.find((device) =>
            /back|rear|environment|arri/i.test(device.label || "")
          ) || devices[devices.length - 1];

        if (!backCamera) {
          setError("Aucune camera detectee. Utilisez la photo ou la selection demo.");
          return;
        }

        await tryStart(backCamera.id);
      } catch {
        setError("Camera indisponible. Utilisez la photo ou la selection demo ci-dessous.");
      }
    };

    start();
    return () => {
      stopped = true;
      (async () => {
        try {
          if (scannerRef.current) {
            const state = scannerRef.current.getState?.();
            if (state === 2) {
              await scannerRef.current.stop();
            }
            await scannerRef.current.clear();
          }
        } catch {}
        scannerRef.current = null;
      })();
    };
  }, [open]);

  const scanImageFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    try {
      let scanner = scannerRef.current;
      if (!scanner) {
        scanner = new Html5Qrcode("qr-reader", false);
        scannerRef.current = scanner;
      }

      const state = scanner.getState?.();
      if (state === 2) {
        await scanner.stop();
      }

      const decoded = await scanner.scanFile(file, true);
      onResultRef.current?.(decoded);
    } catch {
      setError("QR illisible sur cette image. Essayez avec le QR plus net et plus proche.");
    }
  };

  const demoSchoolIds = new Set(DEMO_QR_BOOTHS.map((booth) => booth.schoolId));
  const quickSchools = [
    ...schools.filter((school) => demoSchoolIds.has(school.id)),
    ...schools.filter((school) => !demoSchoolIds.has(school.id)),
  ].slice(0, 8);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="scanner-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          data-testid="qr-scanner-overlay"
        >
          <div className="scanner-top">
            <button onClick={onClose} data-testid="qr-scanner-close">
              Fermer
            </button>
            <div style={{ fontWeight: 800, fontSize: 15 }}>Scanner un stand</div>
          </div>

          <div className="scanner-video-wrap">
            <div id="qr-reader" />
            <div className="scanner-reticle" />
          </div>

          <div className="scanner-hint">
            {error ? (
              <span>{error}</span>
            ) : (
              <>
                Cadrez le <strong>QR code</strong> en entier, bien net, puis attendez
                une seconde.
              </>
            )}
          </div>

          <div className="scanner-tools">
            <button className="scanner-tool-btn" onClick={() => fileInputRef.current?.click()}>
              Importer une photo du QR
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={scanImageFile}
              style={{ display: "none" }}
            />
          </div>

          <div className="scanner-demo">
            <h4>Selection rapide demo</h4>
            <div className="scanner-demo-grid">
              {quickSchools.map((school) => (
                <button
                  key={school.id}
                  className="scanner-demo-btn"
                  onClick={() => onResultRef.current?.(school.qr_token)}
                  data-testid={`demo-stand-${school.id}`}
                >
                  {school.name}
                </button>
              ))}
            </div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
