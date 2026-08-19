import os
import ezdxf
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.path import Path

def program_2_check_constraints():
    # フェアリング名とフォルダの指定
    #fairing_name = input("フェアリングの名前を入力してください (例: fairing-1): ")
    base_dir = f""
    
    hex_dir = os.path.join(base_dir, "restriction-hexagon")
    base_airfoil_dir = os.path.join(base_dir, "base-foil")
    
    # 調べたい箇所の入力
    hex_dxf_name = input("調べたい制約の六角形dxfファイル名 (拡張子抜き): ") + ".dxf"
    airfoil_dat_name = input("調べたい基礎翼型datファイル名 (拡張子抜き): ") + ".dat"
    chord_len = float(input("その地点での翼弦長(mm)を入力してください: "))

    # 1. 制約の六角形(dxf)の読み込み
    hex_points = []
    try:
        hex_path = os.path.join(hex_dir, hex_dxf_name)
        doc = ezdxf.readfile(hex_path)
        msp = doc.modelspace()
        for entity in msp.query('LWPOLYLINE LINE'):
            if entity.dxftype() == 'LWPOLYLINE':
                hex_points.extend([(p[0], p[1]) for p in entity.get_points()])
            elif entity.dxftype() == 'LINE':
                hex_points.append((entity.dxf.start.x, entity.dxf.start.y))
                hex_points.append((entity.dxf.end.x, entity.dxf.end.y))
        # 重複する頂点を削除
        hex_points = list(set(hex_points))
        
        if len(hex_points) >= 3:
            # 重心（各点の平均値）を計算
            center_x = sum(p[0] for p in hex_points) / len(hex_points)
            center_y = sum(p[1] for p in hex_points) / len(hex_points)
            
            # 重心からの角度に基づいてソート（反時計回り）
            hex_points.sort(key=lambda p: np.arctan2(p[1] - center_y, p[0] - center_x))
    except Exception as e:
        print(f"DXFの読み込みに失敗しました: {e}")
        return

    # 2. 基礎翼型(dat)の読み込みと翼弦長倍への拡張
    airfoil_pts = []
    try:
        airfoil_path = os.path.join(base_airfoil_dir, airfoil_dat_name)
        with open(airfoil_path, 'r') as f:
            lines = f.readlines()[1:] # 1行目の名前をスキップ
            for line in lines:
                parts = line.split()
                if len(parts) == 2:
                    # 原点を最前縁(0,0)として、翼弦長(chord_len)分に拡張
                    airfoil_pts.append([float(parts[0]) * chord_len, float(parts[1]) * chord_len])
        airfoil_pts = np.array(airfoil_pts)
    except Exception as e:
        print(f"DATファイルの読み込みに失敗しました: {e}")
        return

    # 3. 六角形をはみ出すことなく囲えるかの判定
    # 翼型の点群でポリゴン（閉じた経路）を作成
    airfoil_path = Path(airfoil_pts)
    # 六角形のすべての頂点が翼型の内部にあるかを判定
    is_contained = all(airfoil_path.contains_points(hex_points))

    # 4. 判断結果をテキストで出力
    result_text = "PASS: 六角形をはみ出すことなく囲めています。" if is_contained else "FAIL: 六角形がはみ出しています。"
    print(f"\n[判定結果] {result_text}")
    
    #result_txt_path = os.path.join(base_dir, f"{fairing_name}_program2_result.txt")
    #with open(result_txt_path, "w", encoding="utf-8") as f:
        #f.write(f"判定対象六角形: {hex_dxf_name}\n")
        #f.write(f"判定対象翼型: {airfoil_dat_name}\n")
        #f.write(f"翼弦長: {chord_len} mm\n")
        #f.write(f"結果: {result_text}\n")

    # 5. 六角形と拡張した翼型をplot
    plt.figure(figsize=(12, 6))
    
    # 翼型をプロット
    plt.plot(airfoil_pts[:, 0], airfoil_pts[:, 1], 'b-', label=f"Airfoil: {airfoil_dat_name} (c={chord_len}mm)")
    
    # 六角形をプロット (閉じた線にするため最初の点を末尾に追加)
    hex_plot_pts = hex_points + [hex_points[0]]
    hx, hy = zip(*hex_plot_pts)
    plt.plot(hx, hy, 'r--', linewidth=2, label=f"Hexagon: {hex_dxf_name}")
    plt.fill(hx, hy, 'r', alpha=0.1) # 六角形の内側を薄く塗る

    # 原点(0,0)の強調
    plt.plot(0, 0, 'ko', label="Leading Edge (0,0)")

    plt.gca().set_aspect('equal', adjustable='box')
    plt.title(f"Constraint Check - {result_text}")
    plt.xlabel("X [mm]")
    plt.ylabel("Y [mm]")
    plt.legend()
    plt.grid(True)
    plt.show()

# 実行する場合は以下をアンコメントしてください
if __name__ == "__main__":
    program_2_check_constraints()