#!/usr/bin/env python3
import argparse
import os
import yaml
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, List

try:
    from PIL import Image
except ImportError:
    Image = None


def run_cmd(cmd: List[str], cwd: Optional[Path] = None) -> None:
    """
    执行外部命令；失败直接抛出异常
    """
    print(f"[CMD] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def find_tool(candidate_paths: List[Path], fallback_cmd: Optional[str] = None) -> Optional[str]:
    """
    查找工具的绝对路径；若未找到则返回 None 或备用命令名
    """
    for p in candidate_paths:
        if p and p.exists():
            return str(p)
    if fallback_cmd:
        return fallback_cmd
    return None


def ensure_dir(path: Path) -> None:
    """
    确保目录存在
    """
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    """
    读取文本文件内容
    """
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, content: str) -> None:
    """
    写入文本文件内容
    """
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def copy_icon_to_res(res_dir: Path, icon_path: Path) -> None:
    """
    将图标复制到常见的 mipmap/drawable 密度目录下的 ic_launcher.png
    """
    densities = {
        "mipmap-mdpi": (48, 48),
        "mipmap-hdpi": (72, 72),
        "mipmap-xhdpi": (96, 96),
        "mipmap-xxhdpi": (144, 144),
        "mipmap-xxxhdpi": (192, 192),
        "drawable-mdpi": (48, 48),
        "drawable-hdpi": (72, 72),
        "drawable-xhdpi": (96, 96),
        "drawable-xxhdpi": (144, 144),
        "drawable-xxxhdpi": (192, 192)
    }

    # 尝试使用 Pillow 加载并转换图片
    img = None
    if Image:
        try:
            img = Image.open(icon_path)
            img = img.convert("RGBA")  # 统一转换为 RGBA，避免非 PNG 格式问题
        except Exception as e:
            print(f"[WARN] 无法使用 Pillow 加载图片: {e}")

    for d, size in densities.items():
        target_dir = res_dir / d
        ensure_dir(target_dir)
        target_file = target_dir / "ic_launcher.png"
        
        if img:
            try:
                # Resize 并保存
                resized = img.resize(size, Image.Resampling.LANCZOS)
                resized.save(target_file, "PNG")
                continue
            except Exception as e:
                print(f"[WARN] 图片缩放保存失败 ({d}): {e}")
        
        # 回退：直接复制
        shutil.copyfile(str(icon_path), str(target_file))

    # 兜底：若无 res 目录则创建一个 drawable 并复制
    if not res_dir.exists():
        ensure_dir(res_dir / "drawable")
        if img:
             try:
                img.resize((96, 96), Image.Resampling.LANCZOS).save(res_dir / "drawable" / "ic_launcher.png", "PNG")
             except:
                shutil.copyfile(str(icon_path), str(res_dir / "drawable" / "ic_launcher.png"))
        else:
            shutil.copyfile(str(icon_path), str(res_dir / "drawable" / "ic_launcher.png"))


def create_styles(res_dir: Path) -> None:
    """
    创建 styles.xml 以定义自定义主题（移除启动页）
    """
    values_dir = res_dir / "values"
    ensure_dir(values_dir)
    styles_xml = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="AppTheme" parent="@android:style/Theme.DeviceDefault.NoActionBar">
        <!-- 设置启动预览背景为白色 -->
        <item name="android:windowBackground">@android:color/white</item>
        <!-- 确保启用预览窗口，否则会黑屏等待 -->
        <item name="android:windowDisablePreview">false</item>
    </style>
