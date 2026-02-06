# HTML 转 APK 打包工具

这是一个轻量级工具，可以将静态 HTML 网页（HTML/JS/CSS）一键打包成 Android 应用（APK）。

## 环境要求

1. **Python 3**: 需安装依赖 `pip install pyyaml`。
2. **Java**: 需安装 JRE 或 JDK (用于运行 apktool 和签名工具)。
3. **Android SDK**: 需设置 `ANDROID_HOME` 环境变量，且安装 Build-Tools (提供 `zipalign` 和 `apksigner`)。

## 快速使用

### 1. 准备资源

* 将你的网页入口文件准备好（默认 `index.html`）。
* 准备一个应用图标（默认 `icon.png`）。

### 2. 修改配置

打开 `args.yaml` 文件，根据需要修改以下信息：

```yaml
html: index.html      # 入口文件
icon: icon.png        # 应用图标
pkg: com.dada         # 应用包名
version: v2.0         # 版本号
name: 打答            # 应用名称
```

### 3. 执行打包

在终端运行：

```bash
python build_apk.py
```

### 4. 获取 APK

打包成功后，APK 文件将生成在当前目录下，例如：`打答_com.dada_v2.0.apk`。
