import { useState, useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import { analyzeCode } from "./api";
import AuthSuccess from "./AuthSuccess";
import ScreenshotAnnotator from "./ScreenshotAnnotator";

/* ------------------------------
   GOOGLE LOGIN
-------------------------------- */
function loginWithGoogle() {
  window.location.href = "http://localhost:8000/auth/login";
}

/* ------------------------------
   HOME
-------------------------------- */
function Home() {
  const [code, setCode] = useState("");
  const [logs, setLogs] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  const [sessionId, setSessionId] = useState(null);
  const [joinSessionInput, setJoinSessionInput] = useState("");
  const [ws, setWs] = useState(null);

  const [screenshot, setScreenshot] = useState(null);
  const [loading, setLoading] = useState(false);

  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  });

  /* ------------------------------
     AUTH SYNC
  -------------------------------- */
  useEffect(() => {
    const syncAuth = () => {
      setToken(localStorage.getItem("token"));
      const raw = localStorage.getItem("user");
      setUser(raw ? JSON.parse(raw) : null);
    };
    window.addEventListener("storage", syncAuth);
    return () => window.removeEventListener("storage", syncAuth);
  }, []);

  /* ------------------------------
     WEBSOCKET RECONNECT
  -------------------------------- */
  useEffect(() => {
    if (!sessionId) return;
    if (!token && ws) {
      ws.close();
      setWs(null);
    }
    if (token && !ws) connectWebSocket(sessionId);
  }, [token]);

  /* ------------------------------
     COLLAB
  -------------------------------- */
  async function createSession() {
    const res = await fetch("http://localhost:8000/session", { method: "POST" });
    const data = await res.json();
    setSessionId(data.session_id);
    connectWebSocket(data.session_id);
  }

  function connectWebSocket(sid) {
    const socket = new WebSocket(`ws://localhost:8000/ws/session/${sid}`);
    socket.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "init") {
        setCode(msg.code);
        setLogs(msg.logs || "");
      }
      if (msg.type === "code_update") setCode(msg.code);
      if (msg.type === "logs_update") setLogs(msg.logs);
      if (msg.type === "analyze_result") {
        setResult(msg.result);
        addToHistory(msg.result);
      }
    };
    setWs(socket);
  }

  function addToHistory(res) {
    setHistory((prev) => [
      { timestamp: new Date().toLocaleString(), result: res },
      ...prev,
    ]);
  }

  /* ------------------------------
     ANALYZE
  -------------------------------- */
  async function handleAnalyze() {
    if (!token) return alert("Please sign in first");

    if (ws && sessionId) {
      ws.send(JSON.stringify({ type: "analyze_request" }));
      return;
    }

    try {
      setLoading(true);
      const formData = new FormData();
      formData.append("code", code);
      formData.append("logs", logs);
      if (screenshot) formData.append("image", screenshot);

      const res = await analyzeCode(formData);
      setResult(res);
      addToHistory(res);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    setResult(null);
  }

  /* ------------------------------
     UI
  -------------------------------- */
  return (
    <div style={styles.page}>
      {/* TOP BAR */}
      <div style={styles.topBar}>
        <h1>Agentic Debug Assistant</h1>
        {token && user ? (
          <div style={styles.profile}>
            <img src={user.picture} alt="avatar" />
            <span>{user.name}</span>
            <button onClick={logout}>Logout</button>
          </div>
        ) : (
          <button onClick={loginWithGoogle}>Sign in with Google</button>
        )}
      </div>

      <div style={styles.body}>
        {/* SIDEBAR */}
        <div style={styles.sidebar}>
          <button onClick={createSession}>Start Collaboration</button>

          {sessionId && <div style={styles.sessionBox}>{sessionId}</div>}

          <input
            placeholder="Paste Session ID"
            value={joinSessionInput}
            onChange={(e) => setJoinSessionInput(e.target.value)}
          />
          <button
            onClick={() => {
              setSessionId(joinSessionInput);
              connectWebSocket(joinSessionInput);
            }}
          >
            Join Collaboration
          </button>

          <h3>History</h3>
          <div style={styles.history}>
            {history.map((h, i) => (
              <div key={i} style={styles.historyItem}>
                <div>{h.timestamp}</div>
                <b>{h.result.error_summary.message}</b>
              </div>
            ))}
          </div>
        </div>

        {/* MAIN APP (RESTORED UI) */}
        <div style={styles.main}>
          <div style={styles.editorRow}>
            <div style={styles.card}>
              <h2>Code</h2>
              <textarea
                style={styles.textarea}
                value={code}
                onChange={(e) => {
                  setCode(e.target.value);
                  ws &&
                    ws.send(
                      JSON.stringify({
                        type: "code_update",
                        code: e.target.value,
                      })
                    );
                }}
              />
            </div>

            <div style={styles.card}>
              <h2>Logs / Error Output</h2>
              <textarea
                style={styles.textarea}
                value={logs}
                onChange={(e) => {
                  setLogs(e.target.value);
                  ws &&
                    ws.send(
                      JSON.stringify({
                        type: "logs_update",
                        logs: e.target.value,
                      })
                    );
                }}
              />
            </div>
          </div>

          <ScreenshotAnnotator onExport={setScreenshot} />

          <button style={styles.analyzeBtn} onClick={handleAnalyze}>
            {loading ? "Analyzing..." : "Analyze"}
          </button>

          {result && (
            <div style={styles.resultsGrid}>
              <div style={{ ...styles.card, borderColor: "#ff6b6b" }}>
                <h2>Error Detection</h2>
                <p><b>Message:</b> {result.error_summary.message}</p>
                <p><b>Root Cause:</b> {result.error_summary.root_cause}</p>
              </div>

              <div style={{ ...styles.card, borderColor: "#4ade80" }}>
                <h2>Fix & Explanation</h2>
                <pre>{result.fixed_code}</pre>
                <p>{result.explanation}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------
   ROUTES
-------------------------------- */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/auth/success" element={<AuthSuccess />} />
    </Routes>
  );
}

/* ------------------------------
   STYLES
-------------------------------- */
const styles = {
  page: { height: "100vh", background: "#0f1117", color: "#fff" },
  topBar: {
    display: "flex",
    justifyContent: "space-between",
    padding: "16px 24px",
  },
  profile: { display: "flex", gap: 8, alignItems: "center" },
  body: { display: "flex", height: "calc(100vh - 64px)" },
  sidebar: {
    width: 280,
    padding: 16,
    borderRight: "1px solid #222",
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  sessionBox: {
    fontFamily: "monospace",
    fontSize: 12,
    background: "#111",
    padding: 6,
  },
  history: { flex: 1, overflowY: "auto" },
  historyItem: {
    background: "#161a22",
    padding: 8,
    borderRadius: 6,
    marginBottom: 6,
  },
  main: { flex: 1, padding: 24 },
  editorRow: { display: "flex", gap: 24 },
  card: {
    flex: 1,
    background: "#161a22",
    border: "1px solid #242938",
    borderRadius: 12,
    padding: 16,
  },
  textarea: {
    width: "100%",
    height: 180,
    background: "#0f1117",
    color: "#fff",
    border: "1px solid #242938",
    borderRadius: 8,
    padding: 12,
  },
  analyzeBtn: {
    margin: "24px auto",
    display: "block",
    padding: "12px 28px",
    background: "#4f8cff",
    border: "none",
    borderRadius: 10,
    color: "#fff",
    fontSize: 16,
  },
  resultsGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 },
};
