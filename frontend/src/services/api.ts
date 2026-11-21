import axios from 'axios';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

// Datasets
export const getDemoDataset = async () => {
  const response = await api.get('/datasets/demo');
  return response.data;
};

export const getDemoMetadata = async () => {
  const response = await api.get('/datasets/demo/metadata');
  return response.data;
};

export const uploadDataset = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post('/datasets/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

// Validation
export const runValidation = async (datasetPath?: string, datasetName?: string) => {
  const response = await api.post('/validation/run', {
    dataset_path: datasetPath,
    dataset_name: datasetName,
  });
  return response.data;
};

export const getValidationResult = async (runId: string) => {
  const response = await api.get(`/validation/${runId}`);
  return response.data;
};

export const getChart_data = async (datasetName?: string) => {
  const params = datasetName ? { dataset_name: datasetName } : {};
  const response = await api.get('/chart/data', { params });
  return response.data;
};

// History
export const getValidationHistory = async () => {
  const response = await api.get('/history');
  return response.data;
};

// Reports
export const getJsonReport = async (runId: string) => {
  const response = await api.get(`/reports/${runId}/json`, {
    responseType: 'blob',
  });
  return response;
};

export const getCsvReport = async (runId: string) => {
  const response = await api.get(`/reports/${runId}/csv`, {
    responseType: 'blob',
  });
  return response;
};

export const getTextReport = async (runId: string) => {
  const response = await api.get(`/reports/${runId}/txt`, {
    responseType: 'blob',
  });
  return response;
};

export default api;
