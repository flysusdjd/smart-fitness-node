package com.example.esp32s3;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public final class BackendApiClient {

    private BackendApiClient() {
    }

    public static RegisterResponse register(String backendUrl, String username, String password)
            throws IOException, JSONException {
        JSONObject body = new JSONObject();
        body.put("username", username);
        body.put("password", password);
        JSONObject payload = executeJsonRequest("POST", backendUrl + "/api/auth/register", body, null);
        JSONObject user = payload.getJSONObject("user");
        return new RegisterResponse(user.getString("username"));
    }

    public static LoginResponse login(String backendUrl, String username, String password)
            throws IOException, JSONException {
        JSONObject body = new JSONObject();
        body.put("username", username);
        body.put("password", password);
        JSONObject payload = executeJsonRequest("POST", backendUrl + "/api/auth/login", body, null);
        JSONObject user = payload.getJSONObject("user");
        return new LoginResponse(
                payload.getString("accessToken"),
                payload.optString("expiresAt", ""),
                user.getString("username")
        );
    }

    public static CurrentUserResponse getCurrentUser(String backendUrl, String accessToken)
            throws IOException, JSONException {
        JSONObject payload = executeJsonRequest("GET", backendUrl + "/api/auth/me", null, accessToken);
        JSONObject user = payload.getJSONObject("user");
        return new CurrentUserResponse(
                user.optString("username", ""),
                user.optString("role", "")
        );
    }

    private static JSONObject executeJsonRequest(
            String method,
            String urlString,
            JSONObject body,
            String accessToken
    ) throws IOException, JSONException {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(urlString);
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod(method);
            connection.setConnectTimeout(8000);
            connection.setReadTimeout(10000);
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            connection.setDoInput(true);

            if (accessToken != null && !accessToken.trim().isEmpty()) {
                connection.setRequestProperty("Authorization", "Bearer " + accessToken.trim());
            }

            if (body != null) {
                connection.setDoOutput(true);
                byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
                try (OutputStream outputStream = connection.getOutputStream()) {
                    outputStream.write(bytes);
                    outputStream.flush();
                }
            }

            int statusCode = connection.getResponseCode();
            String responseText = readAll(statusCode >= 200 && statusCode < 300
                    ? connection.getInputStream()
                    : connection.getErrorStream());

            if (statusCode < 200 || statusCode >= 300) {
                String message = extractErrorMessage(responseText);
                throw new IOException(message.isEmpty() ? ("Request failed: " + statusCode) : message);
            }

            if (responseText == null || responseText.trim().isEmpty()) {
                return new JSONObject();
            }
            return new JSONObject(responseText);
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private static String readAll(InputStream inputStream) throws IOException {
        if (inputStream == null) {
            return "";
        }
        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                builder.append(line);
            }
        }
        return builder.toString();
    }

    private static String extractErrorMessage(String responseText) {
        if (responseText == null || responseText.trim().isEmpty()) {
            return "";
        }
        try {
            JSONObject payload = new JSONObject(responseText);
            return payload.optString("detail", responseText);
        } catch (JSONException ignored) {
            return responseText;
        }
    }

    public static final class RegisterResponse {
        public final String username;

        public RegisterResponse(String username) {
            this.username = username;
        }
    }

    public static final class LoginResponse {
        public final String accessToken;
        public final String expiresAt;
        public final String username;

        public LoginResponse(String accessToken, String expiresAt, String username) {
            this.accessToken = accessToken;
            this.expiresAt = expiresAt;
            this.username = username;
        }
    }

    public static final class CurrentUserResponse {
        public final String username;
        public final String role;

        public CurrentUserResponse(String username, String role) {
            this.username = username;
            this.role = role;
        }
    }

}
