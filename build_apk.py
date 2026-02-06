#!/usr/bin/env python3
import argparse
import os
import yaml
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, List
try:
    from PIL import Image
except ImportError:
    Image = None



class TitleParser(HTMLParser):
    """
    解析 HTML 文档的 <title>，用于默认软件名称
    """
    def __init__(self):
        super().__init__()
        self._in_title = False
        self.title = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            text = data.strip()
            if text:
                self.title = text


def run_cmd(cmd: List[str], cwd: Optional[Path] = None) -> None:
    """
    执行外部命令；失败直接抛出异常
    :param cmd: 命令及参数列表
    :param cwd: 工作目录
    """
    print(f"[CMD] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def find_tool(candidate_paths: List[Path], fallback_cmd: Optional[str] = None) -> Optional[str]:
    """
    查找工具的绝对路径；若未找到则返回 None 或备用命令名
    :param candidate_paths: 候选绝对路径
    :param fallback_cmd: 备用命令名（可在 PATH 中）
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
    :param path: 目录路径
    """
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    """
    读取文本文件内容
    :param path: 文件路径
    """
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, content: str) -> None:
    """
    写入文本文件内容
    :param path: 文件路径
    :param content: 文本内容
    """
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def parse_title_from_html(html_path: Path) -> Optional[str]:
    """
    从 HTML 文件中解析 <title> 作为默认软件名称
    :param html_path: HTML 文件路径
    :return: 解析到的标题或 None
    """
    parser = TitleParser()
    parser.feed(read_text(html_path))
    return parser.title


def update_manifest(manifest_path: Path, pkg: str, version_name: str) -> None:
    """
    更新 AndroidManifest.xml 的 package 与 android:versionName
    :param manifest_path: Manifest 文件路径
    :param pkg: 包名（applicationId）
    :param version_name: 版本名称
    """
    xml = read_text(manifest_path)
    # 更新 package 属性
    xml = re.sub(r'package="[^"]+"', f'package="{pkg}"', xml, count=1)
    # 更新 versionName；若不存在则插入到 <manifest ...> 标签内
    if re.search(r'android:versionName="[^"]+"', xml):
        xml = re.sub(r'android:versionName="[^"]+"', f'android:versionName="{version_name}"', xml, count=1)
    else:
        xml = xml.replace(
            "<manifest ",
            f'<manifest android:versionName="{version_name}" '
        )
    
    # 确保添加 INTERNET 权限
    if "android.permission.INTERNET" not in xml:
        xml = xml.replace(
            "<application",
            '<uses-permission android:name="android.permission.INTERNET" />\n    <application'
        )
    
    # 确保 application 标签有 android:icon 属性
    if 'android:icon=' not in xml:
        xml = xml.replace('<application', '<application android:icon="@mipmap/ic_launcher"')

    write_text(manifest_path, xml)


