import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { API_BASE_URL } from "@/utils/helpers/apiBaseUrl";
import { getAccessToken } from "@/utils/auth/tokenStorage";
import { handleSessionExpired } from "@/utils/auth/sessionHandler";
import { removeAuthTokenValuesFromLocalStorage } from "@/utils/auth/localStorageAuthHelper";

const apiInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

apiInstance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

apiInstance.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      removeAuthTokenValuesFromLocalStorage();
      handleSessionExpired();
    }
    return Promise.reject(error);
  },
);

export default apiInstance;
