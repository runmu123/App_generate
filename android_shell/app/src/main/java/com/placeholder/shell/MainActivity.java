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

public class MainActivity extends Activity {
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

        WebView webView = new WebView(this);
        // 设置 WebView 背景色为 #F9FAFB（与 HTML 背景一致），防止加载时黑屏
        webView.setBackgroundColor(0xFFF9FAFB);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        
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
        webView.loadUrl("file:///android_asset/www/index.html");
    }
}