def copy_icon_to_res(res_dir: Path, icon_path: Path) -> None:
    """
    将图标复制到常见的 mipmap/drawable 密度目录下的 ic_launcher.png
    :param res_dir: 资源目录（通常为 workdir/res）
    :param icon_path: 图标文件路径
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
        
        # 回退：直接复制（若 Pillow 不可用或处理失败）
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
    :param base_dir: 基础工作目录
    :return: keystore 路径
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
    命令行入口：优先使用 aapt+d8 快速从空壳工程打包；若存在 apktool 则走反编译/回编译路径
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
    parser.add_argument("--html", default=config.get("html", "index.html"), help="HTML 文件路径（默认：配置文件或 index.html）")
    parser.add_argument("--icon", default=config.get("icon", "icon.png"), help="图标文件路径（默认：配置文件或 icon.png）")
    parser.add_argument("--pkg", default=config.get("pkg", "com.dada"), help="应用包名（默认：配置文件或 com.dada）")
    parser.add_argument("--version", default=config.get("version", "v2.0"), help="版本名称（默认：配置文件或 v2.0）")
    parser.add_argument("--name", default=config.get("name"), help="软件名称（默认：配置文件或从 HTML <title> 解析）")
    parser.add_argument("--out-dir", default=config.get("out_dir"), help="输出目录（默认：配置文件或 HTML 同级目录）")
    args = parser.parse_args()

    base_dir = Path.cwd()
    html_path = Path(args.html).resolve()
    icon_path = Path(args.icon).resolve()
    template_apk = base_dir / "android_shell" / "template.apk"

    if not html_path.exists():
        print(f"HTML 不存在：{html_path}")
        sys.exit(1)
    if not icon_path.exists():
        print(f"图标不存在：{icon_path}")
        sys.exit(1)

    # 软件名称与输出目录
    app_name = args.name or parse_title_from_html(html_path)
    out_dir = Path(args.out_dir).resolve() if args.out_dir else html_path.parent
    ensure_dir(out_dir)
    # 使用纯英文临时文件名进行构建，避免 Windows 下工具链处理中文路径异常
    final_apk_name = f"{app_name}_{args.pkg}_{args.version}.apk"
    temp_build_name = f"build_temp_{args.pkg}.apk"
    final_apk = out_dir / final_apk_name
    
    # 将临时签名的 APK 输出到 build 目录，这样其副作用文件 .idsig 也会生成在 build 目录
    ensure_dir(base_dir / "build")
    temp_apk_path = base_dir / "build" / temp_build_name

    # 探测工具：zipalign 与 apksigner 必须；apktool 可选
    apktool = find_tool([base_dir / "apktool.jar"], fallback_cmd=None)
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

        if apktool:
            # apktool 路径：反编译/回编译
            workdir = tmpdir / "workdir"
            unsigned_apk = tmpdir / "unsigned.apk"

            run_cmd(["java", "-jar", apktool, "d", str(template_apk), "-o", str(workdir), "-f"])

            assets_www = workdir / "assets" / "www"
            ensure_dir(assets_www)
            shutil.copyfile(str(html_path), str(assets_www / "index.html"))

            res_dir = workdir / "res"
            ensure_dir(res_dir)
            copy_icon_to_res(res_dir, icon_path)

            manifest_path = workdir / "AndroidManifest.xml"
            update_manifest(manifest_path, args.pkg, args.version)

            run_cmd(["java", "-jar", apktool, "b", str(workdir), "-o", str(unsigned_apk)])
            run_cmd([zipalign, "-f", "-p", "4", str(unsigned_apk), str(aligned_apk)])
        else:
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
            # 确保有 uses-sdk
            if "<uses-sdk" not in xml:
                xml = xml.replace("<application", '<uses-sdk android:minSdkVersion="21" android:targetSdkVersion="33" />\n    <application')
            
            # 确保添加 INTERNET 权限
            if "android.permission.INTERNET" not in xml:
                xml = xml.replace("<application", '<uses-permission android:name="android.permission.INTERNET" />\n    <application')
            
            # 确保 application 标签有 android:icon 属性
            if 'android:icon=' not in xml:
                xml = xml.replace('<application', '<application android:icon="@mipmap/ic_launcher"')
            
            # 确保使用自定义 AppTheme 主题
            if 'android:theme=' not in xml:
                xml = xml.replace('<application', '<application android:theme="@style/AppTheme"')
            elif 'android:theme="' in xml:
                xml = re.sub(r'android:theme="[^"]+"', 'android:theme="@style/AppTheme"', xml)

            # 确保入口 Activity 有 exported="true" (Android 12+)
            if 'android:exported="true"' not in xml and '<intent-filter>' in xml:
                xml = re.sub(r'(<activity[^>]+)(>)', r'\1 android:exported="true"\2', xml, count=1)

            # 关键修复：MainActivity 的 android:name 若为相对路径（如 .MainActivity），
            # 更改 package 后会指向错误的包名。需将其强制修改为绝对路径（原始包名+类名）。
            # 假设原始 Activity 为 .MainActivity 或 com.placeholder.shell.MainActivity
            xml = xml.replace('android:name=".MainActivity"', 'android:name="com.placeholder.shell.MainActivity"')
            
            # 修改应用标签（应用名称）
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

            # 编译 Java → DEX（复用已有 classes.dex 更快）
            classes_dex = base_dir / "build" / "dex" / "classes.dex"
            
            if not classes_dex.exists():
                # 编译 MainActivity.java
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
                # 回退：不打入 res（不设 app 图标），保证快速产出 APK
                print("[WARN] 资源打包失败，回退为不包含 res 的打包（图标将不生效）")
                run_cmd([aapt, "package", "-f", "-M", str(manifest_tmp), "-I", str(android_jar), "-A", str(assets_dir), "-F", str(unsigned_apk)])
            
            # 关键修正：确保 classes.dex 添加到 APK 根目录，而不是带绝对路径
            # 先切换到 dex 目录，然后执行 aapt add classes.dex
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

        # 构建完成后重命名为最终文件名
        if temp_apk_path.exists():
             if final_apk.exists():
                 os.remove(final_apk)
             os.rename(temp_apk_path, final_apk)

    print(f"[OK] 生成 APK：{final_apk}")


if __name__ == "__main__":
    main()
