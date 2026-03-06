import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 300000, // 5 min for generation
});

export const listProjects = () => api.get('/projects/');
export const createProject = (title = '') => api.post('/projects/', { title });
export const getProject = (id) => api.get(`/projects/${id}/`);

export const uploadData = (projectId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/projects/${projectId}/upload-data/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const uploadDocument = (projectId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/projects/${projectId}/upload-document/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const getProfile = (projectId) => api.get(`/projects/${projectId}/profile/`);
export const inferObjectives = (projectId) => api.post(`/projects/${projectId}/infer-objectives/`);
export const getObjectives = (projectId) => api.get(`/projects/${projectId}/objectives/`);
export const updateObjectives = (projectId, data) => api.put(`/projects/${projectId}/objectives/`, data);

export const generatePresentation = (projectId) => api.post(`/projects/${projectId}/generate/`, {}, { timeout: 600000 }); // 10 min
export const getSlides = (projectId) => api.get(`/projects/${projectId}/slides/`);
export const downloadPresentation = (projectId) =>
  `http://localhost:8000/api/projects/${projectId}/download/`;

export const downloadPdf = (projectId) =>
  `http://localhost:8000/api/projects/${projectId}/pdf/`;

export const sendChat = (projectId, message) =>
  api.post(`/projects/${projectId}/chat/`, { message });
export const getChatHistory = (projectId) => api.get(`/projects/${projectId}/chat/`);
