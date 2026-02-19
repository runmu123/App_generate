package com.placeholder.shell;

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import android.webkit.SslErrorHandler;
import android.net.http.SslError;
import android.Manifest;
import android.content.pm.PackageManager;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.util.Log;
import java.util.Arrays;

public class MainActivity extends Activity {
    private WebView webView;
    private PermissionRequest currentPermissionRequest;

    /**
     * 初始化并展示 WebView，加载本地 assets 中的 index.html
     * @param savedInstanceState Activity 保存的状态
     */
    @Override
    @SuppressWarnings("deprecation")
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 设置状态栏颜色为 #F9FAFB (灰色背景)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            Window window = getWindow();
            window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
            window.setStatusBarColor(0xFFF9FAFB); // ARGB

            // 如果背景是浅色，需要设置状态栏文字为深色
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                window.getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
            }
        }

        FrameLayout rootLayout = new FrameLayout(this);
        rootLayout.setLayoutParams(new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        webView = new WebView(this);
        webView.setLayoutParams(new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        // 设置 WebView 背景色为 #F9FAFB（与 HTML 背景一致），防止加载时黑屏
        webView.setBackgroundColor(0xFFF9FAFB);

        final ProgressBar progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setLayoutParams(new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 20));
        progressBar.setVisibility(View.GONE);

        rootLayout.addView(webView);
        rootLayout.addView(progressBar);

        setContentView(rootLayout);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setMediaPlaybackRequiresUserGesture(false);
        
        // 允许混合内容 (HTTPS 页面加载 HTTP 资源)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        }

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                // 忽略 SSL 证书错误，允许继续加载 (仅用于调试或自签证书场景)
                handler.proceed();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                // 处理网页权限请求（如录音、摄像头）
                // 仅当是录音权限时，才进行动态权限申请
                boolean needsRecordAudio = false;
                for (String resource : request.getResources()) {
                    if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)) {
                        needsRecordAudio = true;
                        break;
                    }
                }

                if (needsRecordAudio) {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                            // 保存当前的请求对象，以便在权限回调中处理
                            currentPermissionRequest = request;
                            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 1);
                        } else {
                            // 已经有权限，直接授权
                            request.grant(request.getResources());
                        }
                    } else {
                        // Android 6.0 以下，直接授权
                        request.grant(request.getResources());
                    }
                } else {
                    // 其他权限直接授权
                    request.grant(request.getResources());
                }
            }

            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                if (newProgress == 100) {
                    progressBar.setVisibility(View.GONE);
                } else {
                    if (progressBar.getVisibility() == View.GONE) {
                        progressBar.setVisibility(View.VISIBLE);
                    }
                    progressBar.setProgress(newProgress);
                }
                super.onProgressChanged(view, newProgress);
            }
        });

        // 移除启动时的自动权限申请逻辑，改为在 WebChromeClient.onPermissionRequest 中按需申请
        // if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) { ... }

        webView.loadUrl("file:///android_asset/www/index.html");
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        if (requestCode == 1) {
            // 处理录音权限回调
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                // 1. 通知 WebView 权限已获取
                if (currentPermissionRequest != null) {
                    currentPermissionRequest.grant(currentPermissionRequest.getResources());
                    currentPermissionRequest = null;
                }
                
                // 2. 刷新页面以确保 JS 上下文更新 (可选，部分场景需要)
                if (webView != null) {
                   // webView.reload(); // 通常 grant 后不需要 reload，除非 JS 逻辑强依赖
                }
            } else {
                // 用户拒绝了权限
                if (currentPermissionRequest != null) {
                    currentPermissionRequest.deny();
                    currentPermissionRequest = null;
                }
            }
        }
    }
}
