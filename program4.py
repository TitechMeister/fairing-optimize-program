import os
import numpy as np

def program_4_generate_autocad_script():
    fairing_name = input("フェアリングの名前を入力してください (例: fairing-1): ")
    base_dir = f""
    
    # 参照データのパス設定
    pos_file_name = input("参照する位置情報ファイル名 (例: fairing-1_positions.txt): ")
    pos_path = os.path.join(base_dir, "foil-place", pos_file_name)
    opt_dir = os.path.join(base_dir, "optimized-foil")
    cmd_dir = os.path.join(base_dir, "AutoCAD-command")

    if not os.path.exists(pos_path):
        print(f"エラー: {pos_path} が見つかりません。")
        return

    # 位置データの読み込み (1列目: x座標オフセット, 2列目: y座標(高さ), 3列目: 翼弦長)
    positions = np.loadtxt(pos_path)
    
    # スクリプトファイルの作成 (.scr)
    script_path = os.path.join(cmd_dir, f"{fairing_name}_draw_wings.scr")
    
    count = 0
    with open(script_path, "w", encoding="utf-8") as f:
        # AutoCADのコマンド設定（OSNAPなどを一時的にオフにすると描画が安定します）
        f.write("OSMODE 0\n") 
        
        for row in positions:
            x_off, y_height, chord, _ = row
            
            # 対応する最適化済み翼型ファイルを探す
            dat_file = os.path.join(opt_dir, f"{fairing_name}_optimized_{int(y_height)}.dat")
            
            if not os.path.exists(dat_file):
                print(f"スキップ: {dat_file} が見つかりません。")
                continue
            
            # 翼型データの読み込み (スキップ行なしで読み込み、コメント行を無視)
            try:
                pts = np.loadtxt(dat_file, skiprows=1)
            except:
                continue

            # AutoCADの SPLINE コマンド開始
            f.write("_SPLINE\n")
            
            for p in pts:
                # 座標変換ロジック:
                # AutoCAD X = (翼型x * 翼弦長) + 側面図でのxオフセット
                # AutoCAD Y = (翼型y * 翼弦長)  <- 正面から見た厚み方向
                # AutoCAD Z = セクションの高さ(y_height)
                ax = (p[0] * chord) + x_off
                ay = p[1] * chord
                az = y_height
                
                # AutoCAD形式で座標を書き出し
                f.write(f"{ax:.6f},{ay:.6f},{az:.6f}\n")
            
            # SPLINEコマンドを終了するための空行（エンター2回分）
            f.write("\n\n")
            count += 1

        f.write("OSMODE 16383\n") # OSNAPを元に戻す

    print(f"--- スクリプト生成完了 ---")
    print(f"生成ファイル: {script_path}")
    print(f"描画予定の断面数: {count}")
    print("\n【AutoCADでの操作手順】")
    print("1. AutoCADを開き、3D表示（等角投影など）にします。")
    print("2. コマンドラインに 'SCRIPT' と入力してエンター。")
    print(f"3. 上記の {fairing_name}_draw_wings.scr を選択してください。")

if __name__ == "__main__":
    program_4_generate_autocad_script()