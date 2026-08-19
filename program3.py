import os
import subprocess
import numpy as np
import tkinter as tk
from tkinter import filedialog
from matplotlib.path import Path
import ezdxf
from scipy.signal import savgol_filter  # スムージング用に追加

# --- 0. xfoil.exe の場所をユーザーに選択させる ---
def get_xfoil_executable():
    root = tk.Tk()
    root.withdraw()
    print("解析に使用する xfoil.exe を選択してください...")
    xfoil_path = filedialog.askopenfilename(
        title="xfoil.exe を選択",
        filetypes=[("実行ファイル", "*.exe"), ("すべてのファイル", "*.*")]
    )
    root.destroy()
    return xfoil_path

# --- 1. XFOILを実際に動かす関数 ---
def run_xfoil(xfoil_exe, airfoil_file, reynolds, alfa=0):
    airfoil_abs_path = os.path.abspath(airfoil_file).replace("\\", "/")
    polar_abs_path = os.path.abspath("tmp.polar").replace("\\", "/")
    
    if os.path.exists(polar_abs_path):
        os.remove(polar_abs_path)

    input_str = (
        f"load {airfoil_abs_path}\n"
        "pane\n"
        "oper\n"
        f"visc {reynolds}\n"
        "iter 200\n"
        f"alfa {alfa}\n"
        f"dump {polar_abs_path}\n"
        "quit\n"
    )

    try:
        subprocess.run(
            [xfoil_exe],
            input=input_str,
            text=True,
            capture_output=True,
            timeout=15
        )
    except Exception as e:
        print(f"  XFOIL起動エラー: {e}")
        return None

    cd = None
    if os.path.exists(polar_abs_path):
        try:
            with open(polar_abs_path, "r") as f:
                lines = f.readlines()
                for line in lines[12:]:
                    parts = line.split()
                    if len(parts) >= 3:
                        val = float(parts[2])
                        if val > 0.0001:
                            cd = val
                            break
        except:
            pass
        finally:
            if os.path.exists(polar_abs_path):
                os.remove(polar_abs_path)
    
    return cd

# --- 2. 翼厚位置をシフトさせる関数 ---
def modify_thickness_pos(base_pts, target_pos_percent):
    x = base_pts[:, 0]
    y = base_pts[:, 1]
    
    half = len(y)//2
    thickness = np.abs(y[:half] - y[::-1][:half]) if len(y)%2==0 else np.abs(y)
    current_max_idx = np.argmax(thickness)
    current_pos_x = x[current_max_idx]
    
    target_pos_x = target_pos_percent / 100.0
    if current_pos_x <= 0 or current_pos_x >= 1: return base_pts
    
    new_x = np.where(x < current_pos_x,
                     x * (target_pos_x / current_pos_x),
                     target_pos_x + (x - current_pos_x) * ((1 - target_pos_x) / (1 - current_pos_x)))
    
    return np.column_stack((new_x, y))

# ベース翼型の現在の最大翼厚位置を取得する補助関数
def get_current_max_thick_pos(pts):
    x = pts[:, 0]
    y = pts[:, 1]
    half = len(y)//2
    thickness = np.abs(y[:half] - y[::-1][:half]) if len(y)%2==0 else np.abs(y)
    return x[np.argmax(thickness)] * 100

