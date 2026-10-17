// 安卓会话管理器：把登录令牌、后端地址、游客模式和语音设置保存在 SharedPreferences。
package com.example.esp32s3;

import android.content.Context;
import android.content.SharedPreferences;

// 集中封装本地会话读写，避免 Activity 直接操作 SharedPreferences 键名。
public final class SessionManager {

    private static final String PREFS_NAME = "smart_fitness_auth";
    private static final String KEY_BACKEND_URL = "backend_url";
    private static final String KEY_ACCESS_TOKEN = "access_token";
    private static final String KEY_TOKEN_EXPIRY = "token_expiry";
    private static final String KEY_USERNAME = "username";
    private static final String KEY_GUEST_MODE = "guest_mode";
    private static final String KEY_VOICE_ENABLED = "voice_enabled";

    private final SharedPreferences preferences;

    public SessionManager(Context context) {
        preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    public String getBackendUrl() {
        return preferences.getString(KEY_BACKEND_URL, "");
    }

    public void saveBackendUrl(String backendUrl) {
        preferences.edit().putString(KEY_BACKEND_URL, normalizeBackendUrl(backendUrl)).apply();
    }

    // 保存完整登录态，并关闭游客模式。
    public void saveLogin(String backendUrl, String accessToken, String tokenExpiry, String username) {
        preferences.edit()
                .putString(KEY_BACKEND_URL, normalizeBackendUrl(backendUrl))
                .putString(KEY_ACCESS_TOKEN, accessToken)
                .putString(KEY_TOKEN_EXPIRY, tokenExpiry)
                .putString(KEY_USERNAME, username)
                .putBoolean(KEY_GUEST_MODE, false)
                .apply();
    }

    // 开启游客模式时清理账号令牌，避免身份混用。
    public void enableGuestMode(String backendUrl) {
        preferences.edit()
                .putString(KEY_BACKEND_URL, normalizeBackendUrl(backendUrl))
                .remove(KEY_ACCESS_TOKEN)
                .remove(KEY_TOKEN_EXPIRY)
                .remove(KEY_USERNAME)
                .putBoolean(KEY_GUEST_MODE, true)
                .apply();
    }

    public void clearSession() {
        preferences.edit()
                .remove(KEY_ACCESS_TOKEN)
                .remove(KEY_TOKEN_EXPIRY)
                .putBoolean(KEY_GUEST_MODE, false)
                .apply();
    }

    public boolean isVoiceEnabled() {
        return preferences.getBoolean(KEY_VOICE_ENABLED, true);
    }

    public void setVoiceEnabled(boolean enabled) {
        preferences.edit().putBoolean(KEY_VOICE_ENABLED, enabled).apply();
    }

    public boolean isLoggedIn() {
        return !getAccessToken().isEmpty() && !getUsername().isEmpty();
    }

    public boolean isGuestMode() {
        return preferences.getBoolean(KEY_GUEST_MODE, false);
    }

    public boolean hasAccessMode() {
        return isLoggedIn() || isGuestMode();
    }

    public String getAccessToken() {
        return preferences.getString(KEY_ACCESS_TOKEN, "");
    }

    public String getTokenExpiry() {
        return preferences.getString(KEY_TOKEN_EXPIRY, "");
    }

    public String getUsername() {
        return preferences.getString(KEY_USERNAME, "");
    }

    // 清理后端地址末尾斜杠和页面路由，保证接口拼接正确。
    public static String normalizeBackendUrl(String rawUrl) {
        if (rawUrl == null) {
            return "";
        }
        String normalized = rawUrl.trim();
        while (normalized.endsWith("/")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        String[] knownRoutes = {"/login", "/dashboard", "/training", "/history", "/debug"};
        boolean stripped = true;
        while (stripped) {
            stripped = false;
            for (String route : knownRoutes) {
                if (normalized.endsWith(route)) {
                    normalized = normalized.substring(0, normalized.length() - route.length());
                    while (normalized.endsWith("/")) {
                        normalized = normalized.substring(0, normalized.length() - 1);
                    }
                    stripped = true;
                }
            }
        }
        return normalized;
    }
}
