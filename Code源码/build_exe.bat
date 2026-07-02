@echo off
rem ============================================================
rem PyCraft 一键打包脚本 (Windows)
rem 双击运行：建虚拟环境 -> 装依赖 -> 跑无头测试 -> PyInstaller 打包
rem 产物: dist\PyCraft.exe  (存档生成在 exe 旁边的 saves\ 目录)
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 python，请先安装 Python 3.10+ 并勾选 Add to PATH
    pause & exit /b 1
)

if not exist venv (
    echo === 创建虚拟环境 ===
    python -m venv venv || (echo [错误] venv 创建失败 & pause & exit /b 1)
)
call venv\Scripts\activate.bat

echo === 安装依赖 ===
python -m pip install --upgrade pip -q
pip install -r requirements.txt pyinstaller -q || (echo [错误] 依赖安装失败 & pause & exit /b 1)

echo === 运行无头测试 (地形/物理/爆炸/存档) ===
python test_headless.py
if errorlevel 1 (
    echo [错误] 测试未通过，已停止打包。请把上面的输出发给 Claude。
    pause & exit /b 1
)
echo === 运行功能测试 (光照/战斗/疾跑/飞行/新方块) ===
python test_features.py
if errorlevel 1 (
    echo [错误] 功能测试未通过，已停止打包。请把上面的输出发给 Claude。
    pause & exit /b 1
)

echo === PyInstaller 打包 ===
rem 说明:
rem   --collect-all glcontext  moderngl 的平台后端是动态导入的，必须收集
rem   --collect-all pyglet     pyglet 的 win32 平台模块也是动态导入的
rem   console 模式便于看报错；确认稳定后可改用 --noconsole
pyinstaller --noconfirm --onefile --name PyCraft ^
    --collect-all glcontext ^
    --collect-all pyglet ^
    main.py
if errorlevel 1 (
    echo [错误] 打包失败。请把上面的输出发给 Claude。
    pause & exit /b 1
)

echo.
echo ============================================
echo  完成! 可执行文件: dist\PyCraft.exe
echo  双击运行即可；存档在 exe 旁的 saves\ 下。
echo  报错信息会显示在控制台窗口里。
echo ============================================
pause