# --- 3. メインプログラム ---
def program_3_optimize_fairing():
    XFOIL_EXE = get_xfoil_executable()
    if not XFOIL_EXE:
        print("xfoil.exe が選択されなかったため、終了します。")
        return

    fairing_name = input("フェアリングの名前を入力してください (例: fairing-1): ")
    
    # 34項目
    airfoil_names = [f"base-foil-{i+1}.dat" for i in range(34)]
    hexagon_names = [f"hex-{i+1}.dxf" for i in range(34)]
    
    pos_file_name = input("参照する位置情報ファイル名 (例: fairing-1_positions.txt): ")
    pos_path = os.path.join("foil-place", pos_file_name)
    velocity = float(input("機体速度 (m/s) を入力してください: "))
    
    if not os.path.exists(pos_path):
        print(f"エラー: {pos_path} が見つかりません。")
        return
        
    positions = np.loadtxt(pos_path)
    opt_dir = "optimized-foil"
    os.makedirs(opt_dir, exist_ok=True)

    # 全解析結果を一時保存するリスト
    all_results = []

    for i, row in enumerate(positions):
        if i >= len(airfoil_names): break
        
        x_front, y_coord, chord, _ = row
        re = (velocity * chord) / 1.5e-5
        
        base_dat_path = os.path.join("base-foil", airfoil_names[i])
        hex_dxf_path = os.path.join("restriction-hexagon", hexagon_names[i])
        
        try:
            base_pts = np.loadtxt(base_dat_path, skiprows=1)
            doc = ezdxf.readfile(hex_dxf_path)
            msp = doc.modelspace()
            hex_points = []
            for e in msp.query('LWPOLYLINE LINE'):
                if e.dxftype() == 'LWPOLYLINE':
                    hex_points.extend([(p[0], p[1]) for p in e.get_points()])
                else:
                    hex_points.extend([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)])
            hex_points = list(dict.fromkeys(hex_points))
        except Exception as e:
            print(f"読み込み失敗: {airfoil_names[i]} / {e}")
            continue

        print(f"--- [{i+1}/{len(positions)}] 解析: H={y_coord}mm (Re={re:.1f}) ---")

        PENALTY = 999.0
        best_score = PENALTY
        best_pos_val = get_current_max_thick_pos(base_pts) # 数値としての位置
        best_pos_label = "Base"

        # 1. ベース翼型の計測
        temp_base = "temp_base.dat"
        np.savetxt(temp_base, base_pts, header=f"base", comments='')
        base_cd = run_xfoil(XFOIL_EXE, temp_base, re, alfa=0)
        base_contained = Path(base_pts * chord).contains_points(hex_points).all()

        if base_cd is not None and base_cd > 0.0001 and base_contained:
            best_score = base_cd * chord
            best_pos_label = "Base"
            best_pos_val = get_current_max_thick_pos(base_pts)

        # 2. 変形翼型のスキャン (50% to 60%)
        for pos in range(44, 61):
            current_pts = modify_thickness_pos(base_pts, pos)
            if not Path(current_pts * chord).contains_points(hex_points).all():
                continue

            temp_opt = "temp_opt.dat"
            np.savetxt(temp_opt, current_pts, header=f"pos_{pos}", comments='')
            cd = run_xfoil(XFOIL_EXE, temp_opt, re, alfa=0)
            
            if cd is not None and cd > 0.0001:
                current_score = cd * chord
                if current_score < best_score:
                    best_score = current_score
                    best_pos_val = float(pos)
                    best_pos_label = f"{pos}%"

        # 結果をメモリに保存（まだファイルには書き出さない）
        all_results.append({
            'y_coord': y_coord,
            'x_front': x_front,
            'chord': chord,
            'best_pos_val': best_pos_val,
            'best_score': best_score,
            'base_pts': base_pts # 再生成用に保持
        })
        print(f" -> 解析完了: {best_pos_label} (Score: {best_score:.4e})")

    # --- スムージング工程 ---
    if len(all_results) > 5:
        print("\n--- 全断面のスムージング処理を実行中 ---")
        
        # 窓幅の決定（データ数の1/3程度、最大11の奇数）
        w_size = min(len(all_results) // 3 * 2 + 1, 11)
        if w_size % 2 == 0: w_size -= 1
        
        # 各パラメータを抽出
        x_fronts = np.array([r['x_front'] for r in all_results])
        chords = np.array([r['chord'] for r in all_results])
        pos_vals = np.array([r['best_pos_val'] for r in all_results])
        
        # Savitzky-Golayフィルタで平滑化
        # これにより「ガタつき」を抑えつつ、翼全体のしなりを維持します
        smooth_x = savgol_filter(x_fronts, w_size, 2)
        smooth_c = savgol_filter(chords, w_size, 2)
        smooth_p = savgol_filter(pos_vals, w_size, 2)
        
        # 平滑化された位置情報を保存（後のAutoCADスクリプト等で使用するため）
        smooth_pos_file = os.path.join("foil-place", f"{fairing_name}_smoothed_positions.txt")
        with open(smooth_pos_file, "w") as f:
            for i in range(len(all_results)):
                f.write(f"{smooth_x[i]:.4f} {all_results[i]['y_coord']} {smooth_c[i]:.4f} {smooth_p[i]:.2f}\n")
        print(f" -> 平滑化された位置情報を保存しました: {smooth_pos_file}")

        # スムージング後の数値で最終的な翼型ファイルを書き出し
        print("--- 最終的な翼型データを保存中 ---")
        for i, res in enumerate(all_results):
            final_pts = modify_thickness_pos(res['base_pts'], smooth_p[i])
            save_name = f"{fairing_name}_optimized_{int(res['y_coord'])}.dat"
            header_text = f"Height:{int(res['y_coord'])} SmoothPos:{smooth_p[i]:.2f}% OrigPos:{res['best_pos_val']}"
            np.savetxt(os.path.join(opt_dir, save_name), final_pts, header=header_text, comments='')
    else:
        print("\n警告: データ数が少なすぎるためスムージングをスキップしました。")

    # 一時ファイルの掃除
    for f in ["xfoil_input.txt", "temp_base.dat", "temp_opt.dat", "tmp.polar"]:
        if os.path.exists(f): os.remove(f)
    print("\nすべての工程が終了しました。")

if __name__ == "__main__":
    program_3_optimize_fairing()