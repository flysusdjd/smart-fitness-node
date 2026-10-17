// 安卓后端客户端：用 HttpURLConnection 调用 PC 网关认证接口。
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

// 静态工具类，不保存状态，所有方法都围绕 PC 网关 JSON 接口。
// 手机端和网页端账号互通的原因就在这里：它们都调用同一台 PC 网关的 /api/auth/* 接口。
public final class BackendApiClient {

    private BackendApiClient() {
    }

    // 调用 POST /api/auth/register。
    // 输入：服务器地址、用户名、密码；输出：后端确认创建成功的用户名。
    public static RegisterResponse register(String backendUrl, String username, String password)
            throws IOException, JSONException {
        JSONObject body = new JSONObject();
        body.put("username", username);
        body.put("password", password);
        JSONObject payload = executeJsonRequest("POST", backendUrl + "/api/auth/register", body, null);
        JSONObject user = payload.getJSONObject("user");
        return new RegisterResponse(user.getString("username"));
    }

    // 调用 POST /api/auth/login。
    // 登录成功后返回 accessToken，MainActivity 会把它保存起来，后续请求就不用每次重新输入密码。
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

    // 调用 GET /api/auth/me。
    // 通过 Authorization: Bearer <token> 向后端证明“我是谁”，用于校验已保存的登录状态是否还有效。
    public static CurrentUserResponse getCurrentUser(String backendUrl, String accessToken)
            throws IOException, JSONException {
        JSONObject payload = executeJsonRequest("GET", backendUrl + "/api/auth/me", null, accessToken);
        JSONObject user = payload.getJSONObject("user");
        return new CurrentUserResponse(
                user.optString("username", ""),
                user.optString("role", "")
        );
    }

    // 安卓端 HTTP 接口统一入口。
    // 这里集中处理 URL、请求方法、JSON 请求体、Bearer Token、超时和错误响应，避免每个接口重复写网络代码。
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
                // 和网页端 app.js 的 authHeaders() 对应，后端 api.py 会从 Authorization 请求头中解析当前用户。
                connection.setRequestProperty("Authorization", "Bearer " + accessToken.trim());
            }

            if (body != null) {
                // POST 接口需要把 JSONObject 序列化成 UTF-8 字节写入请求体。
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
                // 后端 FastAPI 失败时通常返回 {"detail": "..."}，这里提取 detail 给界面显示。
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

    // 读取响应流为字符串，兼容错误流为空的情况。
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