</resources>
"""
    write_text(values_dir / "styles.xml", styles_xml)


def ensure_debug_keystore(base_dir: Path) -> Path:
    """
    确保存在用于签名的 debug JKS keystore
    """
    ensure_dir(base_dir / "build")
    ks = base_dir / "build" / "debug-jks.keystore"
    if not ks.exists():
        run_cmd([
            "keytool", "-genkey", "-storetype", "JKS",
            "-v", "-keystore", str(ks),
            "-storepass", "android", "-keypass", "android",
            "-keyalg", "RSA", "-keysize", "2048",
            "-validity", "10000", "-alias", "androiddebugkey",
            "-dname", "CN=Android Debug,O=Android,C=US"
        ])
    return ks


def main():
    """
    命令行入口：使用 aapt+d8 快速从空壳工程打包
    """
    # 尝试加载 args.yaml 配置文件
    config = {}
    config_path = Path("args.yaml")
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            print(f"[INFO] 已加载配置文件: {config_path}")
        except Exception as e:
            print(f"[WARN] 加载配置文件失败: {e}")

    parser = argparse.ArgumentParser(description="静态 HTML 一键打包生成 APK")
    parser.add_argument("--html", default=config.get("html", "index.html"), help="HTML 文件路径")
    parser.add_argument("--icon", default=config.get("icon", "icon.png"), help="图标文件路径")
    parser.add_argument("--pkg", default=config.get("pkg", "com.dada"), help="应用包名")
    parser.add_argument("--version", default=config.get("version", "v2.0"), help="版本名称")
    parser.add_argument("--name", default=config.get("name"), help="软件名称")
    parser.add_argument("--out-dir", default=config.get("out_dir"), help="输出目录")
    args = parser.parse_args()

    base_dir = Path.cwd()
    html_path = Path(args.html).resolve()
    icon_path = Path(args.icon).resolve()
    
    if not html_path.exists():
        print(f"HTML 不存在：{html_path}")
        sys.exit(1)
    if not icon_path.exists():
        print(f"图标不存在：{icon_path}")
        sys.exit(1)

    # 软件名称与输出目录
    # 由于删除了 TitleParser，这里如果没有 name 参数，将使用默认值 "App" 或报错
    # 为了健壮性，若未提供 name，使用 "App"
    app_name = args.name or "App"
    
    out_dir = Path(args.out_dir).resolve() if args.out_dir else html_path.parent
    ensure_dir(out_dir)
    final_apk_name = f"{app_name}_{args.pkg}_{args.version}.apk"
    temp_build_name = f"build_temp_{args.pkg}.apk"
    final_apk = out_dir / final_apk_name
    
    ensure_dir(base_dir / "build")
    temp_apk_path = base_dir / "build" / temp_build_name

    # 探测工具：zipalign 与 apksigner
    zipalign = find_tool([
        Path(os.environ.get("ANDROID_HOME", "")) / "build-tools" / "35.0.1" / "zipalign.exe",
        Path(os.environ.get("ANDROID_HOME", "")) / "build-tools" / "34.0.0" / "zipalign.exe",
        Path(os.environ.get("ANDROID_HOME", "")) / "build-tools" / "30.0.3" / "zipalign.exe",
    ], fallback_cmd="zipalign")
    apksigner = find_tool([
        Path(os.environ.get("ANDROID_HOME", "")) / "build-tools" / "35.0.1" / "apksigner.bat",
        Path(os.environ.get("ANDROID_HOME", "")) / "build-tools" / "34.0.0" / "apksigner.bat",
        Path(os.environ.get("ANDROID_HOME", "")) / "build-tools" / "30.0.3" / "apksigner.bat",
    ], fallback_cmd="apksigner")
    
    if zipalign is None or apksigner is None:
        print("未找到 zipalign 或 apksigner，请检查 ANDROID_HOME/build-tools 是否安装")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        aligned_apk = tmpdir / "aligned.apk"

        # 无 apktool：使用 aapt+d8 从空壳工程快速打包
        android_home = Path(os.environ.get("ANDROID_HOME", ""))
        build_tools = android_home / "build-tools" / "35.0.1"
        platforms = android_home / "platforms" / "android-33"
        aapt = find_tool([build_tools / "aapt.exe"], fallback_cmd="aapt")
        d8 = find_tool([build_tools / "d8.bat"], fallback_cmd="d8")
        if aapt is None or d8 is None or not platforms.exists():
            print("未找到 aapt/d8 或 Android 平台 android.jar，请检查 ANDROID_HOME")
            sys.exit(1)
        android_jar = platforms / "android.jar"

        # 基于空壳工程的 Manifest 与 assets 路径
        shell_main = base_dir / "android_shell" / "app" / "src" / "main"
        manifest_src = shell_main / "AndroidManifest.xml"
        manifest_tmp = tmpdir / "AndroidManifest.xml"
        xml = read_text(manifest_src)
        
        # 自动注入配置
        if "<uses-sdk" not in xml:
            xml = xml.replace("<application", '<uses-sdk android:minSdkVersion="21" android:targetSdkVersion="33" />\n    <application')
        
        if "android.permission.INTERNET" not in xml:
            xml = xml.replace("<application", '<uses-permission android:name="android.permission.INTERNET" />\n    <application')
        
        if 'android:icon=' not in xml:
            xml = xml.replace('<application', '<application android:icon="@mipmap/ic_launcher"')
        
        if 'android:theme=' not in xml:
            xml = xml.replace('<application', '<application android:theme="@style/AppTheme"')
        elif 'android:theme="' in xml:
            xml = re.sub(r'android:theme="[^"]+"', 'android:theme="@style/AppTheme"', xml)

        if 'android:exported="true"' not in xml and '<intent-filter>' in xml:
            xml = re.sub(r'(<activity[^>]+)(>)', r'\1 android:exported="true"\2', xml, count=1)

        if 'android:name=".MainActivity"' in xml:
            xml = xml.replace('android:name=".MainActivity"', 'android:name="com.placeholder.shell.MainActivity"')
        
        if 'android:label="' in xml:
            xml = re.sub(r'android:label="[^"]+"', f'android:label="{app_name}"', xml, count=1)

        xml = re.sub(r'package="[^"]+"', f'package="{args.pkg}"', xml, count=1)
        if re.search(r'android:versionName="[^"]+"', xml):
            xml = re.sub(r'android:versionName="[^"]+"', f'android:versionName="{args.version}"', xml, count=1)
        else:
            xml = xml.replace("<manifest ", f'<manifest android:versionName="{args.version}" ')
        write_text(manifest_tmp, xml)

        # 资产与图标
        assets_dir = tmpdir / "assets"
        assets_www = assets_dir / "www"
        ensure_dir(assets_www)
        shutil.copyfile(str(html_path), str(assets_www / "index.html"))

        res_dir = tmpdir / "res"
        ensure_dir(res_dir)
        copy_icon_to_res(res_dir, icon_path)
        create_styles(res_dir)

        unsigned_apk = tmpdir / "unsigned.apk"

        # 编译 Java → DEX
        classes_dex = base_dir / "build" / "dex" / "classes.dex"
        
        if not classes_dex.exists():
            src = shell_main / "java" / "com" / "placeholder" / "shell" / "MainActivity.java"
            classes_dir = tmpdir / "classes"
            ensure_dir(classes_dir)
            run_cmd([
                "javac", "-encoding", "UTF-8", "-source", "1.8", "-target", "1.8",
                "-bootclasspath", str(android_jar),
                "-classpath", str(android_jar),
                "-d", str(classes_dir),
                str(src)
            ])
            dex_out = tmpdir / "dex"
            ensure_dir(dex_out)
            class_files = [str(p) for p in classes_dir.rglob("*.class")]
            if not class_files:
                print("未找到编译产生的 .class 文件")
                sys.exit(1)
            run_cmd([d8, "--min-api", "21", "--output", str(dex_out)] + class_files)
            classes_dex = dex_out / "classes.dex"

        # aapt 打包 + 添加 dex
        try:
            run_cmd([aapt, "package", "-f", "-M", str(manifest_tmp), "-I", str(android_jar), "-A", str(assets_dir), "-S", str(res_dir), "-F", str(unsigned_apk)])
        except subprocess.CalledProcessError:
            print("[WARN] 资源打包失败，回退为不包含 res 的打包（图标将不生效）")
            run_cmd([aapt, "package", "-f", "-M", str(manifest_tmp), "-I", str(android_jar), "-A", str(assets_dir), "-F", str(unsigned_apk)])
        
        run_cmd([aapt, "add", str(unsigned_apk), "classes.dex"], cwd=classes_dex.parent)
        run_cmd([zipalign, "-f", "-p", "4", str(unsigned_apk), str(aligned_apk)])

        # 签名输出
        keystore = ensure_debug_keystore(base_dir)
        run_cmd([
            apksigner, "sign",
            "--ks", str(keystore),
            "--ks-pass", "pass:android",
            "--key-pass", "pass:android",
            "--ks-key-alias", "androiddebugkey",
            "--out", str(temp_apk_path),
            str(aligned_apk)
        ])

        if temp_apk_path.exists():
            if final_apk.exists():
                os.remove(final_apk)
            os.rename(temp_apk_path, final_apk)

    print(f"[OK] 生成 APK：{final_apk}")


if __name__ == "__main__":
    main()
