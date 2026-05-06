import axios from "axios";

const LOCAL_BACKEND_URL = "http://localhost:8000";
const isLocalBrowser =
  typeof window !== "undefined" &&
  ["localhost", "127.0.0.1"].includes(window.location.hostname);
const BACKEND_URL =
  process.env.REACT_APP_BACKEND_URL || (isLocalBrowser ? LOCAL_BACKEND_URL : "");
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 15000 });

export const getHalls = () => api.get("/halls").then((r) => r.data);
export const getSchools = () => api.get("/schools").then((r) => r.data);
export const getSchool = (id) => api.get(`/schools/${id}`).then((r) => r.data);

export const createStudent = (payload) =>
  api.post("/students", payload).then((r) => r.data);
export const createGuestStudent = () =>
  api.post("/students/guest").then((r) => r.data);
export const claimGuestStudent = (id, payload) =>
  api.post(`/students/${id}/claim`, payload).then((r) => r.data);
export const listStudents = (includeDemo = false) =>
  api.get(`/students?include_demo=${includeDemo}`).then((r) => r.data);
export const getStudent = (id) =>
  api.get(`/students/${id}`).then((r) => r.data);
export const updateStudent = (id, payload) =>
  api.patch(`/students/${id}`, payload).then((r) => r.data);
export const deleteStudent = (id) =>
  api.delete(`/students/${id}`).then((r) => r.data);
export const getRgpd = (id) =>
  api.get(`/students/${id}/rgpd`).then((r) => r.data);
export const rgpdExportUrl = (id) => `${API}/students/${id}/rgpd/export`;
export const getStamps = (id) =>
  api.get(`/students/${id}/stamps`).then((r) => r.data);
export const createStamp = (payload) =>
  api.post("/stamps", payload).then((r) => r.data);
export const deleteStamp = (id) =>
  api.delete(`/stamps/${id}`).then((r) => r.data);
export const rateStamp = (stampId, rating) =>
  api.patch(`/stamps/${stampId}/rating`, { rating }).then((r) => r.data);
export const getRecap = (id) =>
  api.get(`/students/${id}/recap`).then((r) => r.data);

export const createClass = (payload) =>
  api.post("/classes", payload).then((r) => r.data);
export const getClass = (code) =>
  api.get(`/classes/${code}`).then((r) => r.data);
export const getClassStudents = (code) =>
  api.get(`/classes/${code}/students`).then((r) => r.data);
export const deleteClass = (code, cascade = false) =>
  api.delete(`/classes/${code}?cascade=${cascade}`).then((r) => r.data);
export const getLeaderboard = () =>
  api.get("/leaderboard").then((r) => r.data);

export const getAnalytics = () =>
  api.get("/analytics/overview").then((r) => r.data);
export const getLeads = (filters = {}) => {
  const q = new URLSearchParams(filters).toString();
  return api.get(`/analytics/leads?${q}`).then((r) => r.data);
};
export const leadsCsvUrl = (filters = {}) => {
  const q = new URLSearchParams(filters).toString();
  return `${API}/analytics/leads.csv?${q}`;
};

export const adminStats = () =>
  api.get("/admin/stats").then((r) => r.data);
export const adminAllStudents = () =>
  api.get("/admin/all-students").then((r) => r.data);
export const adminAllClasses = () =>
  api.get("/admin/all-classes").then((r) => r.data);
export const adminReset = (keepDemo = true) =>
  api.post(`/admin/reset?keep_demo=${keepDemo}`).then((r) => r.data);
