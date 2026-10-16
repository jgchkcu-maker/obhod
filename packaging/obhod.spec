# PyInstaller spec: builds dist/Obhod/Obhod.exe (onedir, windowed).
# bin/, lists/, strategies/ and data/ are not bundled here: Paths() looks for them
# next to Obhod.exe, so build.ps1 copies them into dist/Obhod afterwards.
from PyInstaller.utils.hooks import collect_data_files

# The app needs only Core/Gui/Widgets/Network/Svg/Xml; everything else drags in
# WebEngine, QML and multimedia (~500 MB).
QT_UNUSED = ["QtWebEngineCore", "QtWebEngineWidgets", "QtWebEngineQuick", "QtWebChannel", "QtWebSockets",
             "QtQml", "QtQuick", "QtQuickWidgets", "QtQuick3D", "QtQuickControls2", "Qt3DCore", "Qt3DRender",
             "Qt3DExtras", "Qt3DInput", "Qt3DLogic", "Qt3DAnimation", "QtMultimedia", "QtMultimediaWidgets",
             "QtSpatialAudio", "QtTextToSpeech", "QtPdf", "QtPdfWidgets", "QtCharts", "QtDataVisualization",
             "QtGraphs", "QtGraphsWidgets", "QtOpenGL", "QtOpenGLWidgets", "QtSql", "QtTest", "QtBluetooth",
             "QtNfc", "QtPositioning", "QtLocation", "QtSensors", "QtSerialPort", "QtSerialBus",
             "QtRemoteObjects", "QtScxml", "QtStateMachine", "QtHttpServer", "QtDesigner", "QtUiTools",
             "QtHelp", "QtConcurrent", "QtDBus", "QtAxContainer", "QtPrintSupport", "QtNetworkAuth"]

a = Analysis(["launcher.py"], pathex=[".."], datas=collect_data_files("qfluentwidgets"),
             hiddenimports=["win32com.client", "win32com.shell.shell", "win32com.shell.shellcon"],
             excludes=["tkinter", "pytest", "qfluentwidgets.multimedia",
                       *(f"PySide6.{m}" for m in QT_UNUSED)])

def keep(entry):
    path = entry[0].replace("\\", "/")
    if "/translations/" in path and not path.endswith("_ru.qm"):
        return False
    return not any(f"/{p}" in path for p in ("qml/", "resources/qtwebengine", "Qt6WebEngine", "Qt6Quick",
                                            "Qt6Qml", "Qt6Pdf", "Qt6Multimedia", "Qt63D", "avcodec",
                                            "avformat", "avutil", "swresample", "swscale", "opengl32sw"))

a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Obhod", console=False,
          version="version_info.txt")
coll = COLLECT(exe, a.binaries, a.datas, name="Obhod")
