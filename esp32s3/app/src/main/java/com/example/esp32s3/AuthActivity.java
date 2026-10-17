// 安卓认证页面：处理后端地址、注册、登录和游客模式入口。
package com.example.esp32s3;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.textfield.TextInputEditText;

import org.json.JSONException;

import java.io.IOException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

// 认证 Activity 控制登录页 UI 和后台请求线程。
public class AuthActivity extends AppCompatActivity {

    private TextInputEditText etBackendUrl;
    private TextInputEditText etUsername;
    private TextInputEditText etPassword;
    private TextView tvAuthStatus;
    private TextView tvAuthHint;
    private Button btnRegister;
    private Button btnLogin;
    private Button btnGuest;

    private SessionManager sessionManager;
    private ExecutorService authExecutor;

    // 初始化表单、恢复后端地址，并绑定注册/登录/游客按钮。
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        sessionManager = new SessionManager(this);
        if (sessionManager.hasAccessMode()) {
            openMainActivity();
            return;
        }

        setContentView(R.layout.activity_auth);

        etBackendUrl = findViewById(R.id.etBackendUrl);
        etUsername = findViewById(R.id.etAuthUsername);
        etPassword = findViewById(R.id.etAuthPassword);
        tvAuthStatus = findViewById(R.id.tvAuthStatus);
        tvAuthHint = findViewById(R.id.tvAuthHint);
        btnRegister = findViewById(R.id.btnRegister);
        btnLogin = findViewById(R.id.btnLogin);
        btnGuest = findViewById(R.id.btnGuest);

        authExecutor = Executors.newSingleThreadExecutor();

        String savedBackendUrl = sessionManager.getBackendUrl();
        if (!savedBackendUrl.isEmpty()) {
            etBackendUrl.setText(savedBackendUrl);
        }
        String rememberedUsername = sessionManager.getUsername();
        if (!rememberedUsername.isEmpty()) {
            etUsername.setText(rememberedUsername);
        }

        btnRegister.setOnClickListener(v -> submitRegister());
        btnLogin.setOnClickListener(v -> submitLogin());
        btnGuest.setOnClickListener(v -> enterAsGuest());
    }

    @Override
    protected void onDestroy() {
        if (authExecutor != null) {
            authExecutor.shutdownNow();
        }
        super.onDestroy();
    }

    // 提交注册请求，成功后保留服务器地址并提示继续登录。
    private void submitRegister() {
        String backendUrl = normalizedBackendUrl();
        String username = valueOf(etUsername);
        String password = valueOf(etPassword);

        if (!validateInputs(backendUrl, username, password)) {
            return;
        }

        setLoading(true);
        tvAuthStatus.setText(R.string.auth_status_registering);
        tvAuthHint.setText(R.string.auth_sync_hint);

        authExecutor.execute(() -> {
            try {
                BackendApiClient.RegisterResponse response =
                        BackendApiClient.register(backendUrl, username, password);
                runOnUiThread(() -> {
                    sessionManager.saveBackendUrl(backendUrl);
                    setLoading(false);
                    etUsername.setText(response.username);
                    tvAuthStatus.setText(R.string.auth_status_register_success);
                    tvAuthHint.setText(R.string.auth_sync_hint);
                    etPassword.requestFocus();
                });
            } catch (IOException | JSONException e) {
                showAuthError(e.getMessage());
            }
        });
    }

    // 提交登录请求，成功后保存令牌并进入主页面。
    private void submitLogin() {
        String backendUrl = normalizedBackendUrl();
        String username = valueOf(etUsername);
        String password = valueOf(etPassword);

        if (!validateInputs(backendUrl, username, password)) {
            return;
        }

        setLoading(true);
        tvAuthStatus.setText(R.string.auth_status_logging_in);
        tvAuthHint.setText(R.string.auth_sync_hint);

        authExecutor.execute(() -> {
            try {
                BackendApiClient.LoginResponse response =
                        BackendApiClient.login(backendUrl, username, password);
                sessionManager.saveLogin(
                        backendUrl,
                        response.accessToken,
                        response.expiresAt,
                        response.username
                );
                runOnUiThread(() -> {
                    setLoading(false);
                    tvAuthStatus.setText(R.string.auth_status_login_success);
                    tvAuthHint.setText(R.string.auth_sync_hint);
                    openMainActivity();
                });
            } catch (IOException | JSONException e) {
                showAuthError(e.getMessage());
            }
        });
    }

    // 游客模式只保存后端地址，不保存访问令牌。
    private void enterAsGuest() {
        String backendUrl = normalizedBackendUrl();
        if (backendUrl.isEmpty()) {
            tvAuthStatus.setText(R.string.auth_status_invalid_server);
            return;
        }
        sessionManager.enableGuestMode(backendUrl);
        tvAuthStatus.setText(R.string.auth_status_guest);
        tvAuthHint.setText(R.string.auth_sync_hint);
        openMainActivity();
    }

    // 进入网络请求前做最基本的表单校验。
    private boolean validateInputs(String backendUrl, String username, String password) {
        if (backendUrl.isEmpty() || !backendUrl.startsWith("http")) {
            tvAuthStatus.setText(R.string.auth_status_invalid_server);
            return false;
        }
        if (username.isEmpty()) {
            tvAuthStatus.setText(R.string.auth_status_invalid_username);
            return false;
        }
        if (password.isEmpty()) {
            tvAuthStatus.setText(R.string.auth_status_invalid_password);
            return false;
        }
        return true;
    }

    private void showAuthError(String message) {
        runOnUiThread(() -> {
            setLoading(false);
            tvAuthStatus.setText(toFriendlyAuthMessage(message));
        });
    }

    // 把底层网络错误转换成适合用户阅读的中文提示。
    private String toFriendlyAuthMessage(String message) {
        if (message == null || message.trim().isEmpty()) {
            return getString(R.string.status_error_generic);
        }
        String lowered = message.toLowerCase();
        if (lowered.contains("failed to connect") || lowered.contains("connect to")) {
            return "无法连接到服务器，请确认手机和电脑连接到同一个 Wi‑Fi 或同一个热点，并检查服务器地址与端口是否正确。";
        }
        if (lowered.contains("not found")) {
            return "服务器地址不正确，请只填写后端根地址，例如：http://电脑局域网IP:8787";
        }
        return message.trim();
    }

    private void setLoading(boolean loading) {
        btnRegister.setEnabled(!loading);
        btnLogin.setEnabled(!loading);
        btnGuest.setEnabled(!loading);
        etBackendUrl.setEnabled(!loading);
        etUsername.setEnabled(!loading);
        etPassword.setEnabled(!loading);
    }

    private String normalizedBackendUrl() {
        return SessionManager.normalizeBackendUrl(valueOf(etBackendUrl));
    }

    private String valueOf(TextInputEditText editText) {
        return editText.getText() == null ? "" : editText.getText().toString().trim();
    }

    private void openMainActivity() {
        Intent intent = new Intent(this, MainActivity.class);
        startActivity(intent);
        finish();
    }
}
